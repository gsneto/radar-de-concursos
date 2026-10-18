# Plano — Fase 40: contexto da reserva indígena e zero publicado

Data: 2026-10-18. Base `7ad7171` (F39), schema v21, 1.748 testes verdes.

## Objetivo

Separar três situações que a F39 tratava com um rótulo só: zero imediato publicado com
reserva quantificada, reserva sem quantidade extraída e menção lexical que não é reserva.
Nenhuma quantidade nova é inferida.

## Passos

1. **Módulo de contexto** — criar `radar/indigenous_scope.py` com
   `mention_context(text, title)` e `MENTION_CONTEXTS`/`MENTION_CONTEXT_LABELS`.
   Janela de ±220 caracteres por ocorrência; prioridade reserva exclusiva > combinada >
   demais contextos; percentual só conta se não houver outro grupo entre o número e
   "indígena"; ano de lei entre parênteses não é percentual.
2. **Matriz** — em `radar/eligibility.py`:
   - novo estado `cargo_zero_imediato_com_reserva` quando há vaga imediata com valor 0 e
     reserva positiva;
   - `cargo_sem_imediata_com_reserva` fica para reserva publicada sem coluna de vaga
     imediata;
   - `reserva_combinada_com_outros_grupos` para regra combinada;
   - `mencao_fora_do_escopo_de_reserva` para menção sem regra;
   - `mencao_sem_quantidade` só para regra de reserva sem quantidade extraída;
   - `_reason` e `highlights` com motivo por estado; versão `eligibility_v3`.
3. **Carteira** — `radar/decisive_fields.py` usa o mesmo classificador e ganha os dois
   estados novos; `radar/portfolio.py` inclui combinada nas lacunas, retira menção fora de
   reserva e define a próxima ação da combinada.
4. **UI** — filtros de escopo indígena (matriz) e de carteira com os estados novos.
5. **Testes** — `tests/test_indigenous_scope_f40.py`:
   - classificação de 9 contextos, incluindo syllabus com "negros e indígenas" e ano de lei;
   - zero publicado com reserva;
   - reserva do cargo sem coluna imediata;
   - coluna combinada (matriz e carteira);
   - menção fora de reserva (matriz e carteira);
   - regra sem quantidade extraída;
   - versão e denominador;
   - filtro aceita estado novo e rejeita inventado.
6. **Documentação** — design, pesquisa, plano e prova real; registro no log autônomo.
7. **Verificação** — suíte completa; conferência na base real; revisão independente;
   commit e push na branch de trabalho.

## Critérios de aceite

- Os 55 cargos Quadrix deixam de aparecer como lacuna e aparecem como
  `cargo_zero_imediato_com_reserva`.
- Nenhum concurso com menção apenas lexical (RANI, vestuário, conteúdo, heteroidentificação)
  aparece como `mencao_sem_quantidade`.
- SEPLAG-RJ e MPRJ aparecem como `reserva_combinada_com_outros_grupos`, sem número indígena
  derivado.
- Nenhuma proposta, valor atual ou decisão humana é criada, alterada ou apagada.
- Suíte completa verde; contrato de `GET /api/concursos` inalterado.

## Fora de escopo

- Parser do Anexo II da SEDUC-PA.
- Extração de `CR*` e de "1 vaga para indígenas".
- Rateio de coluna combinada ou de total agregado.
- Migração de schema.
