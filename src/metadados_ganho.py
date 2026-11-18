"""Mede o que os filtros por metadado acrescentam à recuperação.

Para cada pergunta das avaliações que gera filtro (nota, período, categoria,
atraso), roda a recuperação duas vezes: com o filtro e sem ele (só o texto da
pergunta). Conta quantas das evidências respeitam o recorte que a pergunta pediu.

Uso: python src/metadados_ganho.py
"""
import copy

import numpy as np

import config as cfg
from avaliacao import CONJUNTOS
from consulta import interpretar
from recuperacao import Recuperador


def main():
    rec = Recuperador()
    linhas = []
    for conjunto, (dentro, _) in CONJUNTOS.items():
        for pergunta, _ in dentro:
            c = interpretar(pergunta, rec.categorias_en)
            if not c.filtros:
                continue
            permitido = set(rec.df.loc[rec.mascara(c.filtros), "doc_id"])
            com, _ = rec.buscar(c)
            sem_c = copy.deepcopy(c)
            sem_c.filtros = {}
            sem, _ = rec.buscar(sem_c)
            linhas.append({
                "pergunta": pergunta,
                "filtros": "; ".join(c.explicacao),
                "com": np.mean([e.doc_id in permitido for e in com]) if com else 0.0,
                "sem": np.mean([e.doc_id in permitido for e in sem]) if sem else 0.0,
            })
            print(f"{linhas[-1]['sem']:.2f} -> {linhas[-1]['com']:.2f} | {pergunta[:70]}", flush=True)

    media_sem = np.mean([l["sem"] for l in linhas])
    media_com = np.mean([l["com"] for l in linhas])
    md = [
        "# Ganho dos filtros por metadado",
        "",
        f"{len(linhas)} perguntas que geram filtro. Para cada uma, a fração das {cfg.K_FINAL} evidências",
        "que respeita o recorte pedido (nota, período, categoria ou atraso), com e sem o filtro.",
        "",
        f"Média sem filtro: **{media_sem:.0%}**. Com filtro: **{media_com:.0%}**.",
        "",
        "| Pergunta | Filtros | Sem filtro | Com filtro |",
        "|---|---|---:|---:|",
    ]
    for l in linhas:
        md.append(f"| {l['pergunta']} | {l['filtros']} | {l['sem']:.0%} | {l['com']:.0%} |")
    (cfg.REPORTS / "metadados_ganho.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nmédia sem filtro {media_sem:.2f} | com filtro {media_com:.2f}")


if __name__ == "__main__":
    main()
