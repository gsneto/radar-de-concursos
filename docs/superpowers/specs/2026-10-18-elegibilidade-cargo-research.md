# Pesquisa — Fase 38: elegibilidade por cargo, escopo e vagas indígenas

Data da consulta: **2026-10-18**. Objetivo: resolver os problemas reais da fase — requisito
por cargo, escopo de reserva, leitura de quadro de vagas em PDF — sem dependência nova.

## 1. Entity resolution de cargos e especialidades

O projeto já tem o mecanismo da Fase 35 (`role_identity`): pontuação estrutural (nome, código,
prefixo, especialidade) e decisão humana append-only. A fase **não** cria outro resolvedor.

O que faltava era o casamento entre **documentos** do mesmo concurso: a tabela de vagas usa
"208 Profissional de Suporte Técnico (PST)-Assistente de T.I." e o requisito usa
"208 PROFISSIONAL..." (caixa diferente). A solução adotada é normalização determinística do
rótulo (`normalize_role`), não similaridade: dois rótulos que normalizam igual são o mesmo
escopo; os demais continuam pendentes de decisão humana.

## 2. Classificação de requisitos por evidência

Abordagens examinadas:

- **Modelo de linguagem** para classificar requisitos. Descartado: não auditável, não
  reproduzível e exigiria serviço externo.
- **Listas de palavras-chave** (o que o projeto já usa). Mantido, com duas guardas novas
  derivadas do texto: marcador de formação e marcador de área de computação.
- **Regras de escopo** (cargo × concurso). Adotadas: é o ponto central da fase.

A classificação continua em `edital_requirements.classify_si_compatibility`; a elegibilidade
apenas interpreta o estado com precedência explícita.

## 3. Modelagem de escopo concurso × cargo

Padrão adotado: **todo fato tem escopo declarado** (`scope`), e a matriz nunca promove um fato
de escopo mais amplo para um mais estreito. É o mesmo princípio de grão em modelagem
dimensional: um total no grão "concurso" não é distribuído ao grão "cargo" sem uma tabela que
faça essa distribuição.

Estados explícitos para a reserva indígena tornam a distinção visível: `cargo_imediata`,
`cargo_sem_imediata_com_reserva`, `concurso_imediata_sem_distribuicao`,
`distribuido_por_cargo`.

## 4. Leitura de quadro de vagas em texto de PDF

PDFs de banca publicam o quadro como texto (não como tabela estruturada). Abordagens:

- **Extração de tabela do PDF** (`pymupdf`/`pdfplumber`): já usada em outros layouts, mas
  dependente da detecção de linhas; falha em quadros desenhados com espaços.
- **Parser posicional por cabeçalho** (adotado): localiza o cabeçalho pelas modalidades e lê
  uma célula por coluna. Determinístico, testável e independente da geometria do PDF.

Guardas contra falsos positivos: âncora colada ao cabeçalho, cabeçalho compacto, exigência de
AMPLA + INDÍGENA + TOTAL, número de células igual ao de colunas, e rejeição de numeração de
tópicos ("1.", "2.").

## 5. Sistemas explicáveis de recomendação

Padrão adotado: **estado exclusivo + motivo textual + evidência**, em vez de pontuação. É a
mesma escolha das fases 34–37 (prontidão explicável, prioridade por tupla). Um score único
esconderia diferenças entre "requisito sustenta", "exige interpretação" e "incompatível".

## 6. Proveniência e revisão humana

Mantido o modelo documento → versão → bloco → evidência → proposta → decisão. A matriz cita
proposta, documento, página e trecho; a decisão continua em `review.decide_proposal`
(append-only). Nenhuma tabela paralela.

## 7. Reconciliação entre edital e retificação

A matriz usa todas as propostas abertas do cargo (edital + retificações) e mostra as duas
leituras quando divergem; não escolhe a mais recente. A auditoria de prazo da Fase 37 já cobre
a retificação que altera ou repete valor.

## 8. Avaliação de precisão e cobertura

Sem conjunto rotulado, a avaliação é por **casos de teste determinísticos**: cargo compatível e
incompatível no mesmo concurso, categoria sustentada, correlato, outra formação, reserva por
cargo, reserva só do concurso, "CR", total agregado, cargo não reconciliado. O caso TJSC é o
teste de integridade semântica ponta a ponta.

## 9. Fontes oficiais consultadas (referência, não coleta)

- Página FGV do concurso: https://conhecimento.fgv.br/concursos/tjscjuiz26
- Edital: https://conhecimento.fgv.br/sites/default/files/concursos/edital-n-33-2026-edital-de-abertura.pdf
- Notícia TJSC: https://www.tjsc.jus.br/web/imprensa/-/tjsc-lanca-novo-concurso-publico-para-ingresso-na-carreira-da-magistratura

A verificação usou o documento **já armazenado** (sha256 `85bd7cfe…`), comparado na Fase 37 com
o servido hoje (`fonte_inalterada`). Nenhuma coleta nova foi feita nesta fase.

## 10. O que foi rejeitado

- Modelo de linguagem para classificar requisitos: não auditável.
- Fundir rótulos por similaridade: proibido pelo projeto; normalização exata apenas.
- Distribuir a reserva indígena do concurso por cargo: inventaria dados.
- Tratar "CR" ou "-" como zero: inventaria quantidade.
- Criar uma segunda tela de revisão: a matriz complementa a mesa.
