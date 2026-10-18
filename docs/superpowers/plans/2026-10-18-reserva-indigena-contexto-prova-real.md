# Prova real — Fase 40

Data: 2026-10-18. Base: `data/radar.sqlite3` (schema v21). Branch `radar-configuracao`.

## Antes

- `git status`: árvore limpa, HEAD `7ad7171` (F39), sincronizada com o remoto.
- Suíte: 1.748 testes, 1 skip, OK.
- Backup: `data/radar.sqlite3.bak-20261018-183310` (61.856 KB, v21, `integrity ok`).
- Base: 1.232 documentos, 1.055 versões, 7.648 propostas, 0 revisões, 0 valores atuais,
  0 reconciliações, 11 revalidações, 125 cargos de identidade, 634 certames.

## Depois

- Suíte: **1.775 testes**, 1 skip, OK (`RESULT OK`).
- `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: vazio.
- 1.232 documentos, **1.072 versões** (+17 do ciclo agendado em andamento, não desta fase),
  7.648 propostas (inalteradas), 0 revisões, 0 valores atuais, 0 reconciliações,
  11 revalidações.
- Nenhuma proposta, decisão humana ou valor atual foi criado, alterado ou apagado.

## Matriz por cargo (159 cargos)

| Estado indígena | Cargos |
|---|---|
| `mencao_fora_do_escopo_de_reserva` | 83 |
| `cargo_zero_imediato_com_reserva` | 55 |
| `distribuido_por_cargo` | 9 |
| `mencao_sem_quantidade` | 3 |
| `cargo_explicito_zero` | 3 |
| `ausente_no_documento` | 2 |
| `reserva_combinada_com_outros_grupos` | 3 |
| `cargo_imediata` | 1 |

Elegibilidade (inalterada, como esperado — a fase não mexe em requisito):
61 `incompativel_por_requisito`, 51 `identidade_pendente`, 28 `informacao_insuficiente`,
16 `compativel_por_nivel_minimo`, 2 `compativel_sem_vaga_indigena`,
1 `compativel_por_interpretacao`.

## Concursos conferidos um a um

| Concurso | Antes | Depois | Evidência |
|---|---|---|---|
| `4bcc186d` (Quadrix 3049) | `cargo_sem_imediata_com_reserva` | `cargo_zero_imediato_com_reserva` | linha `207 … 1 - - - - 25 2 10 1 1 40` |
| `c268e937` (3053) | idem | idem | tabela com `-` em vagas efetivas e reserva > 0 |
| `e4271152` (3052) | idem | idem | idem |
| `d494705a` (3072) | idem | idem | idem |
| `6ae3cd17` (3070) | idem | idem | idem |
| `e3c874e0` (3071) | idem | idem | idem |
| `2a04e7e4` (SEPLAG-RJ) | `mencao_sem_quantidade` | `reserva_combinada_com_outros_grupos` | `20% … negros (pretos e pardos) ou indígenas`; legenda `N/I: Candidatos negros e indígenas`; tabela por cargo com coluna N/I |
| `14c68b75` (MPRJ) | `mencao_sem_quantidade` | `reserva_combinada_com_outros_grupos` | reserva combinada de negros e indígenas |
| `4b5579c4` (TJAP) | `mencao_sem_quantidade` | `mencao_sem_quantidade` | `CR*` para indígenas: reserva sem quantidade |
| `7c54d7df` (TJRS) | `mencao_sem_quantidade` | `mencao_sem_quantidade` | `3% … aos indígenas`; quantidade não extraída |
| `8e229b08` (IBFC) | `mencao_sem_quantidade` | `reserva_combinada_com_outros_grupos` | `reservadas às pessoas negras e às pessoas indígenas … 20%` |
| `f4235e23` (SEDUC-PA) | `mencao_sem_quantidade` | `mencao_sem_quantidade` | Anexo II p. 63–83 com colunas `PI`, `PPIQ`, `PI/PQ`; extração por cargo pendente |
| `prefsjceducacao25`, `quadrix-3056/3057/3069/3073`, `ibfc-490`, `mprjpromotor2026` (menções) | `mencao_sem_quantidade` | `mencao_fora_do_escopo_de_reserva` | RANI, vestuário, conteúdo programático, heteroidentificação |

## Carteira (634 concursos)

12 `mencao_fora_do_escopo_de_reserva`, 3 `mencao_sem_quantidade`,
3 `reserva_combinada_com_outros_grupos`, 6 `apenas_reserva`,
2 `explicito_sem_vaga_imediata`, 1 `explicito_imediato`, 3 `nao_mencionado`,
604 `nao_pesquisado`.

## Testes novos (27)

`tests/test_indigenous_scope_f40.py`:

- 9 de classificação de contexto (RANI, vestuário, conteúdo, heteroidentificação,
  percentual exclusivo, percentual combinado, reserva sem percentual, syllabus com
  "negros e indígenas", ano de lei entre parênteses);
- zero publicado com reserva (estado, âmbito e motivo);
- reserva do cargo sem coluna imediata;
- coluna combinada na matriz e na carteira;
- menção fora de reserva na matriz e na carteira;
- regra sem quantidade extraída;
- versão `eligibility_v3` e denominador;
- filtro aceita o estado novo e rejeita estado inventado;
- texto sem acento não trava a classificação (regressão de laço infinito);
- legenda `N/I` é coluna combinada;
- linha do concurso não usa rótulo de cargo;
- página de conteúdo antes da regra não esconde a reserva.

## Pendências registradas

- Parser do Anexo II da SEDUC-PA (linha com `AC PcD PP PI PQ PPIQ PI/PQ Total`, validando
  que a soma das sete primeiras colunas fecha o total).
- Extração de `CR*` (TJAP) e de "1 (uma) vaga para indígenas" (TJRS).
- Nenhum rateio de coluna combinada, percentual ou total agregado.
