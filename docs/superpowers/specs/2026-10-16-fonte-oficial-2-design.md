# Segunda fonte oficial: DOU (Imprensa Nacional) — desenho e decisão

Data: 2026-10-16

## Intenção

Demonstrar que o Radar suporta **uma segunda fonte oficial independente** da já
integrada (Guajará-Mirim / Diário Oficial dos Municípios de Rondônia, AROM), sem
alterar os 18 campos de `GET /api/concursos` nem o fluxo documental existente.
Sucesso significa: um adaptador isolado, reutilizável e auditável que descobre
publicações oficiais, registra documentos com proveniência e alimenta o
monitoramento — sem confundir números globais com números por cargo e sem
confirmar fatos automaticamente.

Não-objetivos: cobertura nacional, dezenas de fontes, plataforma de estudos,
serviços pagos, tarefas agendadas reais, migração da base de produção.

## Investigação de fontes (2026-10-16)

| Candidata | Oficialidade | Acesso | Documentos | Veredito |
|---|---|---|---|---|
| **DOU – Leitura do Jornal (in.gov.br)** | Imprensa Nacional (federal) | Página diária pública; JSON embutido; HTTPS; sem login | Matérias da Seção 3 (editais, retificações, avisos) com título, órgão, tipo, data e texto | **Escolhida** |
| DOU – busca (`/consulta/-/buscar/dou`) | Imprensa Nacional | Portal Liferay; retornou 200 no navegador, mas é frágil (relatos de 404) e devolve HTML | Resultados paginados | Descartada (fragilidade; a Leitura do Jornal entrega o mesmo com estrutura mais estável) |
| DOU – Base de Dados (XML/ZIP) | Imprensa Nacional | `in.gov.br/dados-abertos/...`; ZIP mensal | XML das edições | Descartada para o ciclo (mensal, volumosa, defasada) |
| **INLABS** (`inlabs.in.gov.br`) | Imprensa Nacional | Exige **conta** (`logar.php`) para download automatizado | XML/PDF por edição | Descartada (dependeria de credencial de conta) |
| DOU – WS-INCom (`wsincom.in.gov.br`) | Imprensa Nacional | WebService SOAP **de publicação**, com autorização/IP liberado | — | Descartada (é para publicar, não consultar) |
| DOE-RS | Estado do RS | TLS instável no teste | — | Descartada (indisponível no momento) |
| DOE-ES / DOE-PR | Estados | DNS não resolveu no teste | — | Descartadas |
| Agregadores (ex.: Querido Diário, Jusbrasil) | Terceiros | Vários | Agregados | Descartados como **fonte** (não comprovam oficialmente; poderiam só ajudar a descobrir) |

### Por que o DOU (Leitura do Jornal)

- **Oficialidade**: é o veículo oficial da Imprensa Nacional; o conteúdo do site é
  publicado sob licença Creative Commons (Atribuição-SemDerivações 3.0).
- **Acesso**: página diária pública `https://www.in.gov.br/leiturajornal?data=DD-MM-AAAA&secao=do3`
  (Seção 3 = "contratos, editais e avisos", que inclui **concursos públicos**).
  A página embute um JSON oficial com as matérias do dia.
- **Documentos**: cada matéria tem `urlTitle` (slug + ID estável), `title`,
  `artType` (Edital, Aviso, Retificação, Resultado de Concurso Público…),
  `hierarchyStr` (órgão), `pubDate` e o `content` (texto oficial).
- **Independência**: cobertura federal, complementar à municipal já integrada.
- **Estabilidade**: a URL da matéria é `https://www.in.gov.br/web/dou/-/{urlTitle}`,
  com ID numérico; a edição é identificada por data + seção.
- **Limites verificados**: o servidor responde **403 a clientes sem cabeçalhos de
  navegador**; com User-Agent de navegador responde 200. A página tem ~2,5 MB por
  edição. Não há autenticação, cota ou custo. Não se contorna bloqueio: usa-se
  apenas leitura pública com um UA compatível.

### Limitações assumidas e documentadas

- A interface "Leitura do Jornal" é pública, porém **não é uma API formalmente
  versionada**; sua estrutura pode mudar. O adaptador falha fechado
  (`ValueError`) e o monitoramento registra a falha, sem inventar dados.
- O `content` pode ser um recorte textual; a extração é conservadora e nada é
  confirmado sem revisão humana.
- A publicação **certificada (PDF)** prevalece sobre o texto aberto.

## Arquitetura

Adaptador isolado em `radar/dou_source.py`, sem espalhar regras da fonte:

- `edition_url(section, day)` / `fetch_edition(...)` — HTTPS, UA de navegador,
  limite de 8 MB, decodificação UTF-8 → Windows-1252.
- `parse_edition(html)` — extrai o array JSON oficial balanceado; falha fechado.
- `is_relevant(item)` / `classify_kind(item)` — relevância por menção a "concurso"
  (prova textual) e tipo `edital` / `retificacao` / `outro`.
- `article_url(item)` / `to_candidate(item, observation_id, discovered_at)` —
  candidato para `register_document`, com `inline_content` (o texto oficial).
- `discover(html, observation_id)` — candidatos deduplicados por URL.
- `dou_source(day)` — descritor da fonte para o monitoramento, com
  `source_url` própria (`.../leiturajornal?secao=do3`), `competition_id` próprio
  (`DOU-S3`) e `fetch`/`discover`.

Reutilização (não reimplementação):
- `document_store.register_document` + `record_version` — documentos e versões.
- `document_store.ensure_observation` (**novo**, genérico) — cria identidade de
  concurso + observação para fontes que não derivam de `concursos` v1, idempotente.
- `document_extract.extract_blocks` + `document_fields.extract_field_proposals` —
  extração conservadora (vagas imediatas, indígenas, cadastro de reserva, datas).
- `monitoring.run_cycle` — a fonte entra como mais uma fonte; candidatos podem
  trazer `inline_content`, que vira versão sem rebaixar a página.

Integridade das vagas (herdada de `document_fields`): só emite proposta com frase
explícita; `role_id` sempre `None` (o DOU não distribui por cargo no texto);
zero de reserva só com declaração inequívoca; cadastro de reserva sem número não
vira zero; nada é validado automaticamente.

Fluxo: edição diária → JSON oficial → candidatos (por matéria relevante) →
documento + versão (texto oficial) → blocos → propostas com evidência → revisão
humana. O v1 (`concursos`) permanece exclusivo da fonte municipal.

## Contratos preservados

- `GET /api/concursos` — 18 campos inalterados.
- `GET /api/concursos/identidades`, `/detalhes`, `/api/monitoramento` — inalterados.
- Nenhuma migração de esquema nova (v4 já suporta ciclos/fontes).
- `document_discovery._AUTHORIZED_SOURCES` ganha `www.in.gov.br` (só `/web/dou/-/`),
  sem enfraquecer as defesas de download.

## Como adicionar uma terceira fonte

1. Escrever `radar/<fonte>_source.py` com `fetch`/`discover` e, se preciso,
   `competition_id`.
2. Declarar o host/rota em `document_discovery._AUTHORIZED_SOURCES`.
3. Incluir o descritor em `monitoring.default_sources()`.
4. Testar parsing/filtro/idempotência com fixtures; nada além disso muda.
