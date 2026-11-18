"""Gera os embeddings das avaliações e grava no ChromaDB.

Uso: python src/indexacao.py
"""
import shutil
import time

import chromadb
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

import config as cfg


def carregar_modelo() -> SentenceTransformer:
    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    modelo = SentenceTransformer(cfg.MODELO_EMB, device=dispositivo)
    modelo.max_seq_length = cfg.EMB_MAX_TOKENS  # as avaliações têm no máximo 48 palavras
    if dispositivo == "cuda":
        modelo.half()
    return modelo


def metadados(df: pd.DataFrame) -> list[dict]:
    # o Chroma não aceita None nos metadados; ausente vira -1 (flag) ou -999 (dias)
    atraso_flag = df["chegou_atrasado"].map({True: 1, False: 0}).fillna(-1).astype(int)
    dias = df["dias_atraso"].fillna(-999).astype(int)
    saida = []
    for i, r in enumerate(df.itertuples(index=False)):
        saida.append({
            "nota": int(r.nota),
            "ano": int(r.ano),
            "ano_mes": r.ano_mes,
            "categoria": r.categoria,
            "categoria_en": r.categoria_en,
            "status_pedido": r.status_pedido,
            "atrasou": int(atraso_flag.iloc[i]),
            "dias_atraso": int(dias.iloc[i]),
        })
    return saida


def main():
    df = pd.read_parquet(cfg.DOCUMENTOS)
    print(f"{len(df)} documentos")

    if cfg.CHROMA_DIR.exists():
        shutil.rmtree(cfg.CHROMA_DIR)
    cfg.CHROMA_DIR.mkdir(parents=True)

    modelo = carregar_modelo()
    cliente = chromadb.PersistentClient(path=str(cfg.CHROMA_DIR))
    col = cliente.create_collection(cfg.COLECAO, configuration={"hnsw": {"space": "cosine"}})

    inicio = time.time()
    lote = 2000
    for ini in tqdm(range(0, len(df), lote), desc="indexando"):
        parte = df.iloc[ini:ini + lote]
        emb = modelo.encode(
            parte["texto"].tolist(), batch_size=cfg.BATCH_EMB, normalize_embeddings=True,
            convert_to_numpy=True, show_progress_bar=False,
        )
        col.add(
            ids=parte["doc_id"].tolist(),
            embeddings=emb.tolist(),
            documents=parte["texto"].tolist(),
            metadatas=metadados(parte),
        )
    print(f"pronto em {time.time() - inicio:.0f}s, {col.count()} vetores em {cfg.CHROMA_DIR}")

    # uma consulta de teste confirma que o índice carrega e força a gravação em disco
    teste = col.query(query_embeddings=[emb[:1].tolist()[0]], n_results=1)
    assert teste["ids"][0], "índice não respondeu"


if __name__ == "__main__":
    main()
