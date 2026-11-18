"""Montagem do prompt e chamada do modelo de linguagem.

Três backends, escolhidos por LLM_BACKEND no .env:
  claude_cli  chama o Claude Code (`claude -p`), usa o login da assinatura
  openrouter  chama a API do OpenRouter
  manual      não chama nada, só grava o prompt em reports/prompts/
"""
import os
import subprocess
import tempfile
import time

import requests
from dotenv import load_dotenv

import config as cfg

load_dotenv(cfg.RAIZ / ".env")

SISTEMA = """Você analisa avaliações de clientes de um e-commerce brasileiro (base Olist, 2016 a 2018).
Responda em português do Brasil, em tom direto, para um gestor que quer entender o que os clientes dizem.

Regras:
1. Use somente as avaliações que aparecem no bloco EVIDÊNCIAS. Não use conhecimento externo sobre a Olist nem invente motivos.
2. Cada afirmação sobre o que os clientes relatam precisa citar o id da avaliação entre colchetes, um id por colchete, por exemplo [r012345] [r067890].
3. Não dê números ou proporções que não estejam no bloco RECORTE. Com as avaliações recuperadas você pode dizer que um tema aparece em várias delas, mas não que é "o mais comum" sem apoio numérico.
4. Se as evidências não respondem à pergunta, ou respondem só em parte, diga isso de forma explícita e responda apenas a parte que tem suporte.
5. Se a pergunta for sobre algo que não está nas avaliações (preço, concorrente, previsão, assunto sem relação), diga que a base não permite responder e pare aí.
6. Não repita as avaliações inteiras. Resuma os temas e cite os ids. Respostas curtas: até uns 200 palavras.

Formato obrigatório: a primeira linha da resposta é exatamente uma destas:
VEREDITO: SUPORTADA    (as evidências respondem bem à pergunta)
VEREDITO: PARCIAL      (respondem só em parte, ou a amostra é pequena para concluir)
VEREDITO: SEM_SUPORTE  (não respondem, ou a pergunta está fora do que a base cobre)
Depois da primeira linha vem a resposta. Se for SEM_SUPORTE, escreva só uma frase curta dizendo por que a base não responde, sem citar avaliações."""


def montar_prompt(pergunta: str, contexto: str) -> str:
    return f"{contexto}\n\nPERGUNTA: {pergunta}\n\nResponda seguindo as regras."


def _claude_cli(prompt: str) -> str:
    modelo = os.getenv("CLAUDE_MODELO", "sonnet")
    cmd = [
        "claude", "-p",
        "--model", modelo,
        "--tools", "",
        "--no-session-persistence",
        "--system-prompt", "Você é um analista de avaliações de clientes. Siga as regras que vêm no início da mensagem.",
        "--output-format", "text",
    ]
    # as regras vão pela entrada padrão: argumento multilinha quebra no cmd.exe do Windows
    entrada = f"{SISTEMA}\n\n---\n\n{prompt}"
    # roda numa pasta vazia para não carregar CLAUDE.md nem configurações de projeto.
    # Às vezes a chamada falha sem mensagem (instabilidade); tenta de novo com espera.
    erro = ""
    for tentativa, espera in enumerate((0, 10, 30)):
        time.sleep(espera)
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                cmd, input=entrada, capture_output=True, text=True, encoding="utf-8",
                cwd=tmp, timeout=180, shell=(os.name == "nt"),
            )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        erro = (r.stderr or r.stdout).strip()[:300]
    raise RuntimeError(f"claude -p falhou depois de 3 tentativas ({r.returncode}): {erro}")


def _openrouter(prompt: str) -> str:
    chave = os.getenv("OPENROUTER_API_KEY")
    if not chave:
        raise RuntimeError("OPENROUTER_API_KEY não definida no .env")
    modelo = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-5.5")
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {chave}"},
        json={
            "model": modelo,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SISTEMA},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _manual(prompt: str) -> str:
    pasta = cfg.REPORTS / "prompts"
    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / f"prompt_{int(time.time() * 1000)}.txt"
    arq.write_text(f"[SISTEMA]\n{SISTEMA}\n\n[USUARIO]\n{prompt}\n", encoding="utf-8")
    return f"(backend manual: prompt salvo em {arq.relative_to(cfg.RAIZ)})"


BACKENDS = {"claude_cli": _claude_cli, "openrouter": _openrouter, "manual": _manual}


def gerar(pergunta: str, contexto: str, backend: str | None = None) -> str:
    backend = backend or os.getenv("LLM_BACKEND", "claude_cli")
    if backend not in BACKENDS:
        raise ValueError(f"backend desconhecido: {backend}")
    return BACKENDS[backend](montar_prompt(pergunta, contexto))
