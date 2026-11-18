# Avaliação do pipeline (avaliacao_calibracao)

| Métrica | Resultado |
|---|---|
| Perguntas dentro do escopo respondidas | 20/20 (100%) |
| Perguntas fora do escopo recusadas | 14/15 (93%) |
| Fora do escopo barradas antes do modelo (portão) | 11/15 (73%) |
| Respostas com ao menos uma citação | 20/20 (100%) |
| Respostas em que todo id citado foi recuperado | 20/20 (100%) |
| Perguntas que falharam na chamada ao modelo (fora das métricas) | 0 |

## Dentro do escopo

| Pergunta | Filtros | Veredito |
|---|---|---|
| Quais são os principais problemas relatados pelos clientes em suas avaliações? | nota 1 a 3 (a pergunta pede reclamações) | SUPORTADA |
| O que os clientes relatam sobre problemas relacionados à entrega? | - | SUPORTADA |
| Quais aspectos da experiência de compra são mais elogiados pelos clientes? | nota 4 ou 5 (a pergunta pede elogios) | PARCIAL |
| Quais padrões podem ser identificados nas avaliações de clientes insatisfeitos? | nota 1 ou 2 (cliente insatisfeito) | PARCIAL |
| Quais avaliações sustentam a conclusão de que existem problemas recorrentes relacionados ao prazo de entrega? | - | SUPORTADA |
| Os clientes reclamam de produto diferente do que foi anunciado? | nota 1 a 3 (a pergunta pede reclamações) | SUPORTADA |
| Há reclamações sobre embalagem danificada ou mal feita? | nota 1 a 3 (a pergunta pede reclamações) | PARCIAL |
| O que dizem sobre produtos que chegaram quebrados ou com defeito? | - | SUPORTADA |
| Como os clientes avaliam o atendimento dos vendedores? | - | PARCIAL |
| Há relatos de pedidos que chegaram incompletos, com itens faltando? | - | SUPORTADA |
| Os clientes comentam sobre o preço e o custo-benefício? | - | SUPORTADA |
| Há clientes que dizem que nunca receberam o produto? | - | SUPORTADA |
| Quais são os principais problemas relatados nas avaliações com nota baixa? | nota 1 ou 2 (cliente insatisfeito) | PARCIAL |
| O que os clientes mais elogiam em produtos de cama, mesa e banho? | nota 4 ou 5 (a pergunta pede elogios); categoria: bed_bath_table | SUPORTADA |
| Quais reclamações aparecem nas compras de informática? | nota 1 a 3 (a pergunta pede reclamações); categoria: computers_accessories, computers, pc_gamer, tablets_printing_image | SUPORTADA |
| Quais temas aparecem nas avaliações de pedidos que chegaram com atraso? | pedidos que chegaram depois da data estimada | PARCIAL |
| O que os clientes relatam sobre as compras feitas em 2017? | ano da compra: 2017 | PARCIAL |
| Quais problemas aparecem nas avaliações de brinquedos? | categoria: toys | PARCIAL |
| O que os clientes de telefonia dizem sobre a entrega? | categoria: telephony, fixed_telephony | SUPORTADA |
| Quais elogios aparecem nas avaliações de perfumaria? | nota 4 ou 5 (a pergunta pede elogios); categoria: perfumery | SUPORTADA |

## Fora do escopo

| Pergunta | Veredito | Cobertura de vocabulário |
|---|---|---|
| Qual o preço do iPhone 15 na Amazon? | BARRADA | 1.0 |
| Quem ganhou a Copa do Mundo de 2018? | BARRADA | 1.0 |
| Como fazer bolo de cenoura? | BARRADA | 0.67 |
| Qual a capital da França? | BARRADA | 0.5 |
| Qual será o faturamento da Olist em 2025? | BARRADA | 0.67 |
| Quantos funcionários a Olist tem hoje? | BARRADA | 0.67 |
| O que os clientes acham do Mercado Livre? | PARCIAL | 1.0 |
| Quais são as melhores lojas da Shopee? | SEM_SUPORTE | 0.75 |
| Explique como funciona um modelo de linguagem. | BARRADA | 0.5 |
| Qual a previsão do tempo para amanhã em São Paulo? | BARRADA | 1.0 |
| Qual o telefone do suporte da Olist? | BARRADA | 0.5 |
| Os clientes elogiam o serviço de assinatura de streaming? | SEM_SUPORTE | 0.67 |
| O que os clientes dizem sobre a entrega por drone? | SEM_SUPORTE | 1.0 |
| Quais são as avaliações de clientes de 2020? | BARRADA | 1.0 |
| Escreva um poema sobre o mar. | BARRADA | 0.0 |
