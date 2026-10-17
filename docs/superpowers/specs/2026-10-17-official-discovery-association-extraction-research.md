# Pesquisa — Fase 26: fontes oficiais, associação e extração de PDF

Data: 2026-10-17. Nenhum código de terceiros foi copiado nesta fase.

## 1. Extração de texto de PDF

| Alternativa | Avaliação | Decisão |
|---|---|---|
| `pypdf` (já usado) com `extraction_mode="layout"` | preserva quebras de linha, mas muda o texto de todos os blocos → invalidaria evidências e hashes existentes | **Rejeitado** para esta fase |
| pdfplumber / PyMuPDF | novas dependências binárias; mudariam offsets | **Rejeitado** |
| OCR (Tesseract) | custo alto, precisão incerta, PDFs são textuais | **Rejeitado**: nenhum dos 15 editais é digitalizado |
| Re-segmentação do parágrafo em linhas lógicas | sem dependência, sem alterar o texto, mantém a citação literal | **Adotado** |

O padrão reaproveitado é o de "logical document" que o próprio projeto já usa em
`section_requirements.build_logical_document` (junção com mapa de offsets). Aqui a ideia foi
aplicada ao eixo oposto: **dividir** o parágrafo em linhas, não juntar páginas.

## 2. Fontes oficiais (Frente A)

Auditoria das integrações reais (`ciclos_fontes`):

| Fonte | Papel | Resultado medido | Limitação confirmada |
|---|---|---|---|
| DOU Seção 3 | descoberta | 20 docs, 10 novos | identidade por **seção**, não por certame |
| FGV | descoberta + edital | 35 docs, 34 novos | cobre só a própria banca |
| Quadrix | descoberta + anexos | 185 docs, 115 novos | anexos em CDN (host já autorizado) |
| PCI Concursos | descoberta | 477 docs | agregador: 477 páginas sem tipo |
| Portal municipal | fonte oficial | 0 docs | página sem estrutura estável |

Candidatos avaliados nesta fase:

| Candidato | Verificação | Decisão |
|---|---|---|
| Cebraspe (`cebraspe.org.br/concursos/`) | listagem HTML + PDFs por concurso, sem API | **Não integrado**: a lacuna dominante é *associação*, não volume |
| IBFC (`concursos.ibfc.org.br/`) | idem | **Não integrado** |
| Instituto AOCP | idem | **Não integrado** |
| FCC | idem | **Não integrado** |

Justificativa registrada: adicionar quatro scrapers aumentaria o número de documentos
`kind='outro'` sem aumentar `concursos_com_edital_oficial`, porque o gargalo medido é (a) não
existir edital para 577 concursos e (b) os documentos existentes estarem mal associados. A
métrica que justificaria a expansão continua sendo
`concursos_com_edital_oficial / concursos_com_oportunidade_ativa`.

## 3. Associação documento–concurso

Investigação do caso de 9 atos do DOU em um concurso:

- `dou_source.py:27` — `DOU_COMPETITION_ID = "DOU-S3"`.
- `dou_source.py:276` — `discover()` recebe a mesma `observation_id` para todos os atos da edição.
- `document_store.register_document` — vincula o documento à observação e, por consequência, ao
  concurso daquela observação.

Conclusão: a arquitetura já suporta associação contextual (`documentos.observation_id`,
`documentos.role_id`, `observacoes_concurso.competition_id`), mas a fonte do DOU usa um
identificador de **seção**. Não foi criada uma segunda estrutura de relacionamento — a correção
proposta é de identidade na fonte, e o diagnóstico ficou explícito.

Alternativas rejeitadas: reassociar por similaridade de título (proibido pelo domínio); criar
tabela `documento_concurso` paralela (duplicaria o modelo existente).

## 4. Local de prova

Não há biblioteca que resolva "onde será a prova" em edital brasileiro; é extração de texto com
regras de negócio. Foram avaliados:

- **geocoding/Nominatim**: não se aplica — o problema é achar a cidade no texto, não converter
  endereço em coordenadas. Rejeitado.
- **spaCy/NLTK**: dependência pesada para um padrão que é regex sobre frase curta. Rejeitado.
- **Regex ancorada em contexto de prova + lista de UFs** (adotada).

Regras de rejeição derivadas de casos reais do banco: "procedimentos presenciais … na cidade de
Macapá" (heteroidentificação), "horário oficial da cidade de Brasília" (fuso), "lotação … na
cidade de X" (local de exercício).

## 5. Referências consultadas

- Especificação do `pypdf` para `extract_text` (modo padrão x layout).
- Código do próprio projeto: `document_extract.py`, `document_store.record_analysis`,
  `section_requirements.build_logical_document`, `dou_source.py`, `location.py`.
- Dados reais: `blocos_documento`, `propostas_campo`, `ciclos_fontes`, `observacoes_concurso`.
