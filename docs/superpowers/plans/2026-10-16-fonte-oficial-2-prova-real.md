# Prova real — segunda fonte oficial (DOU Seção 3)

Data da execução: 2026-10-16

## Fonte e método

- Fonte: Diário Oficial da União (Imprensa Nacional), **Seção 3** ("contratos,
  editais e avisos", que inclui concursos públicos).
- URL consultada: `https://www.in.gov.br/leiturajornal?data=01-10-2026&secao=do3`
- Método: leitura pública por HTTPS (`urllib`), User-Agent de navegador, limite de
  8 MB, decodificação UTF-8 → Windows-1252. A página embute o JSON oficial das
  matérias do dia; nenhum endpoint privado, autenticação ou contorno de bloqueio.

## Resultado observado (real)

| Item | Valor |
|---|---|
| HTTP | 200 |
| Tamanho da edição | 2.527.888 caracteres |
| Tempo do fetch | ~36 s |
| Matérias na edição | 2414 |
| Matérias com "concurso" (filtro por conteúdo) | 14 |
| Candidatos documentais (dedup por URL) | 14 |
| Documentos processados na prova | 6 |
| Banco | temporário (`%TEMP%\dou-proof-*\dou-proof.sqlite3`) |

Documentos processados (5 `edital`, 1 `outro`), com versão gravada e hash SHA-256:

```
edital  sha256=0eef3f432196...  ext=parcial  https://www.in.gov.br/web/dou/-/edital-de-30-de-setembro-de-2026-735872523
edital  sha256=e597e6b7e87d...  ext=parcial  https://www.in.gov.br/web/dou/-/edital-progep-n-78/2026-735811244
edital  sha256=21d25747f09f...  ext=parcial  https://www.in.gov.br/web/dou/-/edital-n-6-de-30-de-setembro-de-2026-735955420
edital  sha256=ec2f3341cc93...  ext=parcial  https://www.in.gov.br/web/dou/-/edital-de-29-de-setembro-de-2026-735965407
edital  sha256=a2eeed4e0676...  ext=parcial  https://www.in.gov.br/web/dou/-/edital-de-convocacao-n-21/2026/cref3/sc-736001220
outro   sha256=eb756a3d954c...  ext=parcial  https://www.in.gov.br/web/dou/-/extrato-de-contrato-n-17/2026-uasg-370003-735955914
```

## Idempotência e integridade

- **Repetição**: reexecutar o mesmo `discover`/`register_document`/`record_version`
  manteve **6 → 6 documentos** e **6 → 6 versões** (deduplicação por
  `UNIQUE(document_id, sha256)` e por `comparison_sha256`).
- **Sem promoção automática**: `revisoes_campo = 0` e `valores_atuais = 0`; nenhuma
  proposta virou fato confirmado.
- **v1 intocado**: a tabela `concursos` (contrato de 18 campos) **não** é usada pela
  fonte DOU; a prova não criou nem alterou dados v1.
- **Integridade de vagas em dados reais**: entre as 14 matérias de concurso, uma
  contém "CADASTRO DE RESERVA" **sem número**; a extração conservadora **não** emitiu
  `reserve_vacancies = 0` nem qualquer quantidade — o valor permanece desconhecido,
  como exige a regra. Nenhuma das 6 matérias processadas continha as frases
  explícitas exigidas (por exemplo, "N vagas para pessoas indígenas"), então
  **nenhuma proposta foi fabricada** (0 propostas).

## Associação de retificações

Nesta edição não havia retificação de concurso com número de edital referenciável.
A associação automática de retificações permanece **não comprovada** com documento
real e, por decisão de projeto, não é feita automaticamente: o vínculo continua
exigindo revisão humana (`documents-link-amendment`), preservando o contrato de
revisão e evitando associações falsas por semelhança de título.

## Limitações observadas

- A interface "Leitura do Jornal" é pública mas **não é uma API versionada**; o
  fetch é lento (~36 s por edição de ~2,5 MB) e pode variar. O adaptador falha
  fechado e o monitoramento registra a falha sem inventar dados.
- O `content` é um recorte textual da matéria; a publicação **certificada (PDF)**
  prevalece. A extração é conservadora e nada é confirmado sem revisão humana.
- PDFs/anexos do DOU não foram baixados nesta prova.

## Reprodução

Script de prova: `%TEMP%\opencode\dou_proof.py` (fora do repositório). Ele tenta o
fetch ao vivo e, em caso de indisponibilidade, usa a cópia real salva obtida por
HTTPS da mesma URL. A suíte de testes cobre o adaptador sem depender da internet
(`tests/test_dou_source.py`, `tests/test_monitoring.py`).
