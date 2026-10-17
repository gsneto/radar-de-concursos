# Prova real — Fase 28: revisão humana, confirmação e recuperação documental

Data: 2026-10-17. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` (schema v16).

## Suíte de testes

- Baseline observada (antes de implementar): **1185 testes, OK**.
- Final: **1255 testes, OK** (+70): `test_review.py` (34), `test_review_api.py` (16),
  `test_document_ingest.py` (15), `test_document_store.py` (+2), `test_identity.py` (+1),
  `test_ui.py` (+2).

## Diagnóstico comprovado

| Sintoma | Causa comprovada |
|---|---|
| 2023 propostas e **0 revisões** | revisão só por CLI, uma proposta por vez; sem fila, prioridade ou lote |
| 10 associações pendentes sem tela | rota existia; nenhuma experiência de comparação/decisão |
| 48 anexos sem byte | CDN com `robots.txt` `Disallow: /`; sem estado por documento nem caminho manual |
| Nenhuma importação validada | exportação/importação de decisões não existia |

## Estado da base

| Momento | Concursos | Documentos | Versões | Propostas | Revisões | Valores |
|---|---|---|---|---|---|---|
| Início da fase (v15) | 598 | 703 | 655 | 2023 | 0 | 0 |
| Após migração v16 | 598 | 703 | 655 | 2023 | 0 | 0 |
| Após ciclo agendado (externo) | **635** | **789** | **741** | **3608** | 0 | 0 |

A migração v16 teve **delta zero** em todas as tabelas históricas (comparação antes/depois).
O crescimento posterior veio do **ciclo operacional agendado do Windows** (“Radar de Concursos —
Ciclo”), que rodou durante a fase (20:19:58–20:22:05 UTC) e terminou `parcial` porque o DOU
falhou na fonte; nenhum erro de código foi registrado. Esse ciclo já usou o schema v16 e gravou
versões e propostas normalmente — validação real da migração em produção local.

## Associações

| Estado | Quantidade |
|---|---|
| `pendente` | **10** |
| `confirmada` | 0 |
| `rejeitada` | 0 |

As 10 pendências são documentos do DOU (container `DOU-S3`) e **já carregam justificativa de
pendência** na evidência: motivo (`identificador externo de fonte não identifica certame`),
identificador da fonte, órgão, ato, data e grupo candidato. Nenhuma confirmação foi inventada.

A tela permite confirmar (exige id do certame + justificativa), rejeitar (sem destino) e manter
pendente (registra justificativa). Confirmar **não** valida campos: teste
`test_confirmar_associacao_nao_valida_propostas` prova 0 revisões e 0 valores após confirmar.

## Fila de revisão

| Métrica | Valor |
|---|---|
| Propostas pendentes na fila | **3608** |
| Com conflito ativo (só propostas abertas) | **3342** |
| Grupos de conflito (concurso+cargo+campo) | **96** |
| Concursos com propostas | 19 |
| Tempo de consulta (limite 5, base real) | ~308 ms |

Topo da fila (determinístico): `exam_location = a_divulgar` (prioridade 12),
`exam_location = Florianópolis/SC` (12), `registration_end` com prazo próximo (12). Fatores
visíveis: edital oficial (+2), prazo em 30 dias (+3), campo decisivo (+3), conflito (+2),
documento mais recente (+1), evidência curta (+1).

## Decisões humanas na base real

**Nenhuma.** Por desenho, a fase entrega a ferramenta e não fabrica revisão: 0 revisões e 0
valores vigentes continuam sendo o estado honesto. A decisão, o lote, a seleção, a associação e a
ingestão manual foram exercitados **em cópia isolada** (`ui-f28.sqlite3`) pela interface real:

- decisão `validado` gravada com revisor `operador local`, origem `interface`, estado anterior
  nulo, justificativa e `evidence_sha256`;
- lote aberto com 10 itens, pausado/retomado, progresso preservado;
- associação “manter pendente” gravada com justificativa (append-only: 11 linhas, histórico
  anterior intacto);
- ingestão manual de PDF: validação (assinatura, 68 bytes, sha256) → confirmação → versão +
  `ingestoes_documentais` + evento; **0** propostas/revisões criadas.

## Anexos IBFC bloqueados

| Item | Valor |
|---|---|
| Documentos no CDN bloqueado | **48** |
| Com versão baixada | **0** |
| Eventos `download_bloqueado` | **48** (idempotentes) |
| Importados manualmente na base real | 0 |
| Estado no relatório | `bloqueado: 48` + `obtido: 741` |

Evidência registrada: `robots.txt` do CDN (`User-agent: *` / `Disallow: /`), URL do robots,
regra e data da verificação. **Nenhuma tentativa de contornar** o bloqueio: sem proxy, sem
user-agent alternativo, sem navegador e sem cópia de terceiro.

Alternativas verificadas:

1. **Espelho por caminho**: os 35 links do CDN e os 13 do r2 do certame 485 têm slugs diferentes
   — não há espelho. A verificação é por igualdade exata de caminho **e** host autorizado.
2. **Portal do órgão**: pesquisa real localizou a página oficial de editais do TJPE
   (`portal.tjpe.jus.br/web/concursos-e-selecoes/editais`), com o edital de abertura em PDF. É
   alternativa legítima, mas a identidade do documento exige conferência humana (o mesmo título
   aparece em certames distintos) — por isso não há ingestão automática.
3. **Diário Oficial**: fonte oficial já integrada; serve como pista de pesquisa, não como
   casamento automático.
4. **Importação manual**: disponível na tela e no CLI, com procedência e hash.

## Integridade e segurança

```
backup: radar.sqlite3.bak-20261017-163128 | integrity: ok | fk: 0 | v15
migração: v16 | integrity: ok | fk: 0 | delta histórico: 0
backfill: 48 eventos de bloqueio, 0 versões, 0 downloads
base final: integrity ok | fk 0 | 10 associações pendentes | 0 revisões | 0 valores
GET /api/concursos: contrato v1 com 18 campos
```

## Revisão independente

**1 crítico, 7 importantes, menores.** Todos os críticos e importantes corrigidos, cada um com
teste de regressão:

1. **Crítico** — proposta rejeitada/superada aparecia como “Valor vigente”: `selected` contava
   qualquer seleção histórica. Agora só a seleção **ativa** do escopo conta, e só com a última
   decisão `validado`. Testes: rejeitar após selecionar; selecionar A e B → só B vigente.
2. `select_current_value` desempatava por `id` (UUID) e podia aceitar proposta rejeitada com
   `reviewed_at` igual; passou a usar `rowid` (ordem de inserção), como o resto do módulo.
3. Conflito e prazo consideravam propostas já decididas, gerando prioridade falsa permanente.
   Agora só propostas **abertas** entram em conflito e em prazo.
4. O botão “Rejeitar vínculo” sempre falhava (400): rejeição sem destino é válida e passou a ser
   aceita; teste de API cobre o payload real.
5. Importação aceitava duas decisões contraditórias para a mesma proposta e não era atômica.
   Agora há deduplicação por proposta, validação de todos os itens antes de gravar e transação
   única com rollback; teste força erro no segundo item e confirma que nada foi aplicado.
6. Alternativa era rotulada “host autorizado” sem verificar autorização. Agora verifica
   `allowed_document_url`; host não autorizado vira tipo distinto.
7. Correção repetida com justificativa diferente duplicava a proposta derivada. Agora reusa a
   derivada existente (mesma evidência + campo + valor).

Menores corrigidos: filtro de lote validado; `documento_mais_recente` só com data real; teste de
container com id real; importação aceita item adiado; rótulo do filtro; origem derivada da rota;
lote retomável após reload (localStorage); ingestão grava o hash da versão efetivamente criada;
evento de bloqueio em uma única transação.

## Limitações honestas

- **Nenhuma proposta foi confirmada na base real.** O ganho é operacional: fila, evidência,
  prioridade e auditoria prontas; a decisão continua humana.
- O ciclo agendado **não inclui o IBFC** (`radar_ops.json` tem `guajara`, `dou`, `fgv`,
  `quadrix`, `pci`). Ativar o piloto na operação periódica é uma decisão de configuração do
  usuário, não aplicada silenciosamente.
- A fila calcula a prioridade em memória (3608 propostas ≈ 308 ms). Para dezenas de milhares,
  será necessário cache ou cálculo incremental.
- `ingestoes_documentais.review_state` é gravado como `pendente` e não é atualizado por uma
  revisão do documento; a coluna documenta o estado da ingestão, não substitui a revisão.
- Os 48 anexos do CDN continuam sem texto extraído: a extração depende de obtenção legítima
  (portal do órgão ou arquivo fornecido pelo usuário).
