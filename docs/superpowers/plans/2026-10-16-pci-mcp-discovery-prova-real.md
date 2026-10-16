# Prova real — descoberta complementar via PCI MCP

Data da execução: 2026-10-16. Banco **temporário** isolado (`%TEMP%\pci10-*`).

## Conexão e ferramentas

- Endpoint: `https://mcp.pciconcursos.com.br/mcp` (HTTPS). Transporte: **Streamable
  HTTP**, JSON-RPC 2.0, protocolo `2025-06-18`; `initialize` → `tools/list` →
  `tools/call`. `initialize`+`tools/list` em ~0,4 s.
- Ferramentas descobertas (5): `listar_concursos`, `pesquisar_concursos`,
  `buscar_por_cargo`, `buscar_por_cidade`, `buscar_apostilas` (**não usada**).

## Consultas executadas (conjunto versionado v1)

| Consulta | Estado | Resultados |
|---|---|---|
| `listar_concursos {}` | concluído | 466 |
| `buscar_por_cargo {"cargo":"analista de sistemas"}` | concluído | 16 |
| `buscar_por_cargo {"cargo":"técnico em informática"}` | concluído | 28 |
| `pesquisar_concursos {"termo":"sistemas de informação"}` | concluído | 46 |

Total observado: **556**; concursos únicos (por id PCI): **477**; 4/4 consultas OK.

## Persistência e idempotência

- Ciclo 1 (`max_new_concursos=25`): **25** concursos novos (demonstra o limite do ciclo).
- Ciclo 2 (`max_new_concursos=2000`): **452** novos → **477** concursos.
- Ciclo 3 (reexecução): **0** novos — **idempotente**; **0 URLs duplicadas**.
- Cada concurso: identidade própria (`competition_id = "pci-<id>"`, `source_url` = link
  da notícia) + documento de descoberta (kind `outro`, `issuer = "PCI Concursos
  (agregador)"`), com **metadados mínimos + proveniência** e sem propostas extraídas.
- Tabela v1 `concursos` **ausente** — a PCI não escreve o contrato v1.

Exemplos de descobertas (título | sha256 | bytes):

```
Câmara de Boituva                          | 9c927187e74a | 524
CRBio-01 - Conselho Regional de Biologia   | fd60f5299eba | 539
CGU - Controladoria-Geral da União         | 834ec8a9246d | 552
Marinha do Brasil - Comando do 7º Distrito | c5ef89308f0b | 561
```

## Métricas da amostra

- **Descoberta nova:** 477 concursos registrados pela PCI que não existiam no Radar.
- **Sobreposição:** 0 na base isolada da prova (não havia outras fontes). Em uso real
  é calculada contra DOU/FGV/v1 (título normalizado) como **pista**, sem fundir.
- **Enriquecimento/confirmação:** 0 — a resposta da PCI fornece o **link da notícia**,
  não o URL do edital oficial; a confirmação documental permanece pendente e exige
  documento oficial (etapa separada, com revisão humana).
- **Pendências:** todos os 477 candidatos (sem confirmação oficial nesta fase).
- **Qualidade operacional:** 4 consultas, 0 erros, 0 respostas vazias, 0 não
  interpretáveis; tempo do ciclo de drenagem ~14 s.

## Limitações observadas

- As ferramentas de concursos filtram por **inscrições abertas** — não cobrem
  previstos/encerrados.
- A PCI **não** fornece URL do edital oficial; a confirmação depende de outras fontes.
- Reexecutar o conjunto consulta a lista nacional de novo (necessário para detectar
  novidades); registros conhecidos não geram duplicatas.
- Aviso da própria PCI: plataforma colaborativa que "pode não cobrir todos os editais
  abertos"; usar como **complemento**.

## Reprodução

Script: `%TEMP%\opencode\proof10.py` (fora do repositório). Testes automatizados
(sem rede): `tests/test_pci_source.py`.
