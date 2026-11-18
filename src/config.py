import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

RAW = RAIZ / "data" / "raw"
PROCESSED = RAIZ / "data" / "processed"
REPORTS = RAIZ / "reports"

DOCUMENTOS = PROCESSED / "documentos.parquet"

# O índice do Chroma não grava em pasta com acento no Windows (o HNSW nativo falha).
# Se o projeto estiver num caminho assim, aponte INDEX_DIR para um caminho ASCII no .env.
INDEX = Path(os.getenv("INDEX_DIR") or RAIZ / "data" / "index")
CHROMA_DIR = INDEX / "chroma"
COLECAO = "avaliacoes_olist"


def _modelo(nome_hub: str, pasta: str) -> str:
    # MODELOS_DIR: pasta com modelos baixados à mão, para quando o download pelo hub trava
    base = os.getenv("MODELOS_DIR")
    if base and (Path(base) / pasta).is_dir():
        return str(Path(base) / pasta)
    return nome_hub


# embeddings e reranker (escolhidos em reports/ranking_benchmark.md)
MODELO_EMB = _modelo("BAAI/bge-m3", "bge-m3")
MODELO_RERANK = _modelo("BAAI/bge-reranker-v2-m3", "bge-reranker-v2-m3")
EMB_MAX_TOKENS = 128
BATCH_EMB = 64

# preparação
MIN_PALAVRAS = 3

# recuperação
K_SEMANTICO = 40
K_BM25 = 40
K_REORDENAR = 30      # quantos candidatos da fusão passam pelo reranker
K_FINAL = 12
RRF_K = 60
# mais que isso de similaridade entre dois textos e o segundo é descartado como repetido
LIMITE_REDUNDANCIA = 0.95

# portão de evidência
# Piso de cosseno (bge-m3) para a melhor avaliação recuperada. Calibrado nas 35
# perguntas de src/avaliacao.py: dentro do escopo o topo foi de 0,61 a 0,87; fora,
# de 0,38 a 0,76. 0,55 fica entre os dois grupos e é validado em perguntas novas
# (conjunto "teste" do avaliacao.py). A nota do reranker não entra aqui: em pergunta
# ampla ela fica perto de zero mesmo com boas evidências, então só serve para ordenar.
# O resto do filtro é a cobertura de vocabulário e o veredito do modelo.
SIM_PISO = 0.55
MIN_DF = 3               # termo com menos avaliações que isso conta como ausente da base
COBERTURA_MINIMA = 0.5
