# Plano — Fase 38: matriz de elegibilidade por cargo e escopo indígena

Data: 2026-10-18. Base: `36db3fd` (Fase 37), 1.668 testes, schema v21.

## Etapas

1. **Auditoria de partida** — diretório, branch, HEAD, remotes, sincronização, suíte, backup
   via API de backup, `integrity_check`, `foreign_key_check`, snapshot com fuso, inspeção das
   rotas/tabelas e da tarefa agendada.
2. **Caso TJSC** — localizar propostas, documentos e versões; verificar quadro de vagas,
   requisito de Direito e prazos; comparar com a fonte armazenada.
3. **Quadro de vagas em texto** (`document_fields._inline_vacancy_proposals`) — parser
   posicional por cabeçalho, com guardas contra prosa, tópicos e células extras.
4. **Reprocessamento controlado** — aplicar o extrator novo apenas às versões cujo quadro
   passou a ser lido; idempotente, só acrescenta.
5. **Módulo de elegibilidade** (`radar/eligibility.py`) — estados exclusivos, escopo
   indígena, guardas de texto, atribuição de cargo único, filtros, contagens por dimensão.
6. **Destaques por elegibilidade** — só requisito sustentado; incompatível fora mesmo com
   vaga indígena; limite por concurso; motivo legível.
7. **Superfície** — 2 rotas aditivas (`/api/elegibilidade`, `/api/elegibilidade/destaques`),
   2 comandos CLI, seção "Matriz de elegibilidade" na carteira com filtros e destaques.
8. **Testes** — `tests/test_eligibility_f38.py` (34), incluindo o caso TJSC e as guardas do
   parser.
9. **Revisão independente**, correções, documentação, commit e push.

## Critérios de aceite

- Elegibilidade por cargo; nenhum estado transferido entre cargos.
- Reserva indígena com escopo declarado; quantidade do concurso não distribuída.
- "CR" e "-" não viram zero nem vaga imediata.
- Cargo incompatível por requisito expresso não aparece como elegível nem nos destaques.
- TJSC: `incompativel_por_requisito` + `cargo_imediata`, com evidência de página e trecho.
- Nenhuma decisão, revisão ou valor vigente criado.
- Contrato `GET /api/concursos` v1 inalterado.
- Suíte completa verde; schema inalterado (v21).

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Parser de texto gerar vaga falsa | âncora + modalidades + contagem de células + testes de prosa/tópicos |
| Atribuir requisito de outro cargo | escopo por rótulo; atribuição só com quadro de cargo único |
| Reserva do concurso virar vaga do cargo | estados `concurso_*` e `distribuido_por_cargo` |
| "Ambíguo" virar compatibilidade | guardas de requisito e de área |
| Reprocessamento duplicar | chave idempotente do `reprocess` |
| Base mudar no ciclo | snapshot com hora; releitura antes de decidir |
