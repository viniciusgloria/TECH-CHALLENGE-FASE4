"""Transformação da pergunta: normalização, filtros por metadado e temas.

Tudo por regra, sem chamar modelo. Assim a etapa é barata, determinística e dá
para explicar ao usuário exatamente o que foi filtrado (a pergunta volta
anotada com os filtros aplicados).
"""
import re
import unicodedata
from dataclasses import dataclass, field


def sem_acento(txt: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn")


def normalizar(txt: str) -> str:
    txt = re.sub(r"[^\w\s]", " ", sem_acento(txt.lower()))
    return re.sub(r"\s+", " ", txt).strip()


# tema -> expressões (já sem acento) que indicam o assunto no texto
TEMAS = {
    "prazo e atraso na entrega": r"atras|demor|prazo|nao chegou|ainda nao|aguardando|esperando|dias para chegar|previsao",
    "produto não recebido": r"nao recebi|nao chegou|nunca chegou|nao entreg|extravi|sumiu|ate hoje",
    "produto diferente ou errado": r"diferente|errad|nao e o que|nao corresponde|outro produto|cor diferente|modelo diferente|trocad",
    "defeito e qualidade": r"defeit|quebr|estragad|danificad|nao funciona|parou de funcionar|qualidade ruim|ma qualidade|rasgad|vazand|falha",
    "item faltando ou entrega parcial": r"faltou|faltando|incomplet|so chegou|chegou apenas|veio so|veio apenas|metade",
    "atendimento e vendedor": r"atendimento|vendedor|loja|sac|suporte|resposta|responder|contato|reembolso|devolu|estorno",
    "embalagem": r"embalag|caixa amassada|mal embalad|bem embalad",
    "preço e custo-benefício": r"preco|barato|caro|custo.?beneficio|valor|promocao|desconto",
    "entrega rápida (elogio)": r"rapid|antes do prazo|antes da data|super rapido|chegou cedo|dentro do prazo|no prazo",
    "qualidade (elogio)": r"otima qualidade|excelente|recomendo|perfeito|adorei|gostei|superou|maravilh|bom produto",
}

# palavras que ampliam a busca lexical (BM25) quando o tema aparece na pergunta
EXPANSAO = {
    "entrega": "entrega entregue prazo atraso atrasou demorou chegou correios transportadora",
    "atraso": "atraso atrasou atrasado demora demorou prazo",
    "qualidade": "qualidade defeito quebrado estragado material",
    "atendimento": "atendimento vendedor loja resposta suporte",
    "defeito": "defeito defeituoso quebrado danificado",
    "embalagem": "embalagem embalado caixa amassada",
    "preco": "preco valor barato caro custo",
}

ALIAS_CATEGORIAS = {
    "bed_bath_table": ["cama mesa e banho", "cama mesa banho", "cama e banho"],
    "health_beauty": ["saude e beleza", "beleza e saude", "beleza", "saude"],
    "sports_leisure": ["esporte", "lazer", "esportes"],
    "computers_accessories": ["informatica", "computadores", "acessorios de informatica"],
    "furniture_decor": ["moveis", "decoracao", "movel"],
    "watches_gifts": ["relogios", "relogio", "presentes"],
    "housewares": ["utilidades domesticas", "casa e utilidades"],
    "telephony": ["telefonia", "celular", "celulares", "telefone"],
    "auto": ["automotivo", "automotiva", "carro", "autopecas"],
    "garden_tools": ["jardim", "ferramentas de jardim", "ferramentas"],
    "toys": ["brinquedos", "brinquedo"],
    "perfumery": ["perfumaria", "perfume", "perfumes"],
    "baby": ["bebe", "bebes", "artigos para bebe"],
    "cool_stuff": ["coisas legais"],
    "electronics": ["eletronicos", "eletronico"],
    "stationery": ["papelaria"],
    "pet_shop": ["pet shop", "pets", "animais"],
    "books_general_interest": ["livros", "livro"],
    "consoles_games": ["games", "videogames", "consoles"],
    "home_appliances": ["eletrodomesticos", "eletrodomestico"],
    "fashion_bags_accessories": ["bolsas", "moda bolsas"],
    "luggage_accessories": ["malas", "bagagem"],
    "musical_instruments": ["instrumentos musicais"],
}

# A Olist espalha o mesmo assunto em várias categorias (home_appliances e home_appliances_2,
# por exemplo). Quem pergunta por "eletrodomésticos" quer todas elas.
GRUPOS_CATEGORIA = {
    "home_appliances": ["home_appliances", "home_appliances_2", "small_appliances",
                        "small_appliances_home_oven_and_coffee", "portateis_cozinha_e_preparadores_de_alimentos"],
    "furniture_decor": ["furniture_decor", "furniture_living_room", "furniture_bedroom",
                        "furniture_mattress_and_upholstery", "office_furniture", "kitchen_dining_laundry_garden_furniture"],
    "computers_accessories": ["computers_accessories", "computers", "pc_gamer", "tablets_printing_image"],
    "telephony": ["telephony", "fixed_telephony"],
    "books_general_interest": ["books_general_interest", "books_technical", "books_imported"],
    "baby": ["baby", "diapers_and_hygiene"],
}

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


# verbos e palavras de instrução: dizem o que o usuário quer fazer, não o assunto
PALAVRAS_DE_TAREFA = set("""reclamam reclamar reclama reclamacoes reclamacao queixa queixas queixam elogiam elogiar
elogia elogios dizem falam relatam relatos relato comentam comentar avaliam avaliar avaliacoes avaliacao citam
mencionam acham pensam aparecem aparecer existem existe principais quais quantos quanto mais menos clientes
cliente pessoal temas tema padroes padrao""".split())


@dataclass
class Consulta:
    original: str
    normalizada: str
    filtros: dict = field(default_factory=dict)
    explicacao: list = field(default_factory=list)
    texto_busca: str = ""      # vai para o embedding
    texto_lexical: str = ""    # vai para o BM25
    ano_fora_da_base: int | None = None
    termos_de_filtro: list = field(default_factory=list)   # trechos que viraram filtro de metadado

    def termos_do_assunto(self) -> str:
        """A pergunta sem os trechos de filtro e sem palavras de instrução.

        Categoria, mês, ano e nota são resolvidos por metadado e não precisam
        aparecer no texto das avaliações. O que sobra é o assunto de fato.
        """
        txt = f" {self.normalizada} "
        for t in self.termos_de_filtro:
            txt = txt.replace(f" {t} ", " ")
        palavras = [p for p in txt.split() if p not in PALAVRAS_DE_TAREFA]
        return " ".join(palavras)


def _ano_fora_da_base(norm: str) -> int | None:
    for a in re.findall(r"\b(19\d\d|20\d\d)\b", norm):
        if not 2016 <= int(a) <= 2018:
            return int(a)
    return None


def _periodo(norm: str, filtros: dict, expl: list, termos: list):
    m = re.search(r"(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+(?:de\s+)?(2016|2017|2018)", norm)
    if m:
        ano = int(m.group(2))
        filtros["ano_mes"] = f"{ano}-{MESES[m.group(1)]:02d}"
        expl.append(f"período: {m.group(1)} de {ano}")
        termos += [m.group(0), m.group(1), str(ano)]
        return
    a = re.search(r"\b(2016|2017|2018)\b", norm)
    if a:
        filtros["ano"] = int(a.group(1))
        expl.append(f"ano da compra: {a.group(1)}")
        termos.append(a.group(1))


def _nota(norm: str, filtros: dict, expl: list, termos: list):
    m = re.search(r"nota\s*(?:igual a\s*)?([1-5])\b", norm)
    if m:
        filtros["nota"] = (int(m.group(1)), int(m.group(1)))
        expl.append(f"nota igual a {m.group(1)}")
        termos += [m.group(0), "nota"]
        return
    m = re.search(r"(\d)\s*estrelas?", norm)
    if m and 1 <= int(m.group(1)) <= 5:
        n = int(m.group(1))
        filtros["nota"] = (n, n)
        expl.append(f"nota igual a {n}")
        termos.append(m.group(0))
        return
    if re.search(r"insatisf|nota baixa|notas baixas|detrator|nota 1 e 2", norm):
        filtros["nota"] = (1, 2)
        expl.append("nota 1 ou 2 (cliente insatisfeito)")
    elif re.search(r"nota alta|notas altas|promotor|bem avaliad|satisfeit", norm):
        filtros["nota"] = (4, 5)
        expl.append("nota 4 ou 5 (cliente satisfeito)")
    elif re.search(r"elogi|mais gostam|valoriz|positiv|adoram", norm):
        filtros["nota"] = (4, 5)
        expl.append("nota 4 ou 5 (a pergunta pede elogios)")
    elif re.search(r"reclama|problemas? (?:relatad|mais)|principais problemas|queixa", norm):
        filtros["nota"] = (1, 3)
        expl.append("nota 1 a 3 (a pergunta pede reclamações)")


def _categoria(norm: str, filtros: dict, expl: list, categorias_en: set, termos: list):
    for en, nomes in ALIAS_CATEGORIAS.items():
        if en not in categorias_en:
            continue
        achados = [n for n in nomes if re.search(rf"\b{re.escape(n)}\b", norm)]
        if achados:
            grupo = [g for g in GRUPOS_CATEGORIA.get(en, [en]) if g in categorias_en] or [en]
            filtros["categoria_en"] = grupo
            expl.append(f"categoria: {', '.join(grupo)}")
            termos += achados   # "esporte e lazer": os dois nomes saem da conta de vocabulário
            return


def _atraso(norm: str, filtros: dict, expl: list):
    if re.search(r"(chegaram|chegou|entregues?|entregue) (?:com )?atras|pedidos? atrasad|entregas? atrasad|com atraso", norm):
        filtros["atrasou"] = 1
        expl.append("pedidos que chegaram depois da data estimada")


def interpretar(pergunta: str, categorias_en: set | None = None) -> Consulta:
    norm = normalizar(pergunta)
    c = Consulta(original=pergunta, normalizada=norm)
    _nota(norm, c.filtros, c.explicacao, c.termos_de_filtro)
    _periodo(norm, c.filtros, c.explicacao, c.termos_de_filtro)
    c.ano_fora_da_base = _ano_fora_da_base(norm)
    _atraso(norm, c.filtros, c.explicacao)
    _categoria(norm, c.filtros, c.explicacao, categorias_en or set(ALIAS_CATEGORIAS), c.termos_de_filtro)

    c.texto_busca = pergunta.strip()
    extras = [v for k, v in EXPANSAO.items() if k in norm]
    c.texto_lexical = " ".join([norm] + extras)
    return c
