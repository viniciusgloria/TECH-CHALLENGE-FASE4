"""Recuperação híbrida: vetor (Chroma) + BM25, fundidos por RRF.

O vetor acha avaliações que dizem a mesma coisa com outras palavras; o BM25
pega termos exatos (nome de categoria, "Correios", número do pedido etc.).
Os filtros por metadado valem para os dois lados.
"""
import re
from collections import Counter
from dataclasses import dataclass

import chromadb
import numpy as np
import pandas as pd
import torch
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

import config as cfg
from consulta import TEMAS, Consulta, sem_acento

STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem que e ou mas se ao aos
foi era ser ter tem teve tinha eu me meu minha meus minhas voce voces ele ela eles elas isso isto esse essa este esta
muito mais menos ja nao sim como quando onde qual quais quem pelo pela pelos pelas sobre entre ate so tambem""".split())


def tokenizar(txt: str) -> list[str]:
    txt = sem_acento(txt.lower())
    toks = re.findall(r"[a-z0-9]+", txt)
    saida = []
    for t in toks:
        if t in STOP or len(t) < 2:
            continue
        # raspagem leve de plural/feminino para casar "atrasado/atrasada/atrasados"
        if len(t) > 4 and t.endswith("s"):
            t = t[:-1]
        if len(t) > 4 and t[-1] in "ao":
            t = t[:-1]
        saida.append(t)
    return saida


@dataclass
class Evidencia:
    doc_id: str
    texto: str
    nota: int
    categoria: str
    ano_mes: str
    dias_atraso: float | None
    sim: float          # similaridade de cosseno com a pergunta
    rerank: float       # nota do cross-encoder, de 0 a 1
    rrf: float
    origem: str         # "vetor", "bm25" ou "ambos"


class Recuperador:
    def __init__(self):
        self.df = pd.read_parquet(cfg.DOCUMENTOS).reset_index(drop=True)
        self.pos = {d: i for i, d in enumerate(self.df["doc_id"])}
        dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        self.modelo = SentenceTransformer(cfg.MODELO_EMB, device=dispositivo)
        self.modelo.max_seq_length = cfg.EMB_MAX_TOKENS
        self.reranker = CrossEncoder(cfg.MODELO_RERANK, device=dispositivo, max_length=256)
        if dispositivo == "cuda":
            self.modelo.half()
            self.reranker.model.half()
        cliente = chromadb.PersistentClient(path=str(cfg.CHROMA_DIR))
        self.col = cliente.get_collection(cfg.COLECAO)
        corpus_tok = [tokenizar(t) for t in self.df["texto"]]
        self.bm25 = BM25Okapi(corpus_tok)
        self.freq_doc = Counter(t for toks in corpus_tok for t in set(toks))
        self.categorias_en = set(self.df["categoria_en"].unique())

    def cobertura(self, pergunta: str) -> tuple[float, list[str]]:
        """Fração dos termos da pergunta que existem no vocabulário da base.

        Termos que quase não aparecem (menos de MIN_DF avaliações) contam como
        ausentes. "iPhone", "Amazon" ou "cenoura" ficam de fora e puxam a nota
        para baixo; "entrega" ou "defeito" passam.
        """
        termos = [t for t in tokenizar(pergunta) if not t.isdigit()]
        if not termos:
            return 1.0, []
        ausentes = [t for t in termos if self.freq_doc.get(t, 0) < cfg.MIN_DF]
        return 1 - len(ausentes) / len(termos), ausentes

    # ---- filtros
    def mascara(self, filtros: dict) -> np.ndarray:
        m = np.ones(len(self.df), dtype=bool)
        if "nota" in filtros:
            lo, hi = filtros["nota"]
            m &= self.df["nota"].between(lo, hi).to_numpy()
        if "ano" in filtros:
            m &= (self.df["ano"] == filtros["ano"]).to_numpy()
        if "ano_mes" in filtros:
            m &= (self.df["ano_mes"] == filtros["ano_mes"]).to_numpy()
        if "categoria_en" in filtros:
            m &= self.df["categoria_en"].isin(filtros["categoria_en"]).to_numpy()
        if "atrasou" in filtros:
            m &= (self.df["chegou_atrasado"] == bool(filtros["atrasou"])).fillna(False).to_numpy()
        return m

    @staticmethod
    def where_chroma(filtros: dict):
        conds = []
        if "nota" in filtros:
            lo, hi = filtros["nota"]
            conds.append({"nota": {"$gte": lo}})
            conds.append({"nota": {"$lte": hi}})
        if "ano" in filtros:
            conds.append({"ano": filtros["ano"]})
        if "ano_mes" in filtros:
            conds.append({"ano_mes": filtros["ano_mes"]})
        if "categoria_en" in filtros:
            cats = filtros["categoria_en"]
            conds.append({"categoria_en": cats[0]} if len(cats) == 1 else {"categoria_en": {"$in": cats}})
        if "atrasou" in filtros:
            conds.append({"atrasou": int(filtros["atrasou"])})
        if not conds:
            return None
        return conds[0] if len(conds) == 1 else {"$and": conds}

    # ---- busca
    def _embed_pergunta(self, texto: str) -> np.ndarray:
        v = self.modelo.encode([texto], normalize_embeddings=True, convert_to_numpy=True)[0]
        return v.astype(np.float32)

    def buscar(self, c: Consulta, k: int = cfg.K_FINAL) -> tuple[list[Evidencia], dict]:
        mask = self.mascara(c.filtros)
        n_recorte = int(mask.sum())
        if n_recorte == 0:
            return [], {"n_recorte": 0}

        q = self._embed_pergunta(c.texto_busca)

        # semântico
        r = self.col.query(
            query_embeddings=[q.tolist()],
            n_results=min(cfg.K_SEMANTICO, n_recorte),
            where=self.where_chroma(c.filtros),
            include=["embeddings"],
        )
        ids_vet = r["ids"][0]
        embs = {i: np.asarray(e, dtype=np.float32) for i, e in zip(ids_vet, r["embeddings"][0])}

        # lexical, só dentro do recorte
        tok = tokenizar(c.texto_lexical)
        scores = np.asarray(self.bm25.get_scores(tok)) if tok else np.zeros(len(self.df))
        scores = np.where(mask, scores, -1.0)
        topo = np.argsort(-scores)[: cfg.K_BM25]
        ids_bm = [self.df["doc_id"].iat[i] for i in topo if scores[i] > 0]

        # fusão
        rrf: dict[str, float] = {}
        for lista in (ids_vet, ids_bm):
            for rank, d in enumerate(lista):
                rrf[d] = rrf.get(d, 0.0) + 1.0 / (cfg.RRF_K + rank + 1)
        ordem = sorted(rrf, key=rrf.get, reverse=True)

        # reordena os melhores da fusão com o cross-encoder
        nota_rr = self._reordenar(c.texto_busca, ordem)
        reordenados = sorted(nota_rr, key=nota_rr.get, reverse=True)

        # embeddings dos que só vieram do BM25 (para medir similaridade e repetição)
        falta = [d for d in reordenados if d not in embs]
        if falta:
            g = self.col.get(ids=falta, include=["embeddings"])
            for i, e in zip(g["ids"], g["embeddings"]):
                embs[i] = np.asarray(e, dtype=np.float32)

        escolhidos = self._sem_repeticao(reordenados, embs, k)

        evid = []
        for d in escolhidos:
            row = self.df.iloc[self.pos[d]]
            dias = row["dias_atraso"]
            origem = "ambos" if (d in ids_vet and d in ids_bm) else ("vetor" if d in ids_vet else "bm25")
            evid.append(Evidencia(
                doc_id=d, texto=row["texto"], nota=int(row["nota"]), categoria=row["categoria_en"],
                ano_mes=row["ano_mes"], dias_atraso=None if pd.isna(dias) else float(dias),
                sim=float(embs[d] @ q), rerank=nota_rr[d], rrf=rrf[d], origem=origem,
            ))
        info = {"n_recorte": n_recorte, "recorte": self.estatisticas(mask)}
        return evid, info

    def _reordenar(self, pergunta: str, ordem: list[str]) -> dict[str, float]:
        """Nota do cross-encoder para os primeiros candidatos da fusão."""
        cand = ordem[: cfg.K_REORDENAR]
        pares = [(pergunta, self.df["texto"].iat[self.pos[d]]) for d in cand]
        notas = self.reranker.predict(pares, convert_to_numpy=True, batch_size=32)
        return {d: float(n) for d, n in zip(cand, notas)}

    @staticmethod
    def _sem_repeticao(ordem: list[str], embs: dict, k: int) -> list[str]:
        """Mantém a ordem e pula avaliações quase idênticas a uma já escolhida.

        A Olist tem muito comentário curto que se repete ("produto chegou no prazo"),
        e doze evidências iguais não dizem nada a mais que uma.
        """
        escolhidos: list[str] = []
        for d in ordem:
            if all(float(embs[d] @ embs[e]) < cfg.LIMITE_REDUNDANCIA for e in escolhidos):
                escolhidos.append(d)
            if len(escolhidos) == k:
                break
        return escolhidos

    # ---- números do recorte, para o modelo não chutar proporções
    def estatisticas(self, mask: np.ndarray) -> dict:
        sub = self.df[mask]
        tx = sub["texto"].map(lambda t: sem_acento(t.lower()))
        temas = {}
        for nome, padrao in TEMAS.items():
            temas[nome] = int(tx.str.contains(padrao, regex=True).sum())
        return {
            "n": int(len(sub)),
            "notas": {int(k): int(v) for k, v in sub["nota"].value_counts().sort_index().items()},
            "temas": temas,
        }
