# Design — Fase 31: OCR controlado, vagas agregadas, requisitos inline

Data: 2026-10-17. Base: Fase 30 publicada (`5d4ef11`), schema v18, 1368 testes.

## 1. Diagnóstico do PDF sem texto

Documento identificado pelo registro, não pelo nome:

| Campo | Valor |
|---|---|
| `document_id` | `b9f1ad9a-6579-4926-8ab1-0d14fe462b5d` |
| Título | "Edital nº 11 - Cumprimento de Decisão Judicial" |
| URL | `https://anexos-r2.selecao.net.br/uploads/747/concursos/485/anexos/122a60ca-…pdf` |
| Concurso | `ibfc-485` (TJPE) |
| `version_id` | `e02eae03-3c12-473a-a285-d5fffdf97a51` |
| SHA-256 | `e0834d70…4b12` |

Evidência do diagnóstico (não suposição):

```
producer: Microsoft: Print To PDF
páginas: 2 | fontes: 0 | spans de texto: 0 | imagens: 0 | desenhos: 4.645
```

**Não é digitalização** (0 imagens), **não é corrupção** (abre e renderiza) e **não é falha do
extrator** (não existe texto para extrair): o texto foi convertido em **contornos vetoriais**.
Só rasterização + OCR recupera.

## 2. OCR: motor escolhido

| Opção | Licença | Instalação | Veredito |
|---|---|---|---|
| **Windows.Media.Ocr** (WinRT, via PowerShell 5.1) | capacidade do SO | **já presente** | **adotado**: `pt-BR` disponível, ~0,5 s/página |
| Tesseract + PyMuPDF | Apache-2.0 + AGPL/comercial | binário + modelo `por` | suportado, não instalado |
| OCRmyPDF | MPL-2.0 (exige Ghostscript AGPLv3) | vários binários | rejeitado: peso e AGPL extra |
| Serviço em nuvem | comercial | chave + custo | rejeitado: dado público, custo e envio externo |

Verificação real em 2026-10-17: `AvailableRecognizerLanguages = ['pt-BR']`. O `pwsh` 7 não
carrega WinRT; o `powershell.exe` (5.1) carrega — por isso o motor usa explicitamente 5.1.

Rasterização: PyMuPDF 1.28.2 (já usado desde a Fase 30), agora **declarado** em
`requirements.txt` com a observação de licença AGPL-3.0 e uso local.

## 3. OCR: contrato e limites

- `availability()` informa motores, idiomas e limites; nunca instala nada.
- `ocr_version(..., apply=False)` (padrão) devolve o plano, sem gerar imagem nem bloco.
- `apply=True` grava **camada derivada**: blocos com `page_number` real, propostas com
  `extraction_method` prefixado `ocr:` e `ambiguity_reason` começando por "texto reconhecido
  por OCR — conferir no documento original".
- O **PDF original nunca é alterado**; o hash é verificado antes e depois.
- Limites: 20 páginas por chamada, DPI 72–400, timeout 5–600 s por página, 40 MiB por imagem.
- Códigos: `ocr_indisponivel`, `ocr_modelo_ausente`, `ocr_timeout`, `ocr_falhou`,
  `ocr_sem_texto`, `ocr_nao_e_pdf`, `ocr_limite_paginas`, `ocr_parametro_invalido`.
- OCR **não** confirma campo: cria candidatos marcados.

## 4. Quadro de vagas com total agregado

Formato real (IBFC, `ibfc-490`): cabeçalho `Total de Vagas (Ampla, Negros e PCD)*`, linhas
`<cargo> NN – Sede: <local> <qtd>`, `TOTAL 228`, e nota `(*) Total de vagas incluindo as
reservadas para pessoas com deficiência e a reserva de vagas para negros`.

Decisão: esse número é `vagas_total_publicado` — **nunca** `immediate_vacancies`,
`indigenous_vacancies` ou `reserve_vacancies`. Distribuir 228 por percentual seria inventar a
abertura que o edital não publica. O campo é novo no modelo interno (aditivo; não entra no
contrato v1).

Verificação do quadro: `soma das linhas` vs `TOTAL publicado`; divergência vira **conflito
declarado** no motivo, não correção silenciosa. Na base real: 27 linhas somam 228 = TOTAL.

Também foi corrigido um risco no extrator genérico: `_field_for("TOTAL DE VAGAS (AMPLA,
NEGROS E PCD)")` mapeava para `immediate_vagancies`; agora devolve `None` (tratado como
agregado).

## 5. Requisitos inline

Formato real (`ibfc-490`): `2.6.2. PROFESSOR … RADIOLOGIA Requisito: Diploma … curso de nível
superior em Enfermagem, em instituição reconhecida pelo MEC.`

`radar/inline_requirements.py`:

- rótulo explícito (`Requisito`, `Escolaridade`, `Formação`, `Habilitação`);
- cargo extraído do **cabeçalho imediatamente anterior no mesmo bloco** — nunca por proximidade
  entre blocos; sem cargo, o motivo diz "requisito sem cargo identificado";
- valor cortado em `Atribuições:` e no próximo item numerado;
- curso extraído com padrão próprio (`curso de nível superior em X`) e filtro de genéricos
  ("instituição", "ensino"), sem depender de `_courses_from` (que capturava "instituição");
- `si_compatibility` sempre como candidato, com o trecho literal.

## 6. Revisão e duplicidades

`review.duplicate_groups` classifica:

- **duplicidade textual**: mesmo bloco, mesma citação e mesmos offsets → candidata a
  consolidação;
- **repetição legítima**: mesmo valor em trechos diferentes (sumário/corpo) → **não** consolidar.

Nada é apagado: rejeitar a redundante é decisão humana append-only. Prioridade ganhou três
fatores declarados (documentados e testados): `vaga_indigena` +4, `formacao_si` +3,
`duplicata` +1. A regra anterior não foi alterada em silêncio.

## 7. Contratos

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/pipeline/ocr` | necessidade de OCR + motor |
| GET | `/api/revisao/duplicidades` | grupos de duplicidade com membros |

CLI: `ocr-pendentes`, `ocr-executar [--apply]`, `revisao-duplicados`. Sem migração (v18).

## Critérios de aceite

- OCR opcional, rastreável, sem alterar o original e sem confirmar campo.
- Total agregado nunca distribuído por modalidade.
- Requisito inline associado ao cargo certo ou marcado como sem cargo.
- Compatibilidade com SI sempre candidata e com evidência.
- Duplicidade textual separada de repetição legítima; nada apagado.
- Contrato v1 intacto; base íntegra; suíte e revisão aprovadas.
