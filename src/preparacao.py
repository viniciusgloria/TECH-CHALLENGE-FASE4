"""Monta a base de documentos a partir dos CSVs da Olist.

Cada avaliação com comentário vira um documento. Os metadados do pedido
(nota, data, atraso na entrega, categoria) ficam ao lado do texto para
poder filtrar na recuperação.

Uso: python src/preparacao.py
"""
import json
import re

import pandas as pd

import config as cfg

URL = re.compile(r"https?://\S+|www\.\S+")
ESPACOS = re.compile(r"\s+")
SO_SIMBOLO = re.compile(r"^[\W\d_]+$")


def limpar(txt: str) -> str:
    txt = URL.sub(" ", txt)
    txt = txt.replace("\r", " ").replace("\n", " ")
    txt = ESPACOS.sub(" ", txt).strip()
    return txt


def carregar():
    r = cfg.RAW
    reviews = pd.read_csv(r / "olist_order_reviews_dataset.csv")
    pedidos = pd.read_csv(
        r / "olist_orders_dataset.csv",
        parse_dates=[
            "order_purchase_timestamp",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    itens = pd.read_csv(r / "olist_order_items_dataset.csv")
    produtos = pd.read_csv(r / "olist_products_dataset.csv")
    trad = pd.read_csv(r / "product_category_name_translation.csv", encoding="utf-8-sig")
    return reviews, pedidos, itens, produtos, trad


def categoria_por_pedido(itens, produtos, trad):
    # pedido com vários itens: fica a categoria do primeiro item
    it = itens.sort_values(["order_id", "order_item_id"]).drop_duplicates("order_id")
    it = it.merge(produtos[["product_id", "product_category_name"]], on="product_id", how="left")
    it = it.merge(trad, on="product_category_name", how="left")
    it = it.rename(columns={"product_category_name": "categoria", "product_category_name_english": "categoria_en"})
    return it[["order_id", "categoria", "categoria_en"]]


def main():
    cfg.PROCESSED.mkdir(parents=True, exist_ok=True)
    cfg.REPORTS.mkdir(parents=True, exist_ok=True)

    reviews, pedidos, itens, produtos, trad = carregar()
    resumo = {"avaliacoes_total": int(len(reviews))}

    # --- seleção: só quem escreveu algo
    reviews["titulo"] = reviews["review_comment_title"].fillna("").astype(str)
    reviews["mensagem"] = reviews["review_comment_message"].fillna("").astype(str)
    reviews["texto"] = (reviews["titulo"].map(limpar) + ". " + reviews["mensagem"].map(limpar)).str.strip(". ")
    reviews["texto"] = reviews["texto"].map(limpar)

    com_texto = reviews[reviews["texto"].str.len() > 0].copy()
    resumo["com_comentario"] = int(len(com_texto))
    resumo["sem_comentario_descartadas"] = resumo["avaliacoes_total"] - resumo["com_comentario"]

    # --- texto sem conteúdo: poucas palavras ou só pontuação/número
    n_palavras = com_texto["texto"].str.split().str.len()
    lixo = (n_palavras < cfg.MIN_PALAVRAS) | com_texto["texto"].str.match(SO_SIMBOLO)
    resumo["descartadas_muito_curtas"] = int(lixo.sum())
    com_texto = com_texto[~lixo]

    # --- a Olist repete a mesma avaliação em review_ids diferentes dentro do pedido
    antes = len(com_texto)
    com_texto["chave"] = com_texto["order_id"] + "|" + com_texto["texto"].str.lower()
    com_texto = com_texto.drop_duplicates("chave")
    resumo["descartadas_duplicadas_no_pedido"] = int(antes - len(com_texto))

    # --- metadados
    cat = categoria_por_pedido(itens, produtos, trad)
    pedidos["dias_atraso"] = (
        pedidos["order_delivered_customer_date"] - pedidos["order_estimated_delivery_date"]
    ).dt.days
    base = com_texto.merge(
        pedidos[["order_id", "order_status", "order_purchase_timestamp", "dias_atraso"]],
        on="order_id",
        how="left",
    ).merge(cat, on="order_id", how="left")

    resumo["sem_pedido_correspondente"] = int(base["order_status"].isna().sum())
    resumo["sem_categoria"] = int(base["categoria"].isna().sum())
    resumo["sem_data_entrega"] = int(base["dias_atraso"].isna().sum())

    base["categoria"] = base["categoria"].fillna("sem_categoria")
    base["categoria_en"] = base["categoria_en"].fillna(base["categoria"])
    base["chegou_atrasado"] = base["dias_atraso"].gt(0).where(base["dias_atraso"].notna())
    base["data_compra"] = base["order_purchase_timestamp"].dt.date.astype("string")
    base["ano_mes"] = base["order_purchase_timestamp"].dt.strftime("%Y-%m")
    base["ano"] = base["order_purchase_timestamp"].dt.year

    base = base.rename(columns={"review_score": "nota", "order_status": "status_pedido"})
    base["n_palavras"] = base["texto"].str.split().str.len()
    base = base.reset_index(drop=True)
    base["doc_id"] = base.index.map(lambda i: f"r{i:06d}")

    cols = [
        "doc_id", "review_id", "order_id", "texto", "nota", "ano", "ano_mes", "data_compra",
        "status_pedido", "dias_atraso", "chegou_atrasado", "categoria", "categoria_en", "n_palavras",
    ]
    base = base[cols]
    base.to_parquet(cfg.DOCUMENTOS, index=False)

    resumo["documentos_finais"] = int(len(base))
    resumo["nota_distribuicao"] = {int(k): int(v) for k, v in base["nota"].value_counts().sort_index().items()}
    resumo["palavras_mediana"] = float(base["n_palavras"].median())
    resumo["palavras_p95"] = float(base["n_palavras"].quantile(0.95))
    resumo["palavras_max"] = int(base["n_palavras"].max())
    resumo["periodo"] = [str(base["data_compra"].min()), str(base["data_compra"].max())]

    with open(cfg.REPORTS / "preparacao_resumo.json", "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
