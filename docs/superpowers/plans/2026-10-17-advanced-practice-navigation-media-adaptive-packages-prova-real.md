# Prova real — Fase 24: navegação, imagens, adaptativa e pacotes

Data: 2026-10-17. Python validado: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.

## Suíte de testes

- Baseline observada (antes de implementar): **912 testes, OK**.
- Final: **1004 testes, OK** (92 novos; 4 são reexecuções herdadas da subclasse de API, portanto
  1000 métodos únicos). Novos: `test_media.py` (14), `test_adaptive.py` (21), `test_packages.py` (29),
  `test_practice.py` (+17: navegação, mídia, adaptativa, schema v14, API), `test_ui.py` (+1 caso
  abrangendo mapa/marcação/retomada, imagem, modos e pacotes).
- Ajuste: 6 asserções de versão de esquema passaram a usar `SCHEMA_VERSION` (13 → 14).

## Revisão independente

Revisão por subagente com foco em segurança e honestidade dos dados. Resultado: **0 críticos**,
6 importantes, 11 menores. Todos os importantes foram corrigidos:

1. Janela de “erro recente” usava as tentativas mais antigas (ordem DESC da consulta) → agora o
   histórico ordena por data antes de cortar a janela; teste novo prova que os acertos recentes
   vencem os erros antigos.
2. Pacotes malformados derrubavam a conexão (`KeyError`/`ValueError`) → validador único
   `_validate_records` usado por prévia e importação; rotas devolvem 400 em JSON.
3. Flashcards com disciplina/tópico quebravam FK na importação → o pacote passou a levar as
   disciplinas/tópicos referenciados; vínculo ausente é removido com conflito reportado.
4. `dry_run` reportava mídia como ausente → ids de mídia são simulados no dry-run e o relatório
   conta corretamente, sem gravar arquivo nem linha.
5. Painel de pacotes mostrava zeros → `list_packages` expõe `questoes`, `flashcards`, `midias` e
   `tipo`; o front passou a ler `counts`.
6. Cobertura de segurança incompleta → testes novos para `nosniff`/`Content-Type`, limite de
   upload, limites de ZIP (membros e por membro), dry-run sem efeitos, migração v13→v14 com dados.

Menores corrigidos: posição de questão fora do intervalo agora é limitada; licença de imagem
validada; existência do cartão verificada antes de gravar arquivo; `tipo` validado na exportação;
rótulos de modo traduzidos; aviso de comparabilidade com `aria-live`; limite de tamanho no cliente.

## Migração da base habitual (v13 → v14)

Backup consistente via API do SQLite (integridade `ok`):
`data/radar.sqlite3.bak-20261017-113747` (pré-v14).

| Momento | integrity | user_version | concursos | documentos | alertas | propostas |
|---|---|---|---|---|---|---|
| antes (v13) | ok | 13 | 593 | 636 | 290 | 751 |
| depois (v14) | ok | 14 | 593 | 636 | 290 | 751 |

Tabelas novas confirmadas: `pratica_midias`, `pratica_pacotes`. Migração reexecutada é idempotente.

## Prova funcional (cópia da base real, v13 → v14)

```
copia v: 13
pos-migracao v: 14 integrity: ok
contagens: 593 636 290 751
imagem: image/png 12 x 8
adaptativa: adaptativa adaptive_v1 plano: 3
motivo: tópico ainda não praticado
resumo: 3 marcadas 1 brancos 3 atual 2
pacote: {'questoes': 4, 'flashcards': 1, 'midias': 1} | import: {'questoes': 4, 'flashcards': 1, 'midias': 1} | conflitos: 0
midia importada: image/png
historico: Prova real 4
final v: 14 integrity: ok
```

## Verificações de contrato

- `GET /api/concursos` manteve os 18 campos (teste `test_preferences_do_not_leak_into_v1` e
  comparação byte a byte em smoke HTTP).
- Nenhuma rota nova revela `gabarito` de prova em andamento: `resumo`, `questoes`, listagens e
  plano adaptativo testados por asserção explícita.
- `GET /api/estudos/midia/<id>` responde com `Content-Type` fixo e `X-Content-Type-Options:
  nosniff`; tentativa de traversal retorna 400/404.
- Pacote com `../`, caminho absoluto, UNC, unidade ou zip bomb é recusado antes de qualquer escrita.

## Limitações honestas

- A prática adaptativa é **heurística determinística** (`adaptive_v1`), não TRI/IRT: não estima
  nota nem probabilidade de aprovação, e o percentual de uma sessão adaptativa **não** é
  comparável ao de um simulado de conjunto fixo (informado na API e na UI).
- Upload de imagem usa base64 em JSON (o servidor não tem parser multipart), com limite de 8 MiB.
- SVG é recusado por poder carregar script; não há sanitizador de SVG no runtime.
- O histórico de pacotes é um log de auditoria: reimportar o mesmo arquivo não duplica conteúdo,
  mas registra nova linha de proveniência.
