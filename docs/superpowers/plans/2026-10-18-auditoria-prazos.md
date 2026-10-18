# Plano — Fase 37: auditoria de prazos, contagens e ficha de decisão

Data: 2026-10-18. Base: `9252d94` (Fase 36), 1.637 testes, schema v21.

## Etapas

1. **Auditoria de partida** — diretório, branch, HEAD, remotes, sincronização, suíte,
   backup via API de backup, `integrity_check`, `foreign_key_check`, snapshot com fuso,
   inspeção das rotas/tabelas e da tarefa agendada.
2. **Caso `4f495c42`** — propostas, versões, blocos, offsets, hashes, URL, contexto
   anterior/posterior, comparação com o documento oficial, ficha de decisão.
3. **Diagnóstico dos demais conflitos** — mesmo procedimento para `4b5579c4`, `637c7a90`,
   `7c54d7df`, `ddb0dac5`, `f4235e23`, `4a271ba4` e os demais.
4. **Reconciliação de contagens** — identificar por que 10+6+71+14 = 101 e separar
   dimensões (temporal, revalidação, conflito, revisão).
5. **Correção do contexto de extração** — janela curta + frase, classificação de evento
   compartilhada, sem alterar dados existentes.
6. **Módulo de auditoria** (`radar/deadline_audit.py`) — classificação por candidato, causa,
   ficha, proposta de correção, contagens por causa.
7. **Dimensões no calendário** — `por_temporal`, `por_revalidacao`, `por_conflito`,
   `por_revisao`, `denominador`, mantendo `por_estado` como alias.
8. **Verificação de versão específica** — `verify_version`, `dry_run` sem rede.
9. **Superfície** — 3 rotas aditivas, 3 comandos CLI, cabeçalho com dimensões, botão e painel
   de ficha do prazo.
10. **Testes** — `tests/test_deadline_audit_f37.py` (31), incluindo o caso real de três
    eventos no mesmo bloco, somas de dimensões, rejeitadas, `verify_version` e API.
11. **Auditorias de apoio** — 11 revalidações, 12 destaques, SI/indígena por escopo,
    287 nominais, mudanças do ciclo.
12. **Revisão independente**, correções, documentação, commit e push.

## Critérios de aceite

- A ficha mostra todos os candidatos com trecho, contexto, página, offsets, hash e URL.
- A causa é explicada; nenhum valor é escolhido automaticamente.
- `19/10/2026` do caso `4f495c42` é classificado como início de inscrição sustentado, não
  como inscrição aberta; a ficha não confirma o prazo.
- As quatro dimensões somam o total, individualmente.
- `fonte_inalterada` não aparece como estado temporal nem como confirmação.
- Nenhuma decisão, revisão ou valor vigente é criado.
- Contrato `GET /api/concursos` v1 inalterado.
- Suíte completa verde; base íntegra; schema inalterado (v21).

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Mudar a extração e alterar dados existentes | correção só vale para extrações futuras; dados atuais intactos |
| Janela curta gerar falso negativo | fallback para a frase; `sem_extrator`/`outro` sinalizado, nunca decidido |
| Auditoria "resolver" o conflito | proposta de correção marcada como não executada |
| Contagem voltar a divergir | teste que soma cada dimensão e compara com o total |
| Ciclo automático mudar a base no meio | snapshot com hora; identidade e versão reconferidas |
| Revalidação virar coleta massiva | só versão específica, política da fonte, limite de tamanho |
