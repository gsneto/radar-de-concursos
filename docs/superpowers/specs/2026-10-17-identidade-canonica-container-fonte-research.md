# Pesquisa — Fase 27: identidade canônica de certame e fonte oficial piloto

Data: 2026-10-17. Nenhum código de terceiros foi copiado nesta fase.

## 1. Modelagem da identidade: certame x fonte

O problema real: `observacoes_concurso.competition_id` guarda o identificador da **fonte**, e
`documentos.contest_id` deriva dele. Quando a fonte usa um identificador de publicação (seção do
DOU) ou de catálogo (lista de certames), todos os documentos daquela publicação caem no mesmo
"concurso".

| Alternativa | Avaliação | Decisão |
|---|---|---|
| `documentos.contest_id` anulável | exige reconstrução da tabela em SQLite (12 passos), recria FKs e índices, e o leitor v1 passaria a lidar com nulo | **Rejeitado**: risco alto, ganho nulo |
| Tabela de junção `documento_concurso` | terceira fonte de verdade ao lado de `documentos.observation_id`; histórico de associação continua sem lugar | **Rejeitado** |
| Coluna de estado na identidade (`container_fonte`) + log append-only de associação | aditivo, sem reconstrução, mantém `observation_id` como vínculo físico e dá histórico explícito | **Adotado** |
| Inferir certame pelo título do documento | proibido pelo domínio (associação por semelhança) | **Rejeitado** |

O padrão de log append-only já existe no projeto (`revisoes_campo`, `valores_atuais`): nenhuma
decisão sobrescreve a anterior; a nova linha aponta para a substituída.

## 2. Diagnóstico de associação: sinal por órgão, não por volume

A primeira versão da regra `muitos_atos_sem_propostas` acusava qualquer concurso com ≥3 editais
sem propostas. Isso produz falso positivo: uma banca pode publicar legitimamente vários editais
do mesmo certame (abertura + retificações + anexos).

Regra revisada: exigir **≥2 emissores distintos** (`documentos.issuer`). Mesma correção em
`titulos_divergentes`. Resultado no banco real: de 3 apontamentos para **0**, com o container
registrado à parte (`containers_fonte = 1`). O defeito original continua visível pelo motivo
`identidade_de_secao`, que é o motivo correto.

## 3. Escolha da fonte oficial piloto

Critérios objetivos, verificados antes de integrar:

| Critério | Por que importa | IBFC | Cebraspe | AOCP | FCC |
|---|---|---|---|---|---|
| HTML estático (catálogo e detalhe) | dispensa navegador e respeita o desenho stdlib-only | sim | sim | sim | sim |
| Identidade **por certame** | evita repetir o defeito do DOU | sim (`ibfc-<id>`) | sim | sim | sim |
| Anexos em host já autorizado | nenhuma nova autorização de rede | sim (`anexos-r2.selecao.net.br`, plataforma do Quadrix) | não | não | não |
| `robots.txt` permite catálogo/detalhe | etiqueta de coleta | sim | sim | sim | sim |
| Publica retificação/comunicado com data | permite enriquecer certame existente | sim | sim | sim | sim |

IBFC foi o único que atendeu **todos** os critérios sem abrir host novo. Os outros três seguem
como candidatos registrados, com a mesma métrica de decisão da Fase 26:
`concursos_com_edital_oficial / concursos_com_oportunidade_ativa`.

## 4. Robôs e etiqueta de download

Medido em 2026-10-17:

| Host | `robots.txt` | Decisão |
|---|---|---|
| `concursos.ibfc.org.br` | permite `/index/` e `/informacoes/`; bloqueia `/admin`, `/painel`, `/uploads` | coletar catálogo e detalhe |
| `anexos-r2.selecao.net.br` | responde 404 (sem restrição) | baixar anexo (host já em `_AUTHORIZED_SOURCES`) |
| `anexos.cdn.selecao.net.br` | `Disallow: /` | **não baixar**: registrar metadados e URL, `fetch_allowed=False` |

Rejeitado contornar o bloqueio (proxy, user-agent alternativo, cache de terceiro): seria
exatamente o tipo de atalho que o projeto não toma. O dado continua acessível ao usuário pelo
link oficial; o que não existe é cópia local.

## 5. Alternativas rejeitadas para o piloto

- **Navegador headless**: as páginas são estáticas; adicionaria dependência binária sem ganho.
- **API não documentada**: não há endpoint público estável; scrape de HTML é o caminho oficial.
- **LLM para casar documento e certame**: proibido — informação extraída por IA não fica
  confirmada automaticamente.
- **Ampliar o piloto para 3–4 bancas de uma vez**: o gargalo é qualidade de associação; um piloto
  por vez permite medir antes/depois com denominador honesto.

## 6. Referências consultadas

- `robots.txt` dos três hosts acima (leitura direta).
- Código do projeto: `dou_source.py`, `document_store.register_document`,
  `monitoring.run_cycle`, `quadrix_source` (plataforma `selecao.net.br`), `document_types`.
- Dados reais: `concursos_identidade`, `observacoes_concurso`, `documentos`, `propostas_campo`,
  `ciclos_fontes`.
