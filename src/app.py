"""Interface de demonstração.

Uso: streamlit run src/app.py
"""
import re
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pipeline import Pipeline  # noqa: E402

st.set_page_config(page_title="Voz do cliente", layout="wide")


@st.cache_resource(show_spinner="Carregando índice e modelo de embeddings...")
def carregar():
    return Pipeline()


EXEMPLOS = [
    "O que os clientes relatam sobre problemas relacionados à entrega?",
    "Quais aspectos da experiência de compra são mais elogiados?",
    "Quais são os principais problemas relatados nas avaliações com nota baixa?",
    "O que os clientes mais elogiam em produtos de cama, mesa e banho?",
    "Qual o preço do iPhone 15 na Amazon?",
]

st.title("Voz do cliente: perguntas sobre as avaliações da Olist")
st.caption("Respostas geradas a partir de avaliações recuperadas da base. Cada afirmação cita o id da avaliação.")

with st.sidebar:
    st.subheader("Exemplos")
    for ex in EXEMPLOS:
        if st.button(ex, use_container_width=True):
            st.session_state["pergunta"] = ex
    k = st.slider("Avaliações no contexto", 5, 20, 12)

pergunta = st.text_input("Pergunta", key="pergunta")

if pergunta:
    pipe = carregar()
    with st.spinner("Buscando avaliações e gerando a resposta..."):
        r = pipe.responder(pergunta, k=k)

    c1, c2, c3 = st.columns(3)
    c1.metric("Veredito", r.veredito)
    c2.metric("Avaliações no recorte", f"{r.recorte.get('n', 0):,}".replace(",", "."))
    c3.metric("Maior similaridade", r.portao.get("top_sim"))

    if r.filtros:
        st.info("Filtros aplicados à pergunta: " + "; ".join(r.filtros))

    st.subheader("Resposta")
    st.write(r.resposta)

    if r.evidencias:
        citados = set(re.findall(r"\br\d{6}\b", r.resposta))
        st.subheader("Evidências recuperadas")
        for e in r.evidencias:
            marca = "citada na resposta" if e["doc_id"] in citados else "recuperada"
            atraso = ""
            if e["dias_atraso"] is not None:
                atraso = f" · {int(e['dias_atraso'])} dias vs. prazo"
            titulo = f"[{e['doc_id']}] nota {e['nota']} · {e['categoria']} · {e['ano_mes']}{atraso} ({marca})"
            with st.expander(titulo, expanded=e["doc_id"] in citados):
                st.write(e["texto"])
                st.caption(f"similaridade {e['sim']:.3f} · origem: {e['origem']}")

    with st.expander("Detalhes do portão e do recorte"):
        st.json({"portao": r.portao, "recorte": r.recorte})
