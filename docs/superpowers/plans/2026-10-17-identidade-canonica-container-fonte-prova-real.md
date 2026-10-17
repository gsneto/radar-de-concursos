# Prova real — Fase 27: identidade canônica e piloto IBFC

Data: 2026-10-17. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` (schema v15).

## Suíte de testes

- Baseline observada (antes de implementar): **1120 testes, OK**.
- Final: **1185 testes, OK** (+65): `test_identity.py` (33), `test_ibfc_source.py` (21),
  `test_identity_api.py` (8), `test_document_store.py` (+1), `test_association.py` (+1),
  `test_exam_location.py` (+1).

## Diagnóstico comprovado (não presumido)

| Sintoma | Causa comprovada | Evidência |
|---|---|---|
| 10 documentos de órgãos diferentes no mesmo "concurso" | `DOU_COMPETITION_ID = "DOU-S3"` — a **seção** do diário é usada como identidade de certame | concurso `54568dbc…`: obs `DOU-S3`, 10 docs, 10 órgãos, **0 propostas** |
| Nenhuma métrica de certame confiável | containers não eram distinguíveis de certames | 593 concursos, sem coluna de natureza |
| Anexos oficiais não eram coletados | nenhuma fonte com identidade por certame integrada | 18 editais oficiais em 593 concursos |

## Reparação de identidade (banco real)

| Item | Antes | Depois |
|---|---|---|
| Concursos | 593 | **598** (597 certames + 1 container) |
| Container `DOU-S3` | tratado como certame | `estado_identidade='container_fonte'` |
| Observação `DOU-S3` | `tipo_identidade='certame'` | `tipo_identidade='secao_publicacao'` |
| Documentos em container | 10 vinculados ao "concurso" | 10, agora com associação **`pendente`** |
| Propostas no container | 0 | **0** (nunca existiram; nada foi apagado) |
| Associações suspeitas | 3 (após a regra antiga) | **0** com a regra por emissores |
| Plano de reparação na 2ª execução | — | **0 ações** (idempotente) |

Nenhum certame foi criado automaticamente. Nenhuma proposta foi removida. Documentos e versões
permaneceram intactos.

## Piloto IBFC (fonte oficial nova)

Ciclo real: `ibfc-piloto --apply --analyze`, estado `concluido`, sem erros.

| Métrica | Valor medido |
|---|---|
| Certames descobertos no catálogo | 9 (`/index/1` + `/index/abertos`) |
| Certames criados neste ciclo | **5** (`ibfc-485/490/496/497/498`) — limite `max_new_details=5` |
| Documentos registrados | **67** (14 em `anexos-r2`, 48 em `anexos.cdn`, 5 páginas de banca) |
| Versões baixadas | **19** |
| Propostas extraídas | **136**, todas com `ambiguity_reason` |
| Downloads bloqueados por `robots.txt` | **48** (`robots_disallow_anexos_cdn`) |
| Confirmações automáticas | **0** |

Distribuição por campo: `conteudo_topico` 123, `conteudo_disciplina` 7, `conteudo_secao` 3,
`exam_uf` 1, `exam_municipio` 1, `exam_location` 1.

Tipos documentais classificados: 34 `resultado`, 9 `edital_abertura`, 5 `retificacao`,
4 `convocacao`, 3 `comunicado`, 3 `homologacao`, 3 `outro`, 1 `edital_retificado`,
5 `pagina_banca`.

## Funil de cobertura (banco real)

| Etapa | Antes (F26) | Depois (F27) |
|---|---|---|
| Concursos (certames) | 593 | **597** |
| Com documento | 499 | **503** |
| Com edital oficial | 16 | **18** |
| Com propostas | 15 | **16** |
| Com campo confirmado | 0 | **0** (inalterado por desenho) |

Causas da lacuna nos 597 certames: `apenas_agregador` **477**, `sem_documento` **94**,
`extraido_ambiguo` **16**, `documento_oficial_sem_edital` **8**, `edital_sem_campos` 1,
`falha_extracao` 1.

Dimensões (denominador = 18 certames com edital): `cargos` 88,9%, `local_prova` **83,3%**,
`prazo_inscricao` 66,7%, `resultado_isencao` 61,1%, `retificacao` 55,6%,
`conteudo_programatico` **33,3%**, `vagas_imediatas` 50,0%, `edital_oficial` 3,6% (18/503).
`local_prova` caiu de 87,5% (14/16) para 83,3% (15/18) **porque o denominador cresceu**: um
certame a mais tem local, mas dois novos não têm. O número absoluto subiu de 14 para 15.

## Integridade e segurança

```
schema: v15 | integrity_check: ok | foreign_key_check: []
backups: .bak-20261017-113747, -120840, -130146, -131921, -141646, -143552 (todos ok)
reparação: dry-run 1 container/1 observação/10 associações; apply igual; 2ª execução 0
piloto: ciclo concluido, 0 erros, 48 downloads bloqueados por robôs
revisoes_campo / valores_atuais: 0 / 0
GET /api/concursos: [] (contrato v1 intacto, 18 campos)
```

Protocolo: `--config` explícito, dry-run primeiro, backup com `integrity_check`, comparação de
contagens antes/depois, backups preservados. `anexos.cdn.selecao.net.br` **não** foi baixado.

## Bug latente corrigido

`_FIELDS` não continha `exam_municipio`/`exam_uf`/`work_municipio`/`work_uf`. Qualquer documento
novo com local de prova faria `record_analysis` levantar `ValueError: escopo ou campo inválido` e
abortar a versão inteira. Corrigido e coberto por `PersistenceTest` em `test_exam_location.py`.

## Revisão independente

**1 crítico, 8 importantes, menores.** Todos os críticos e importantes corrigidos:

1. **Crítico** — `apply_repair` sobrescrevia decisão humana. Agora `repair_plan` só emite ação
   necessária e `apply_repair` só altera `pendente`.
2. Container aceito como alvo de associação — agora recusado (`ValueError`).
3. CLI `ibfc-piloto --apply` não passava `download_new_only` — corrigido.
4. Refresh do IBFC não atualizava `last_checked_at` — rotação ficaria congelada; corrigido.
5. `partial` não seguia a convenção do projeto — agora `bool(errors) and bool(candidates)`.
6. `association` acusava container — excluído, com `containers_fonte` no relatório.
7. Bloqueio de download invisível — `downloads_bloqueados` no resumo e no retorno do ciclo.
8. Regras `muitos_atos_sem_propostas`/`titulos_divergentes` davam falso positivo para um único
   órgão — agora exigem **≥2 emissores distintos**; banco real passou de 3 para 0 apontamentos.

Menores corrigidos: caminho rápido de migração v15 passou a validar a tabela nova (com teste de
regressão); `test_contrato_v1_intacto` confere os **18 nomes**; `/api/associacoes/fila` valida
`state`; IBFC reaproveita o HTML de catálogo já baixado pelo ciclo.

## Limitações honestas

- O piloto criou **5 de 9** certames descobertos: `max_new_details=5` por ciclo é deliberado. Os
  outros 4 entram nos próximos ciclos, sem ação manual.
- **48 de 62** anexos do IBFC estão no CDN com `Disallow: /`: foram registrados como documento
  (URL, título, tipo, data), mas **sem cópia local e sem versão**. Não há extração desses PDFs.
  Contornar o `robots.txt` foi explicitamente rejeitado.
- `edital_oficial` em 3,6% **não** significa 3,6% do país: o denominador são os 503 certames com
  algum documento. 94 certames não têm documento nenhum.
- As 136 propostas do IBFC são **candidatas ambíguas**: nenhuma foi confirmada, nenhuma entrou em
  `valores_atuais`. O ganho é de rastreabilidade, não de confirmação.
- Os 10 documentos do container DOU continuam sem certame: a associação exige evidência e revisão
  humana. O sistema agora **não finge** que eles pertencem a um concurso.
- O container é 1 no banco real porque apenas o DOU usa identidade de seção. A regra existe para
  qualquer fonte futura com o mesmo defeito.
