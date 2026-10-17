# Prova real - Fase 22: conteúdo programático, perfil e preparação

Data: 2026-10-16. Python validado: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.

## Suíte de testes

- Baseline observada (antes de implementar): **751 testes, OK**.
- Final: **829 testes, OK** (78 novos). Novos: `test_program_content.py` (26),
  `test_preparation.py` (21), `test_study_backup.py` (17), `test_knowledge_api.py` (15),
  ampliação de `test_ui.py`. Ajuste: 5 asserções de versão de esquema (10 → 11).

## Migração da base habitual (v10 → v11)

Backup prévio via API do SQLite (consistente): `data/radar.sqlite3.bak-20261016-220648`
(integridade `ok`).

| Momento | integrity | user_version | concursos | documentos | alertas |
|---|---|---|---|---|---|
| antes | ok | 10 | 593 | 636 | 290 |
| depois | ok | 11 | 593 | 636 | 290 |

Tabela criada: `estudo_perfil`. Migração aditiva e idempotente.

## Prova funcional (cópia da base real)

Edital sintético realista (com "ANEXO I - CONTEÚDO PROGRAMÁTICO DAS PROVAS" e disciplinas
"1. LÍNGUA PORTUGUESA", "3. INFORMÁTICA") analisado com o extrator:

```
counts: {'extraido_nao_revisado': 6}  state: extraido_nao_revisado
 - LINGUA PORTUGUESA | Compreensao e interpretacao de textos
 - LINGUA PORTUGUESA | Ortografia oficial
 - RACIOCINIO LOGICO  | Estruturas logicas
 - INFORMATICA        | Redes de computadores
 - INFORMATICA        | Protocolos de comunicacao
 - INFORMATICA        | Banco de dados
```

Perfil + cobertura via CLI (`estudos-perfil`, `estudos-cobertura`):

```
pct: 33
basis: cobertura sobre 6 tópico(s) identificado(s) (0 confirmado(s) por revisão, 6 ainda não revisado(s))
perspectiva: exige_confirmacao - Exige confirmação   (formal: nao_extraido)
lacunas: ['Compreensao e interpretacao de textos', 'Estruturas logicas', 'Protocolos de comunicacao', 'Banco de dados']
```

Exportação / importação / backup (CLI):

```
estudos-exportar --out ... -> counts {perfil: 2, ...}
estudos-importar --dry-run -> ok True created 0 skipped 2 dry_run True
estudos-backup --dest ...  -> integrity ok
```

Round-trip em Python: `restore_database` → integridade `ok`, `perfil=2`; `import_study_data`
em banco novo → `created=2`, `skipped=0` (e `created=0` na repetição, idempotente).

HTTP (servidor loopback real, cópia da base):

```
GET /api/estudos/conteudo?contest_id=...  -> 200  counts=extraido_nao_revisado
GET /api/estudos/preparacao?contest_id=.. -> 200  pct=25
GET /api/estudos/perfil                   -> 200  n=2
GET /api/concursos                        -> 200  (v1 inalterada)
GET /api/prioridades?limit=2              -> 200  (sem regressão)
```

## Revisão independente (delegação via `task`/code-reviewer)

**0 críticos + 7 importantes + 12 menores**. Corrigidos:

- **Importantes:** (I1) `validate_export` passou a exigir campos obrigatórios por entidade e o
  servidor trata exceções inesperadas → 400 (sem derrubar a conexão); (I2) FKs ausentes na
  importação viram conflito (tópico-pai → raiz; sessão → sem vínculo) em vez de abortar; (I3) o
  tempo de sessão aberta é **materializado** ao finalizá-la na importação; (I4) `conteudo_*`
  excluído da detecção de conflito escalar em `/detalhes`; (I5) títulos com sufixo
  ("BÁSICOS E ESPECÍFICOS", "DAS PROVAS", "POR CARGO") reconhecidos; (I6) "RECURSOS" como
  disciplina não encerra a seção (exige "DOS RECURSOS"); (I7) "1. LÍNGUA PORTUGUESA" (maiúsculas)
  classificado como disciplina.
- **Menores:** hash da versão na evidência; rótulos de tabela ("TOTAL", "CARGO") não viram
  disciplina; resto após "DISCIPLINA:" vira tópico; marcador de seção truncada; backup recusa
  destino igual à origem; `perspective` ligada ao relatório; DELETE do perfil aguardado na UI;
  progresso por concurso contabilizado; `send_gap_to_study` restrito a conteúdo identificado.

Suíte após as correções: **829 testes, OK**; contrato v1 inalterado.

## Limitações honestas

- A extração é conservadora (precisão > cobertura); formatos incomuns ficam `nao_localizado`.
- A base real ainda não tem propostas de conteúdo (versões analisadas antes desta fase).
- Sem flashcards/questões nem sincronização entre dispositivos.
