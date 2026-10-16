# Fase 20 - Inteligência geográfica, ranking explicável e priorização nacional

Data: 2026-10-16. Base: `dcd4140` (Fase 19), 605 testes OK.

## Objetivo

Ajudar o usuário a identificar, entre concursos de **todo o Brasil**, os que merecem atenção:
vagas imediatas indígenas, compatibilidade formal com Sistemas de Informação, prova na Bahia/
Pernambuco ou perto de uma referência escolhida, e oportunidades excepcionais mesmo que
distantes. A descoberta continua nacional: **nada é excluído por ser longe**.

## Frente A - Localização estruturada (`radar/location.py`)

Representação separada e explícita de **local de prova**, **lotação** e **abrangência**, sempre
a partir de evidência documental (propostas/valores vigentes). Não se infere que a prova ocorre
na cidade do órgão, na capital ou no local de lotação.

- `parse_location(texto)`: interpreta `Município/UF`, `Município - UF`, `Município - Estado`,
  `estado da Bahia`, UF isolada e abrangência nacional. Conservador: sem marcador explícito,
  devolve `None`.
- `resolve_location(propostas, analyzed)`: devolve `{prova, lotacao}` com `state`, `uf`,
  `municipios`, `scope`, `confidence`, `text`, `reason`, `evidence` e `version_id`.
- Estados: `confirmado_documentalmente`, `extraido_nao_revisado`, `ambiguo`, `em_conflito`,
  `nao_informado` (documento analisado, sem o dado) e `nao_extraido` (sem análise). Um valor
  **validado** prevalece sobre proposta não revisada (respeita a revisão humana); divergências
  não revisadas viram `em_conflito`, preservando o histórico.
- Leitura conservadora: texto corrido não vira município (stopwords como "cidade", "para",
  "av."), nomes de estado (acentuados inclusive) não viram município, e "a definir - para
  todos" **não** é interpretado como local (nunca se fabrica localização).

Não há campo/tabela novos: usa-se a máquina existente de propostas, revisões, valores vigentes
e evidências. Não se duplica representação.

**Precedência de leitura de um campo** (a mesma regra documentada em `ops.py`, aplicada em
`radar/priority.py`): valor **vigente** (`valores_atuais`) > proposta **validada** mais recente
> proposta **mais recente**. Nunca a mais antiga — uma retificação (documento mais novo)
prevalece sobre o edital. Divergência **não resolvida por revisão** é tratada como ambígua (não
se escolhe em silêncio). Vale para `si_compatibility`, vagas e prazos.

## Frente B - Distância e preferências

### `radar/geography.py`

- **Distância geográfica em linha reta** (Haversine). Identificada sempre como
  `kind="geografica_linha_reta"`. **Nunca** é apresentada como distância rodoviária ou tempo de
  viagem (isso exigiria serviço específico, que o projeto não integra).
- Coordenadas de um **seed embutido, limitado e documentado** (capitais + Paulo Afonso/BA +
  Guajará-Mirim/RO) e de um **provedor de arquivo local opcional** (JSON). Sem coordenada →
  `known=False` + motivo. **Nunca** inventa coordenada.
- Nenhum dado é enviado a serviços externos.

### `radar/preferences.py`

Preferências geográficas (`reference_municipio`, `reference_uf`, `interest_states` padrão
`["BA","PE"]`, `practical_distance_km` padrão 300, `priority`). Guardadas em `radar_ops.json`
(**ignorado pelo Git**), validadas, sem endereço residencial e sem campos arbitrários (evita
gravar dados pessoais). BA/PE são **preferências**, nunca filtros obrigatórios.

## Frente C - Ranking explicável (`radar/ranking.py`)

Função determinística e versionada (`RANKING_VERSION=1`). Cada critério contribui com pontos,
peso e **motivo** (`factors`). **Ausência de dado não é zero**: um fator desconhecido fica fora
da soma e reduz a `coverage`, sem misturar "não sabemos" com "sabemos que não existe".

Pesos (máximo por critério):

| Critério | Máx | Escala |
|---|---|---|
| `vagas_indigenas_imediatas` | 4 | 1→1, 2-4→2, 5-9→3, ≥10→4 |
| `vagas_indigenas_reserva` | 2 | 0→0, ≥1→1, ≥5→2 (exibido à parte) |
| `compatibilidade_si` | 4 | aceito 4, categoria 3, ambíguo 1, incompatível 0 |
| `proximidade_prova` | 3 | ≤prática 3, ≤2× 2, mais distante 1 |
| `confianca_evidencia` | 2 | alta 2, média 1, frágil 0 |
| `confirmacao_dados` | 2 | confirmados 2, parcial 1, não confirmado 0 |

`TOTAL_MAX = 17`. **Piso excepcional** (`EXCEPTIONAL_FLOOR = 10`): aplica-se só a **forte**
aderência formal (aceitação **explícita** de Sistemas de Informação) com ≥3 vagas indígenas
imediatas **conhecidas** — mantém visível mesmo distante, sem inflar caso fraco; nunca faz
`score > possible`. Rótulos: `boa_aderencia`, `oportunidade_importante_distante`,
`exige_confirmacao`, `compatibilidade_desfavoravel`, `sem_vagas_indigenas` (dados confirmados,
mas sem vagas indígenas) e `sem_dados_suficientes`. A **urgência** (prazo de isenção/inscrição)
é dimensão independente, exibida à parte; não altera a pontuação e não transforma cargo
incompatível em boa oportunidade. Nunca é apresentada como probabilidade de aprovação.

## Camada de junção (`radar/priority.py`)

Lê propostas/revisões/valores vigentes e produz a lista ordenada. Prova e lotação resolvidas
separadamente; a distância de decisão usa o **local de prova** (nunca a lotação). Ordenação
determinística por `(-score, urgência, contest_id)`.

## API, CLI e interface

- `GET /api/prioridades?limit=N` - lista ordenada com fatores, localização, distância e urgência.
- `GET /api/preferencias` / `POST /api/preferencias` - ler/gravar preferências (validadas).
- CLI: `ops-prioridades`, `ops-preferencias`.
- Interface: seção **Priorização de oportunidades** (`#priorities-panel`) com formulário de
  preferências, filtros (estado, compatibilidade, localização não confirmada), prova × lotação,
  distância honesta, vagas imediatas × cadastro de reserva e explicação por fator.

O contrato v1 de `GET /api/concursos` (18 campos) permanece **inalterado**. Nenhuma migração de
schema foi necessária (v9 segue atual).

## Auditoria do SQLite

Caminho efetivo: `C:\Users\anton\OneDrive\Desktop\radar-de-concursos\data\radar.sqlite3`
(OneDrive), usado pelo **mesmo** caminho no coletor, CLI, servidor e Tarefa Agendada
(`radar_ops.json` → `db_path` relativo à raiz). `PRAGMA integrity_check = ok`, esquema v9,
593 concursos. Risco de sincronização parcial durante escrita permanece; **não** houve migração
de local nesta fase (recomendação não destrutiva: manter fora de sync em tempo real, com backup +
verificação + rollback, sem excluir a cópia antiga).

## Perfil de conhecimento (Fase 21 - auditoria)

Ver `docs/superpowers/plans/2026-10-16-geographic-ranking-prova-real.md` (§Perfil de
conhecimento). Resumo: **não implementado**; a compatibilidade formal (`si_compatibility`) existe,
mas não há perfil de conhecimentos nem cruzamento com conteúdo programático.

## Compatibilidade e limites

- Localização só é usada a partir de proposta documental; a base real ainda **não** tem propostas
  de local, então a maioria aparece como `nao_informado`/`nao_extraido` (honesto).
- Distância é linha reta; não há estimativa rodoviária.
- v1 inalterada; alertas/triagem/notificações da Fase 19 preservados.
