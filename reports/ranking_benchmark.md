# Benchmark de ranking

20 perguntas, top-10, relevância por pooling.
Diversidade = 1 menos a similaridade média entre os pares do top-10 (maior = evidências mais variadas).

| Variante | P@10 (nota ≥1) | P@10 (nota 2) | nDCG@10 | MRR | Diversidade |
|---|---:|---:|---:|---:|---:|
| híbrido bge-m3 + rerank | 0.940 | 0.685 | 0.788 | 0.842 | 0.252 |
| híbrido bge-m3 | 0.950 | 0.665 | 0.778 | 0.832 | 0.250 |
| híbrido e5 + rerank | 0.930 | 0.670 | 0.771 | 0.847 | 0.289 |
| híbrido e5 | 0.890 | 0.655 | 0.736 | 0.797 | 0.327 |
| denso bge-m3 | 0.915 | 0.625 | 0.723 | 0.806 | 0.219 |
| denso e5 | 0.855 | 0.610 | 0.710 | 0.863 | 0.303 |
| híbrido bge-m3 + rerank + MMR λ=0.8 | 0.845 | 0.570 | 0.672 | 0.850 | 0.348 |
| híbrido bge-m3 + rerank + MMR λ=0.9 | 0.835 | 0.570 | 0.672 | 0.847 | 0.337 |
| bm25 | 0.810 | 0.600 | 0.656 | 0.678 | 0.316 |
| híbrido e5 + MMR (versão inicial) | 0.815 | 0.465 | 0.606 | 0.864 | 0.382 |
