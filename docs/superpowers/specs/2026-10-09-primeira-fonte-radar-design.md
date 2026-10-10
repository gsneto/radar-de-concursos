# Primeira fonte do Radar — desenho de fluxo vertical

Objetivo: demonstrar coleta reproduzível de uma única fonte oficial até uma página local, sem afirmar dados ausentes nem depender de infraestrutura externa.

## Fonte e escopo

Autoridade: Prefeitura Municipal de Guajará-Mirim/RO (SEMED). URL oficial: https://guajaramirim.ro.gov.br/prefeitura-de-guajara-mirim-abre-inscricoes-para-concurso-publico-da-educacao-com-107-vagas-e-cadastro-de-reserva/ . Formato: HTML público. Página acessada no navegador em 2026-10-09; artigo apresenta concurso nº 001/2026, cargos de Professor de Educação Infantil (69), Professor dos Anos Iniciais do Ensino Fundamental (32), Professor Intérprete de Libras (3) e Professor de Braille (3); inscrições realizadas de 10 a 30/07/2026 e existência de cadastro de reserva sem quantitativo. A página liga edital e retificações posteriores: este fluxo coleta somente o que está textual e inequivocamente expresso na própria página, não interpreta os PDFs ligados nem afirma que os detalhes do artigo estão sincronizados com todas as retificações. Números representam vagas dos cargos divulgadas no artigo, não a soma de modalidades; cadastro de reserva e cota indígena numéricos permanecem `null`. A página cita possibilidades de localidade (urbana/rural/Distrito de Surpresa), mas não mapeia local por cargo; local de prova e exercício por registro ficam `null`. Escolaridade exigida permanece `null` até validação de edital e retificações.

## Contrato v1

Cada linha representa um cargo na mesma seleção. Chave natural `(source_url, competition_id, role)`; campos JSON: `competition_id` ("001/2026"), `competition`, `agency`, `role`, `education`, `immediate_vacancies`, `reserve_vacancies`, `indigenous_vacancies`, `registration_start`, `registration_end`, `registration_status`, `exam_date`, `exam_location`, `work_location`, `source_name`, `source_url`, `evidence_url`, `verified_at`. `null` é desconhecido; zero somente se a fonte afirmar zero. Datas conhecidas em ISO `YYYY-MM-DD`, `verified_at` em ISO UTC com offset. `registration_status` é "encerradas conforme período divulgado" apenas se a página apresentar inscrição como realizada e a data final já passou; jamais inferir situação presente de edital não lido. `evidence_url` aponta o artigo efetivamente extraído. Campos desconhecidos não são preenchidos a partir de inferência sobre cargo ou nome do município. Sem elegibilidade calculada e sem totais que somem modalidades.

## Arquitetura e falhas

Python 3, somente biblioteca padrão: `radar/collector.py` baixa URL fixa com HTTPS e timeout/limite de bytes; parser HTML restringe-se ao artigo/trecho reconhecível e falha fechado se estrutura ou fatos esperados não forem encontrados. Fixtures locais (HTML fiel ao trecho oficial e variantes sintéticas nomeadas) exercitam extração sem rede. `radar/storage.py` mantém SQLite local com chave única, UPSERT transacional e horário de última verificação; coleta repetida atualiza sem duplicar. `radar/server.py` serve `/api/concursos` (lista JSON com contrato v1), página estática e recursos locais; somente loopback por padrão. Um comando explícito de coleta lê a URL oficial, persiste somente após parse completo; falha da fonte não apaga dados anteriores nem reporta verificação recente. `web/` inclui HTML, CSS e JS, lê apenas a API local, mostra carregamento/erro/vazio, data e links de procedência, com distinções do domínio e sem `innerHTML` para dados recebidos. Nenhuma coleta automática em background; atualizar manualmente conforme interesse, revalidando artigo e retificações antes de afirmar atualidade.

## Aceitação e verificação

1. Fixture oficial extrai quatro registros 69/32/3/3 e mantém reserva/cota indígena, escolaridade e locais desconhecidos; fixture sintética cobre zero distinto de `null`, local de prova distinto de exercício e documento incompleto.
2. Falha de HTTP, HTML alterado e conteúdo incompleto não gravam registros; segunda coleta sobre a mesma chave não duplica e atualização preserva a chave.
3. API responde a lista persistida e lista vazia, contrato e JSON corretos; servidor entrega a página. Interface demonstra rede real de servidor local, dados, estado vazio e erro, links da fonte e última verificação; não exibe `null` como zero.
4. QA independente valida coleta, persistência, API e interface contra contrato; testes automatizados e inspeção do Git fundamentam conclusão.

Decisão de execução: usuário pediu prosseguir sem aprovação de decisões rotineiras e proibiu commits. O desenho/plano desta fase ficam sem commit; usaremos os quatro agentes configurados via OpenCode com revisão independente no final.
