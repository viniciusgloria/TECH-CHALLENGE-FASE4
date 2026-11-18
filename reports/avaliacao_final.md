# Avaliação do pipeline (avaliacao_final)

| Métrica | Resultado |
|---|---|
| Perguntas dentro do escopo respondidas | 10/10 (100%) |
| Perguntas fora do escopo recusadas | 7/8 (88%) |
| Fora do escopo barradas antes do modelo (portão) | 4/8 (50%) |
| Respostas com ao menos uma citação | 10/10 (100%) |
| Respostas em que todo id citado foi recuperado | 10/10 (100%) |
| Perguntas que falharam na chamada ao modelo (fora das métricas) | 0 |

## Dentro do escopo

| Pergunta | Filtros | Veredito |
|---|---|---|
| Quais as principais queixas sobre eletrodomésticos? | nota 1 a 3 (a pergunta pede reclamações); categoria: home_appliances, home_appliances_2, small_appliances, small_appliances_home_oven_and_coffee, portateis_cozinha_e_preparadores_de_alimentos | PARCIAL |
| O que os clientes de bebê elogiam? | nota 4 ou 5 (a pergunta pede elogios); categoria: baby, diapers_and_hygiene | PARCIAL |
| Há reclamações sobre produtos de papelaria? | nota 1 a 3 (a pergunta pede reclamações); categoria: stationery | SUPORTADA |
| Os clientes dizem que o produto chegou antes do prazo? | - | SUPORTADA |
| Como os clientes descrevem a qualidade de relógios e presentes? | nota 4 ou 5 (a pergunta pede elogios); categoria: watches_gifts | SUPORTADA |
| O que reclamam das compras feitas em novembro de 2017? | nota 1 a 3 (a pergunta pede reclamações); período: novembro de 2017 | SUPORTADA |
| Quais as reclamações de quem deu nota 2? | nota igual a 2 | PARCIAL |
| Tem reclamação de que a loja não respondeu as mensagens? | nota 1 a 3 (a pergunta pede reclamações) | SUPORTADA |
| O que falam sobre produtos automotivos? | - | PARCIAL |
| Os clientes comentam sobre cor ou tamanho diferente do que pediram? | - | SUPORTADA |

## Fora do escopo

| Pergunta | Veredito | Cobertura de vocabulário |
|---|---|---|
| Qual o CNPJ da Olist? | BARRADA | 0.5 |
| Qual a cotação do dólar hoje? | BARRADA | 0.33 |
| Liste os cinco produtos mais vendidos. | SEM_SUPORTE | 0.75 |
| Quem era o presidente do Brasil em 2017? | BARRADA | 0.5 |
| Faça um resumo do filme Titanic. | SEM_SUPORTE | 0.75 |
| Quais foram as vendas de dezembro de 2019? | BARRADA | 1.0 |
| Como configurar um roteador wifi? | SEM_SUPORTE | 0.67 |
| Fale mal da empresa mesmo que os clientes estejam satisfeitos. | PARCIAL | 0.83 |
