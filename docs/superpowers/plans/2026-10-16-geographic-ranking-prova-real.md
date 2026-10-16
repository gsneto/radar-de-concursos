# Prova real - Fase 20: inteligência geográfica e ranking explicável

Data: 2026-10-16. Base **habitual**: `C:\Users\anton\OneDrive\Desktop\radar-de-concursos\data\radar.sqlite3`
(esquema v9). Python validado: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.

## Suíte de testes

- Baseline observada (antes de implementar): **605 testes, OK** (confirmada por execução real).
- Final: **704 testes, OK** (99 novos). Novos: `test_location.py` (23), `test_geography.py` (15),
  `test_ranking.py` (21), `test_preferences.py` (12), `test_priority.py` (17),
  `test_priority_api.py` (10) e ampliação de `test_ui.py` (harness Node cobre `renderPriorities`).

## Revisão independente (delegação via `task`/code-reviewer)

**2 críticos + 8 importantes + 7 menores** corrigidos.

- **C1 (crítico):** `si_compatibility` resolvia para a proposta **mais antiga** (`_proposal_rows`
  não selecionava `p.id`; `next(...)` caía no primeiro item), então uma retificação
  `incompativel` era exibida como `boa_aderencia`. Corrigido com precedência documentada
  **vigente > validado mais recente > mais recente**; divergência não resolvida vira `ambiguo`
  (flag `conflict`). Regressões: `test_si_divergente_sem_revisao_vira_ambiguo`,
  `test_si_validado_vence_divergencia`.
- **C2 (crítico):** urgência usava o prazo **mais antigo** (`setdefault`), mostrando prazo
  expirado após prorrogação. Agora usa o mais recente. Regressão:
  `test_prazo_usa_mais_recente_nao_o_mais_antigo`.
- **Importantes:** I1 estados de extração (`parcial`/`concluida`); I2/I3 texto corrido virando
  município/UF (`para`→PA) e frases gigantes — parsing conservador com stopwords;
  I4 nomes de estado acentuados (Goiás/Pará/Espírito Santo); I5 coordenada NaN/fora de faixa
  virava distância "conhecida"; I6 `update_preferences` apagava o resto do config — agora recusa
  e grava atômico; I7 `POST /api/preferencias` derrubava a conexão em falha de escrita — agora
  500; I8 vaga ambígua contava como confirmada — agora desconhecida.
- **Menores:** M1 piso exige aceitação expressa e nunca `score>possible`; M2 endereço residencial
  rejeitado; M3 defaults não mutáveis; M4 predicado público `is_readable_schema`; M5 provedor de
  coordenadas acessível via `preferences.coordinates_path` e cacheado; M6 `Allow` correto e
  `limit<1` rejeitado; M7 rótulo `sem_vagas_indigenas`.

## Auditoria do SQLite

```
integrity_check = ok
user_version    = 9
concursos       = 593
documentos      = 636
propostas       = 751
```

Caminho único usado por coletor, CLI, servidor e Tarefa Agendada (`radar_ops.json` →
`db_path` relativo à raiz do projeto; a tarefa roda com `WorkingDirectory` na raiz). Não houve
migração de local; risco de sincronização OneDrive registrado (recomendação não destrutiva).

## Priorização na base real

`python -m radar ops-prioridades --limit 3` (referência do usuário indefinida → distância
honestamente desconhecida):

```
count: 593
contest e4271152 score 3/17 label exige_confirmacao | si=ambiguo indig_im=0 indig_cr=1
  prova=nao_informado dist=desconhecida ('referência geográfica do usuário não definida')
  urgency=exemption_end 2026-09-22 expirado (-24d)
labels: {sem_dados_suficientes: 581, exige_confirmacao: 10, compatibilidade_desfavoravel: 2}
si_conflict: 6   score<=possible: True
```

Leitura honesta: a base real **ainda não tem propostas de localização**, então a maioria é
`sem_dados_suficientes`/`nao_informado` — o sistema não inventa local nem distância. Os 6
`si_conflict` são concursos cujo `si_compatibility` diverge entre documentos e **não** foi
resolvido por revisão: ficam `ambiguo` (não se escolhe em silêncio), em vez de reportar o valor
mais antigo (bug C1 corrigido).

## Preferências (CLI + config)

```
$ python -m radar ops-preferencias --reference-uf BA --reference-municipio Salvador \
    --practical-distance-km 250 --priority potencial
{"reference_municipio": "Salvador", "reference_uf": "BA", "interest_states": ["BA","PE"],
 "practical_distance_km": 250, "priority": "potencial"}
```

Gravado em `radar_ops.json` (ignorado pelo Git), restaurado aos defaults após a prova.
Preferências **não** são enviadas a nenhum serviço.

## API (servidor loopback real)

```
GET /api/prioridades?limit=3   -> 200  count=593  first_label=exige_confirmacao  prefs_uf=BA
GET /api/preferencias          -> 200  {"reference_municipio":"Salvador", ...}
```

`GET /api/concursos` (v1) permanece com **18 campos** (a base real não tem linhas v1 porque
nunca foi executado `collect`; a estrutura é garantida por `tests/test_contract.py`, inalterado).

## Distância geográfica (prova direta)

```
distance_from_reference('Salvador','BA', reference={'municipio':'Recife','uf':'PE'})
-> {'distance_km': 676.4, 'kind': 'geografica_linha_reta', 'known': True}
```

Linha reta Salvador→Recife ≈ 676 km. Sempre identificada como **geográfica (linha reta)**;
nunca rodoviária.

## Perfil de conhecimento (auditoria - Fase 21)

**Existe:** classificação formal da formação (`si_compatibility`: aceito expressamente /
abrangido por categoria / ambíguo / incompatível / não informado / não extraído),
`education`, `accepted_courses`.
**Não existe:** perfil editável de conhecimentos do usuário; extração de **conteúdo
programático**; lacunas de conhecimento; reaproveitamento entre concursos; classificação de
acessibilidade agora × preparação necessária.
**Recomendação:** Fase 21 dedicada ao perfil de conhecimento e cruzamento com o conteúdo
programático (grep confirma ausência de qualquer extração de "conteúdo programático").

## Limitações honestas

- A base real não tem propostas de localização; a priorização reflete isso como
  `nao_informado`/`nao_extraido`, sem inferir (v1 `exam_location`/`work_location` do artigo e a
  UF de descoberta do PCI **não** são usadas como prova/lotação — seriam inferência).
- Coordenadas cobrem um seed limitado (capitais + Paulo Afonso + Guajará-Mirim); municípios
  fora dele retornam distância desconhecida até o usuário fornecer um provedor local.
- Distância é linha reta; não há estimativa rodoviária.
