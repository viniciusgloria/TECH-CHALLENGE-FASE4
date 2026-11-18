"""Compara variantes de ranking com julgamento de relevância por pooling.

Etapas (rodam em ordem, cada uma guarda cache em disco):
  candidatos  gera o top-K de cada variante para cada pergunta e junta tudo num pool
  julgar      um modelo de linguagem dá nota 0, 1 ou 2 a cada avaliação do pool
  metricas    P@10, nDCG@10 e MRR por variante

Uso: python src/ranking_benchmark.py [--etapa candidatos|julgar|metricas|tudo]
"""
import argparse
import json
import math
import os
import random
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
from sentence_transformers import CrossEncoder, SentenceTransformer

import config as cfg
from avaliacao import DENTRO
from consulta import interpretar
from recuperacao import Recuperador

CACHE = cfg.INDEX / "benchmark"
K_AVAL = 10
K_CAND = 40
MODELOS = {
    "e5": ("intfloat/multilingual-e5-base", "query: ", "passage: "),
    "bge": (cfg.MODELO_EMB, "", ""),
}
RERANKER = cfg.MODELO_RERANK


def embeddings_corpus(rec: Recuperador, chave: str) -> np.ndarray:
    arq = CACHE / f"emb_{chave}.npy"
    if arq.exists():
        return np.load(arq)
    nome, _, pref_doc = MODELOS[chave]
    m = SentenceTransformer(nome, device="cuda")
    m.max_seq_length = 128
    m.half()
    E = m.encode(
        [pref_doc + t for t in rec.df["texto"]], batch_size=64,
        normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True,
    ).astype(np.float16)
    np.save(arq, E)
    del m
    torch.cuda.empty_cache()
    return E


def top_denso(E, q, mask, k):
    s = (torch.from_numpy(E).cuda().float() @ torch.from_numpy(q).cuda().float()).cpu().numpy()
    s = np.where(mask, s, -9.0)
    idx = np.argsort(-s)[:k]
    return [int(i) for i in idx if mask[i]]


def top_bm25(rec, c, mask, k):
    from recuperacao import tokenizar
    sc = np.asarray(rec.bm25.get_scores(tokenizar(c.texto_lexical)))
    sc = np.where(mask, sc, -1.0)
    idx = np.argsort(-sc)[:k]
    return [int(i) for i in idx if sc[i] > 0]


def rrf(*listas, k=cfg.RRF_K):
    pont = {}
    for l in listas:
        for r, i in enumerate(l):
            pont[i] = pont.get(i, 0.0) + 1.0 / (k + r + 1)
    return sorted(pont, key=pont.get, reverse=True)


def mmr_rerank(cand, rel, E, lam, k=K_AVAL):
    emb = {i: E[i].astype(np.float32) for i in cand}
    escolhidos, restantes = [], list(cand)
    while restantes and len(escolhidos) < k:
        def pontuacao(i):
            sim = max((float(emb[i] @ emb[e]) for e in escolhidos), default=0.0)
            return lam * rel[i] - (1 - lam) * sim
        melhor = max(restantes, key=pontuacao)
        escolhidos.append(melhor)
        restantes.remove(melhor)
    return escolhidos


def mmr_cosseno(cand, E, q, lam, k=K_AVAL, limite=0.95):
    """MMR com o cosseno da pergunta como relevância (a versão inicial do pipeline)."""
    emb = {i: E[i].astype(np.float32) for i in cand}
    rel = {i: float(emb[i] @ q.astype(np.float32)) for i in cand}
    escolhidos, restantes = [], list(cand)
    while restantes and len(escolhidos) < k:
        melhor, melhor_s = None, -1e9
        for i in restantes:
            sim = max((float(emb[i] @ emb[e]) for e in escolhidos), default=0.0)
            if sim >= limite:
                continue
            s = lam * rel[i] - (1 - lam) * sim
            if s > melhor_s:
                melhor, melhor_s = i, s
        if melhor is None:
            break
        escolhidos.append(melhor)
        restantes.remove(melhor)
    return escolhidos


def diversidade(E, idx):
    m = E[idx].astype(np.float32)
    s = m @ m.T
    n = len(idx)
    return float(1 - (s.sum() - n) / (n * (n - 1))) if n > 1 else 0.0


def candidatos():
    CACHE.mkdir(parents=True, exist_ok=True)
    rec = Recuperador()
    E = {k: embeddings_corpus(rec, k) for k in MODELOS}
    modelos_q = {k: SentenceTransformer(MODELOS[k][0], device="cuda") for k in MODELOS}
    for m in modelos_q.values():
        m.half()
    reranker = CrossEncoder(RERANKER, device="cuda", max_length=256)

    saida = {}
    for pergunta, _ in DENTRO:
        c = interpretar(pergunta, rec.categorias_en)
        mask = rec.mascara(c.filtros)
        q = {k: modelos_q[k].encode([MODELOS[k][1] + c.texto_busca], normalize_embeddings=True,
                                    convert_to_numpy=True)[0] for k in MODELOS}
        dens = {k: top_denso(E[k], q[k], mask, K_CAND) for k in MODELOS}
        bm = top_bm25(rec, c, mask, K_CAND)

        v = {
            "denso e5": dens["e5"],
            "denso bge-m3": dens["bge"],
            "bm25": bm,
            "híbrido e5": rrf(dens["e5"], bm),
            "híbrido bge-m3": rrf(dens["bge"], bm),
        }
        for nome, base in (("híbrido e5", "híbrido e5"), ("híbrido bge-m3", "híbrido bge-m3")):
            cand = v[base][:30]
            pares = [(pergunta, rec.df["texto"].iat[i]) for i in cand]
            sc = reranker.predict(pares, convert_to_numpy=True, batch_size=32)
            v[nome + " + rerank"] = [cand[j] for j in np.argsort(-sc)]
            if nome == "híbrido bge-m3":
                # MMR sobre a nota do reranker (sigmoide, 0 a 1) em vez do cosseno comprimido
                rel = {cand[j]: float(1 / (1 + np.exp(-sc[j]))) for j in range(len(cand))}
                for lam in (0.8, 0.9):
                    v[f"híbrido bge-m3 + rerank + MMR λ={lam}"] = mmr_rerank(cand, rel, E["bge"], lam)

        # o que o pipeline fazia no começo: híbrido e5 + MMR sobre o cosseno (λ=0,7)
        v["híbrido e5 + MMR (versão inicial)"] = mmr_cosseno(v["híbrido e5"][:K_CAND], E["e5"], q["e5"], 0.7)

        pool = sorted({i for l in v.values() for i in l[:K_AVAL]})
        div = {k: diversidade(E["bge"], l[:K_AVAL]) for k, l in v.items()}
        saida[pergunta] = {"variantes": {k: l[:K_AVAL] for k, l in v.items()}, "pool": pool, "diversidade": div}
        print(f"{len(pool):3d} no pool | {pergunta[:70]}", flush=True)
    (CACHE / "candidatos.json").write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")


PROMPT_JUIZ = """Você avalia a relevância de avaliações de clientes de um e-commerce para uma pergunta de um gestor.

Pergunta: {pergunta}

Dê uma nota a cada avaliação:
2 = relata diretamente o que a pergunta procura (evidência clara e específica)
1 = tem relação com a pergunta, mas é genérica, vaga ou cobre só em parte
0 = não ajuda a responder

Avaliações:
{docs}

Responda somente com um objeto JSON no formato {{"d1": 2, "d2": 0, ...}}, com todas as avaliações listadas."""


def chamar_claude(prompt: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            ["claude", "-p", "--model", os.getenv("CLAUDE_MODELO_JUIZ", "sonnet"), "--tools", "",
             "--no-session-persistence", "--output-format", "text"],
            input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=tmp,
            timeout=300, shell=(os.name == "nt"),
        )
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return r.stdout


def julgar():
    rec = Recuperador()
    cand = json.loads((CACHE / "candidatos.json").read_text(encoding="utf-8"))
    arq = CACHE / "julgamentos.json"
    feitos = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}

    def um(pergunta):
        ja = feitos.get(pergunta, {})
        # só julga o que ainda não tem nota (o pool cresce quando entram variantes novas)
        pool = [i for i in cand[pergunta]["pool"] if str(i) not in ja]
        if not pool:
            return pergunta, ja
        random.Random(7).shuffle(pool)  # ordem embaralhada para não induzir viés de posição
        docs = "\n".join(f"d{j + 1}: {rec.df['texto'].iat[i]}" for j, i in enumerate(pool))
        resp = chamar_claude(PROMPT_JUIZ.format(pergunta=pergunta, docs=docs))
        ini, fim = resp.find("{"), resp.rfind("}")
        notas = json.loads(resp[ini:fim + 1])
        novos = {str(pool[j]): int(notas.get(f"d{j + 1}", 0)) for j in range(len(pool))}
        return pergunta, {**ja, **novos}

    with ThreadPoolExecutor(max_workers=4) as ex:
        for p, n in ex.map(um, list(cand)):
            feitos[p] = n
            print(f"julgado: {p[:70]}", flush=True)
    arq.write_text(json.dumps(feitos, ensure_ascii=False), encoding="utf-8")


def metricas():
    cand = json.loads((CACHE / "candidatos.json").read_text(encoding="utf-8"))
    jul = json.loads((CACHE / "julgamentos.json").read_text(encoding="utf-8"))
    variantes = list(next(iter(cand.values()))["variantes"])
    linhas = []
    for v in variantes:
        p10, p10_forte, ndcg, mrr, divs = [], [], [], [], []
        for pergunta, d in cand.items():
            divs.append(d["diversidade"][v])
            notas = [jul[pergunta].get(str(i), 0) for i in d["variantes"][v][:K_AVAL]]
            p10.append(sum(n >= 1 for n in notas) / K_AVAL)
            p10_forte.append(sum(n == 2 for n in notas) / K_AVAL)
            dcg = sum((2 ** n - 1) / math.log2(r + 2) for r, n in enumerate(notas))
            ideal = sorted(jul[pergunta].values(), reverse=True)[:K_AVAL]
            idcg = sum((2 ** n - 1) / math.log2(r + 2) for r, n in enumerate(ideal))
            ndcg.append(dcg / idcg if idcg else 0.0)
            primeiro = next((r for r, n in enumerate(notas) if n == 2), None)
            mrr.append(1 / (primeiro + 1) if primeiro is not None else 0.0)
        linhas.append((v, np.mean(p10), np.mean(p10_forte), np.mean(ndcg), np.mean(mrr), np.mean(divs)))
    linhas.sort(key=lambda x: -x[3])

    md = ["| Variante | P@10 (nota ≥1) | P@10 (nota 2) | nDCG@10 | MRR | Diversidade |", "|---|---:|---:|---:|---:|---:|"]
    for v, a, b, c, d, e in linhas:
        md.append(f"| {v} | {a:.3f} | {b:.3f} | {c:.3f} | {d:.3f} | {e:.3f} |")
    tabela = "\n".join(md)
    print(tabela)
    cfg.REPORTS.mkdir(parents=True, exist_ok=True)
    (cfg.REPORTS / "ranking_benchmark.md").write_text(
        f"# Benchmark de ranking\n\n{len(cand)} perguntas, top-{K_AVAL}, relevância por pooling.\n"
        "Diversidade = 1 menos a similaridade média entre os pares do top-10 (maior = evidências mais variadas).\n\n"
        f"{tabela}\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--etapa", default="tudo", choices=["candidatos", "julgar", "metricas", "tudo"])
    a = ap.parse_args()
    if a.etapa in ("candidatos", "tudo"):
        candidatos()
    if a.etapa in ("julgar", "tudo"):
        julgar()
    if a.etapa in ("metricas", "tudo"):
        metricas()
