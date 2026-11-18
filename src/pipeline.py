"""Pipeline completo: pergunta -> filtros -> recuperação -> portão -> contexto -> resposta.

Uso rápido:
    python src/pipeline.py "O que os clientes dizem sobre atraso na entrega?"
"""
import json
import sys
from dataclasses import asdict, dataclass

import config as cfg
from consulta import Consulta, interpretar
from geracao import gerar
from recuperacao import Evidencia, Recuperador, tokenizar

RECUSA = {
    "sem_recorte": "Não há avaliações na base que atendam aos filtros pedidos, então não consigo responder.",
    "fora_do_periodo": (
        "A base cobre compras de setembro de 2016 a outubro de 2018, então não há avaliações do período citado na pergunta."
    ),
    "fora_do_vocabulario": (
        "A pergunta fala de termos que não aparecem nas avaliações ({ausentes}). "
        "A base só tem comentários de clientes sobre pedidos, e não dá para responder a isso a partir dela."
    ),
    "pouca_evidencia": (
        "Não encontrei avaliações suficientemente próximas da pergunta para sustentar uma resposta."
    ),
    "sem_suporte": (
        "As avaliações recuperadas não sustentam uma resposta para essa pergunta. {motivo}"
    ),
}

VEREDITOS = ("SUPORTADA", "PARCIAL", "SEM_SUPORTE")


@dataclass
class Resultado:
    pergunta: str
    filtros: list
    evidencias: list
    recorte: dict
    portao: dict
    resposta: str
    chamou_modelo: bool
    veredito: str          # SUPORTADA, PARCIAL, SEM_SUPORTE ou BARRADA (portão, sem chamar o modelo)
    contexto: str = ""


def portao(evid: list[Evidencia], n_recorte: int, cobertura: float, ausentes: list[str],
           ano_fora: int | None = None, tem_assunto: bool = True) -> dict:
    """Primeira barreira, antes de chamar o modelo.

    Barra quando: o filtro não deixa nenhuma avaliação; metade ou mais dos termos
    da pergunta não existe na base; ou nem a melhor avaliação chega no piso de
    similaridade. A segunda barreira é o veredito do próprio modelo (ver responder).

    O piso de similaridade só vale quando a pergunta tem assunto além dos filtros.
    "Quais as queixas sobre eletrodomésticos?" vira categoria + nota baixa e não
    sobra nada para comparar; o cosseno da frase genérica contra avaliações
    concretas fica baixo e barraria uma pergunta legítima.
    """
    top = max((e.sim for e in evid), default=0.0)
    base = {"top_sim": round(top, 4), "cobertura": round(cobertura, 2), "ausentes": ausentes}
    if ano_fora is not None:
        return {**base, "ok": False, "motivo": "fora_do_periodo", "ano": ano_fora}
    if n_recorte == 0:
        return {**base, "ok": False, "motivo": "sem_recorte"}
    if cobertura < cfg.COBERTURA_MINIMA:
        return {**base, "ok": False, "motivo": "fora_do_vocabulario"}
    if tem_assunto and top < cfg.SIM_PISO:
        return {**base, "ok": False, "motivo": "pouca_evidencia"}
    return {**base, "ok": True, "motivo": None}


def separar_veredito(texto: str) -> tuple[str, str]:
    """O modelo abre a resposta com 'VEREDITO: X'. Devolve (veredito, resto)."""
    linhas = texto.strip().splitlines()
    if linhas and linhas[0].upper().startswith("VEREDITO"):
        v = linhas[0].split(":", 1)[-1].strip().upper().replace(" ", "_")
        resto = "\n".join(linhas[1:]).strip()
        return (v if v in VEREDITOS else "PARCIAL"), resto
    return "PARCIAL", texto.strip()


def montar_contexto(c: Consulta, evid: list[Evidencia], info: dict) -> str:
    rec = info["recorte"]
    linhas = ["RECORTE"]
    filtros = "; ".join(c.explicacao) if c.explicacao else "nenhum (toda a base)"
    linhas.append(f"Filtros aplicados: {filtros}")
    linhas.append(f"Avaliações com comentário no recorte: {rec['n']}")
    notas = ", ".join(f"nota {k}: {v}" for k, v in rec["notas"].items())
    linhas.append(f"Distribuição por nota: {notas}")
    linhas.append("Avaliações do recorte que citam cada tema (busca por palavra-chave, aproximada, uma avaliação pode contar em mais de um tema):")
    for tema, n in sorted(rec["temas"].items(), key=lambda x: -x[1]):
        if n:
            linhas.append(f"- {tema}: {n}")
    linhas.append("")
    linhas.append("EVIDÊNCIAS (avaliações recuperadas, da mais relevante para a menos)")
    for e in evid:
        atraso = ""
        if e.dias_atraso is not None:
            atraso = f", entrega {int(e.dias_atraso)} dias após o prazo" if e.dias_atraso > 0 else ", entregue no prazo"
        linhas.append(f"[{e.doc_id}] nota {e.nota}, {e.categoria}, compra em {e.ano_mes}{atraso}: {e.texto}")
    return "\n".join(linhas)


class Pipeline:
    def __init__(self):
        self.rec = Recuperador()

    def responder(self, pergunta: str, backend: str | None = None, k: int = cfg.K_FINAL) -> Resultado:
        c = interpretar(pergunta, self.rec.categorias_en)
        evid, info = self.rec.buscar(c, k=k)
        assunto = c.termos_do_assunto()
        cob, ausentes = self.rec.cobertura(assunto)
        tem_assunto = bool(tokenizar(assunto))
        p = portao(evid, info["n_recorte"], cob, ausentes, c.ano_fora_da_base, tem_assunto)
        recorte = info.get("recorte", {"n": 0})
        base = dict(
            pergunta=pergunta, filtros=c.explicacao, evidencias=[asdict(e) for e in evid],
            recorte=recorte, portao=p,
        )

        if not p["ok"]:
            msg = RECUSA[p["motivo"]].format(ausentes=", ".join(ausentes))
            return Resultado(**base, resposta=msg, chamou_modelo=False, veredito="BARRADA")

        contexto = montar_contexto(c, evid, info)
        bruto = gerar(pergunta, contexto, backend)
        veredito, texto = separar_veredito(bruto)
        if veredito == "SEM_SUPORTE":
            texto = RECUSA["sem_suporte"].format(motivo=texto)
        return Resultado(**base, resposta=texto, chamou_modelo=True, contexto=contexto, veredito=veredito)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    r = Pipeline().responder(" ".join(sys.argv[1:]))
    print(json.dumps(asdict(r), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
