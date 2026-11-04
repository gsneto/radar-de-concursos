# Cobertura Real de Dados — Fase 47

Data da verificação: **2026-11-04** (`America/Recife`).
Base: branch `radar-configuracao`, schema **v21**, banco `data/radar.sqlite3`.

Este documento mede o que o Radar efetivamente enxerga, extrai e disponibiliza para decisão
humana — separando descoberta bruta (notícia de agregador) de cobertura documental oficial
(edital/retificação com evidência literal por página).

---

## 1. Metodologia e Denominadores

1. **Unidade de certame**: registros em `concursos_identidade` com
   `estado_identidade != 'container_fonte'` (**843 certames**). O Diário Oficial da União
   (`dou-secao-3`) é mantido separado como `container_fonte` (**1 container**).
2. **Cobertura documental oficial (`coverage_states_v1`)**: página de agregador (`pci`)
   nunca conta como documento oficial nem comprova vaga, requisito ou prazo. Apenas
   documentos de fonte oficial/banca sustentam `edital_extraido` ou `campos_candidatos`.
3. **Unidade de oportunidade**: par `(concurso × cargo/rótulo)` na carteira operacional
   (`portfolio_v1`, **839 oportunidades**) e na matriz de elegibilidade (`eligibility_v3`,
   **597 oportunidades com propostas extraídas**).
4. **Regra de evidência**: nenhuma proposta extraída (texto ou OCR) é tratada como
   confirmada sem decisão humana em `revisoes_campo` / `valores_atuais`.

---

## 2. Funil Global de Cobertura (Snapshot Baseline — 2026-11-04)

| Camada do funil | Total | % do universo | Observação |
|---|---:|---:|---|
| Certames identificados | 843 | 100,0% | Exclui 1 `container_fonte` (`dou-secao-3`) |
| Certames com ao menos 1 documento | 842 | 99,9% | 1 certame (`guajara`) apenas na tabela v1 |
| Certames apenas em agregador (`pci`) | 703 | 83,4% | Sem travessia automática para a banca oficial |
| Certames com documento de fonte oficial | 139 | 16,5% | FGV (109), Quadrix (22), IBFC (5), DOU (3) |
| Certames com edital oficial classificado | 66 | 7,8% | `edital_abertura` ou `edital_retificado` |
| Certames com campos candidatos ou conflito | 60 | 7,1% | 55 `campos_candidatos` + 5 `conflito` |
| Certames com campos confirmados por humano | 0 | 0,0% | Revisão humana ainda não executada na base |

### 2.1 Estado de cobertura oficial por fonte (`843 certames`)

| Fonte(s) no certame | Total | `campos_candidatos` | `conflito` | `edital_extraido` | `oficial_sem_edital` | `oficial_sem_extracao` | `apenas_agregador` | `oficial_nao_importado` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `pci` | 703 | 0 | 0 | 0 | 0 | 0 | 703 | 0 |
| `fgv-conhecimento` | 106 | 41 | 5 | 0 | 52 | 8 | 0 | 0 |
| `fgv-conhecimento,pci` | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| `quadrix` | 22 | 11 | 0 | 0 | 11 | 0 | 0 | 0 |
| `ibfc` (piloto) | 5 | 3 | 0 | 0 | 2 | 0 | 0 | 0 |
| `dou-secao-3,pci` | 3 | 0 | 0 | 2 | 1 | 0 | 0 | 0 |
| `(sem_fonte)` (`guajara`) | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| **Total** | **843** | **55** | **5** | **2** | **69** | **8** | **703** | **1** |

---

## 3. Cobertura para o Perfil do Usuário

Perfil avaliado (`AGENTS.md` e `radar/preferences.py`):
- **Formação**: Bacharelado em Sistemas de Informação (`si_bacharelado`);
- **Reserva de vagas**: oportunidades indígenas (distinguindo vagas imediatas, cadastro de
  reserva, reserva combinada PPIQ/PI-PQ, zero explícito e menção fora do escopo);
- **Referência geográfica**: deslocamento desde **Paulo Afonso–BA** (`-9.3983, -38.2147`),
  UFs de interesse `["BA", "PE"]`, raio prático `300 km` em linha reta (Haversine).

### 3.1 Elegibilidade para Sistemas de Informação (`597 oportunidades`)

| Estado na matriz (`eligibility_v3`) | Oportunidades | Significado |
|---|---:|---|
| `explicito` | 1 | "Sistemas de Informação" expresso no requisito do cargo |
| `categoria_inclui_curso` | 3 | Categoria (ex.: área de Computação/TI com rol que inclui SI) comprovada |
| `nivel_minimo` | 18 | Exige curso superior em qualquer área |
| `area_correlata_interpretacao` | 5 | Área de TI/Informática sem rol fechado; exige decisão humana |
| `outras_formacoes` (incompatível) | 81 | Requisito expresso restrito a outra formação (Direito, Contábeis etc.) |
| `nao_encontrado` / pendente | 489 | Texto do requisito do cargo ainda não associado ou não extraído |

### 3.2 Reserva Indígena por Cargo (`597 oportunidades`)

| Escopo da reserva indígena | Oportunidades | Regra aplicada |
|---|---:|---|
| `cargo_imediata` | 31 | Vaga imediata indígena explícita na linha do cargo |
| `cargo_zero_imediato_com_reserva` | 55 | `0` imediata publicada + reserva/CR indígena no cargo |
| `distribuido_por_cargo` | 14 | Quantitativo indígena distribuído por cargo |
| `reserva_combinada_com_outros_grupos` | 11 | Coluna unificada (ex.: PPIQ / PI+PQ) sem separar cota indígena |
| `mencao_sem_quantidade` | 17 | Reserva indígena mencionada sem número por cargo |
| `reserva_sem_quantidade` | 1 | Reserva prevista sem quantitativo na tabela |
| `mencao_fora_do_escopo_de_reserva` | 86 | Menção lexical ("indígena" em conteúdo programático/isenção), não é vaga |
| `cargo_explicito_zero` | 357 | Tabela de vagas publicada com `0` ou `-` na coluna indígena |
| `ausente_no_documento` / `nao_localizado` | 25 | Sem menção no trecho extraído |

### 3.3 Geografia e Deslocamento desde Paulo Afonso–BA (`839 itens de carteira`)

- **UFs de prova identificadas (`294 de 839 itens`)**: `ES` (46), `SC` (30), `RJ` (30),
  `MS` (30), `PR` (29), `GO` (25), `AP` (18), `TO` (18), `RS` (13), `BA` (9), `AM` (7),
  `SP` (7), `RO` (6), `SE` (6), `PB` (5), `MG` (5), `MA` (5), `RN` (4), `MT` (1). Sem UF
  extraída: 545.
- **Distância em linha reta desde Paulo Afonso–BA**: calculada em **18 certames** cujo
  município de prova consta no seed geográfico local (ex.: Salvador/BA a `399,2 km`,
  Brasília/DF a `1.266,9 km`, Belo Horizonte/MG a `1.321,1 km`).
- **Lacuna identificada no baseline**:
  1. Em `radar_ops.json`, `reference_municipio` estava `null` (apenas `reference_uf: "BA"`),
     fazendo `distance_km` retornar `null` por falta de município de origem configurado;
  2. Certames em `PE` (como **TJ-PE — `tjpe26`**, `contest_id=59475b5a`) estavam retidos em
     `oficial_sem_extracao` porque o edital de abertura e a 1ª retificação estavam
     registrados mas ainda sem versão baixada;
  3. Municípios próximos a Paulo Afonso–BA (Aracaju/SE a ~185 km, Maceió/AL a ~275 km,
     Petrolina/PE, Juazeiro/BA, Caruaru/PE, Garanhuns/PE, Arapiraca/AL, Feira de Santana/BA)
     e municípios de prova de certames estaduais (ex.: Colatina/ES, Guarapari/ES) precisam
     estar no seed geográfico ou resolver a menor distância quando o certame oferece
     múltiplas cidades de prova.

### 3.4 Prazos Operacionais (`205 grupos de prazo em 843 certames`)

- **Temporais**: `futuro` (10), `expirado` (180), `sem_data` (15).
- **Situação operacional dos futuros**:
  - `candidato_nao_revalidado`: **3** (`cid=8071bb87` com `inscricao_fim` e
    `resultado_isencao_final` em `2026-11-10`; `cid=10cf0970` com `inscricao_fim` em
    `2026-11-18`);
  - `revalidado_na_fonte`: **1** (`cid=4bcc186d` — `quadrix-3049`, `2026-11-05`);
  - `alterado_por_retificacao`: **1** (`cid=4f495c42`, `2027-04-18`);
  - `conflito_documental`: **5** grupos futuros em conflito entre documentos/páginas.

---

## 4. Comparação contra Amostra de Verdade Externa e Gargalos do Funil

Comparando o que as fontes oficiais publicam em suas listagens abertas contra o que chega
até `campos_candidatos` no Radar:

| Fonte / Banca | Amostra na listagem da fonte | Certames no Radar | Com edital extraído / candidatos | Onde escapam (gargalo real) |
|---|---:|---:|---:|---|
| **FGV Conhecimento** | 109 páginas de concurso | 109 (100%) | 46 (42,2%) | **55 em `oficial_sem_edital`** (concursos mais antigos/em andamento onde os anexos recentes são resultados/convocações) e **8 em `oficial_sem_extracao`** (editais não baixados, `nao_iniciada` ou `pdf_sem_texto`). |
| **Quadrix** | 22 concursos ativos coletados | 22 (100%) | 11 (50,0%) | **11 em `oficial_sem_edital`** (anexos no CDN sem edital de abertura classificado ou versões `nao_iniciada`). |
| **IBFC** (piloto) | 5 concursos no piloto | 5 (100%) | 3 (60,0%) | **2 em `oficial_sem_edital`**; conector está desligado por padrão em `radar_ops.json` (`enabled: false`). |
| **DOU Seção 3** | Edições diárias coletadas | 3 certames vinculados (+1 container) | 2 (66,7%) | Avisos do DOU só geram certame quando reconciliados ou com edital identificável; o restante fica retido no container da seção. |
| **PCI Concursos** | 709 notícias listadas | 709 (703 exclusivos + 6 reconciliados) | 5 reconciliados com banca | **703 (99,2%) param em `apenas_agregador`**: o conector PCI coleta a listagem/notícia, mas o Radar não possui conectores para dezenas de bancas menores (Cebraspe, FCC, Vunesp, Idecan, AOCP, Consulplan, prefeituras). |

---

## 5. Classificação das 18 Fontes Catalogadas (`radar/source_catalog.py`)

| # | ID da fonte | Categoria | Natureza | Classificação Fase 47 | Status no catálogo | Justificativa e limites |
|---:|---|---|---|---|---|---|
| 1 | `fgv-conhecimento` | concursos | oficial | **Habilitada agora (ativa)** | `habilitada` | Conector ativo; 109 certames; persistência de metadados e documentos permitida. |
| 2 | `quadrix` | concursos | oficial | **Habilitada agora (ativa)** | `habilitada` | Conector ativo; 22 certames; usa apenas CDN de anexos (`uploads` bloqueado por robots). |
| 3 | `dou-secao-3` | concursos | oficial | **Habilitada agora (ativa)** | `habilitada` | Conector ativo; tratado como `container_fonte` até identificação do certame. |
| 4 | `guajara` | concursos | oficial | **Habilitada agora (ativa)** | `habilitada` | Conector base do contrato v1 (Prefeitura de Guajará-Mirim/RO). |
| 5 | `pci` | concursos | agregador | **Habilitada agora (ativa)** | `habilitada` | Descoberta complementar; nunca confirma vaga nem substitui edital oficial. |
| 6 | `ibge-localidades` | auxiliar | oficial | **Habilitada agora (ativa)** | `habilitada` | Fonte auxiliar oficial para validação de municípios/UFs. |
| 7 | `ibfc` | concursos | oficial | **Habilitável agora (requer autorização)** | `habilitada` | Conector implementado (`radar/ibfc.py`); `enabled: false` em `radar_ops.json` (anexos CDN são opt-in). |
| 8 | `dados-gov-br` | auxiliar | oficial | **Pendente externa (credencial)** | `aguardando_credencial` | Exige variável de ambiente `RADAR_DADOS_GOV_BR_TOKEN`. |
| 9 | `conecta-gov-br` | auxiliar | oficial | **Pendente externa (termos)** | `aguardando_validacao_de_uso` | Catálogo governamental; cada API exige credencial e validação de termos própria. |
| 10 | `concursosnobrasil` | concursos | agregador | **Sem valor imediato / validação pendente** | `aguardando_validacao_de_uso` | Agregador secundário sem conector; aumentaria `apenas_agregador` sem trazer editais oficiais. |
| 11 | `acheconcursos` | concursos | agregador | **Sem valor imediato / validação pendente** | `aguardando_validacao_de_uso` | Agregador secundário sem conector; notícia não comprova concurso. |
| 12 | `jcconcursos` | concursos | agregador | **Sem valor imediato / validação pendente** | `aguardando_validacao_de_uso` | Jornalístico/agregador sem conector; notícia não comprova concurso. |
| 13 | `api-concursos-vinimartinsc` | concursos | comunitaria | **Bloqueada por licença / não implementada** | `nao_implementada` | Licença do software não autoriza armazenar conteúdo raspado de terceiros. |
| 14 | `concursos-api-deno` | concursos | comunitaria | **Sem valor operacional (offline)** | `nao_implementada` | Endpoint público respondeu 404 na verificação. |
| 15 | `api-concursos-kaua` | concursos | comunitaria | **Bloqueada por licença** | `bloqueada` | Repositório sem licença; proibido reutilizar código ou dados. |
| 16 | `quest-api` | educacional | comercial | **Bloqueada por licença/assinatura** | `bloqueada` | Código privado, sem licença e sem assinatura contratada. |
| 17 | `qconcursos` | educacional | comercial | **Bloqueada por licença/robots** | `bloqueada` | Sem autorização de acesso automatizado nem de persistência de conteúdo. |
| 18 | `questoesdeconcursos` | educacional | comercial | **Bloqueada por licença/robots** | `bloqueada` | Sem autorização de acesso automatizado nem de persistência de conteúdo. |

---

## 6. Anatomia das Pendências Documentais (Baseline para a Tarefa 2)

### 6.1 Documentos sem versão (`1.429 documentos`)

| Tipo documental (`tipo_documental`) | `kind` | Quantidade | % dos 1.429 | Prioridade para cobertura |
|---|---|---:|---:|---|
| `resultado` | `outro` | 823 | 57,6% | Baixa (etapa pós-prova) |
| `None` (páginas de agregador PCI / anexos antigos) | `outro` | 207 | 14,5% | Baixa (203 são links do PCI) |
| `homologacao` | `outro` | 145 | 10,1% | Baixa |
| `gabarito` | `outro` | 88 | 6,2% | Baixa |
| `convocacao` | `outro` | 66 | 4,6% | Baixa |
| `outro` | `outro` | 55 | 3,8% | Baixa |
| `comunicado` | `outro` | 23 | 1,6% | Média |
| **`retificacao`** | **`retificacao`** | **9** | **0,6%** | **Alta (altera prazos/vagas/requisitos)** |
| **`pagina_concurso`** | **`outro`** | **7** | **0,5%** | **Alta (metadados oficiais FGV)** |
| **`edital_retificado`** | **`edital`** | **3** | **0,2%** | **Crítica (edital consolidado: TJ-PE, MP-ES, PGE-AC)** |
| **`cronograma`** | **`outro`** | **2** | **0,1%** | **Alta (datas oficiais: MP-ES, PGE-AC)** |
| **`edital_abertura`** | **`edital`** | **1** | **0,1%** | **Crítica (DPE-RJ)** |

### 6.2 Versões baixadas mas não concluídas (`13 versões` fora as `1.105 parciais`)

1. **6 versões `nao_iniciada`** (arquivo já no disco local, zero custo de rede):
   - `vid=557152fb` (`did=5e2eda58`): FGV `edital_abertura` (CGM — `606 KB`)
   - `vid=d4ae33cb` (`did=321e263e`): FGV `edital_abertura` (`655 KB`)
   - `vid=0429f43a` (`did=b823b17d`): Quadrix `edital_abertura` (`732 KB`)
   - `vid=e142b63d` (`did=478b1115`): Quadrix `retificacao` (`280 KB`)
   - `vid=6bc2b0bc` (`did=536412cc`): Quadrix `edital_retificado` (`798 KB`)
   - `vid=cd35e5d4` (`did=1fc5cbb3`): Quadrix `edital_retificado` (`788 KB`)
2. **6 versões `falhou` com `pdf_sem_texto`** (PDFs escaneados da FGV, elegíveis para OCR
   local via `windows_ocr` + `pymupdf`):
   - `vid=aa93d966` (`did=4cda7d1a`): `edital_abertura` (`1,14 MB`)
   - `vid=52482ae7` (`did=0483bea9`): `outro` (`344 KB`)
   - `vid=f7124a70` (`did=5d4ea38f`): `outro` (`382 KB`)
   - `vid=01682fb7` (`did=5e3a7c08`): `outro` (`280 KB`)
   - `vid=41fdac29` (`did=d98f9891`): `convocacao` (`146 KB`)
   - `vid=1cae1a04` (`did=0beeabf1`): `comunicado` (`758 KB`)
3. **1 versão `falhou` com `pdf_ilegivel`**:
   - `vid=86f22fb0` (`did=e8cc66fc`): `cronograma` (`127 KB`, arquivo PDF corrompido na origem).

### 6.3 Conflitos classificados (`111 grupos`)

| Causa diagnosticada (`conflict_review_v1`) | Grupos | Ação prescrita |
|---|---:|---|
| `documentos_com_data_distinta` | 28 | Comparar documento mais recente com o anterior na mesa de revisão |
| `escopo_diferente` | 22 | Verificar se a proposta pertence a outro cargo/localidade |
| `cargos_diferentes_sem_identificacao` | 19 | Reconciliar rótulo de cargo antes de decidir o valor |
| `documentos_diferentes_sem_ordem` | 17 | Preencher/verificar ordem temporal dos documentos |
| `mesmo_documento_valores_distintos` | 15 | Conferir páginas distintas do mesmo edital (ex.: prova objetiva vs. prática) |
| `retificacao_posterior` | 9 | Candidato da retificação mais nova pronto para confirmação humana |
| `variacao_de_extracao` | 1 | Normalização equivalente entre extrações |
