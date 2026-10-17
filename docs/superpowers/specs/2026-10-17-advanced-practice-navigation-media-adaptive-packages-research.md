# Pesquisa — Fase 24: adaptação, imagens e pacotes

Data: 2026-10-17. Pesquisa documental e de bibliotecas; nada foi copiado para o repositório.

## 1. Seleção adaptativa de questões

| Abordagem | O que exige | Decisão |
|---|---|---|
| TRI / IRT (3PL, Rasch) | parâmetros calibrados por item, amostra grande, software dedicado | **Rejeitada**: sem calibração seria precisão inventada |
| Elo / Glicko | rating por item e por usuário, atualização contínua | **Rejeitada para v1**: segundo modelo de habilidade conflita com o perfil declarado |
| BKT / knowledge tracing | modelo treinado por habilidade, dados sequenciais | **Rejeitada**: exigiria treino e validação que o produto não tem |
| Heurística ponderada determinística | histórico local, pesos explícitos, desempate estável | **Adotada** (`adaptive_v1`) |

Regras adotadas: erro recente pesa mais que erro antigo (janela de 8 tentativas); tópico nunca
praticado pesa; revisão atrasada usa 14/28 dias; lacuna declarada no perfil pesa; dificuldade
declarada ajusta levemente. Menos de 3 tentativas ⇒ confiança **baixa** e peso de erro limitado.

Consequência declarada: percentual de sessão adaptativa **não** é comparável ao de simulado de
conjunto fixo; isso aparece na API (`aviso`) e na UI.

## 2. Imagens

- `imghdr` foi **removido no Python 3.13** (PEP 594). Depender dele quebraria o projeto na
  próxima versão do runtime.
- **Pillow** não está no runtime e adicionaria dependência binária; desnecessário para validar
  formato e dimensões.
- Validação por **assinatura** + leitura de cabeçalho:
  - PNG: assinatura `89 50 4E 47 0D 0A 1A 0A` + `IHDR` com largura/altura plausíveis;
  - JPEG: `FF D8 FF` + varredura até `SOFn`;
  - GIF: `GIF87a`/`GIF89a` + dimensões;
  - WebP: `RIFF....WEBP` + `VP8/VP8L/VP8X`.
- **SVG recusado**: é XML e pode carregar script; não há sanitizador no runtime.
- Armazenamento por hash fora do webroot, com `Content-Type` fixo e `nosniff`, evita execução de
  conteúdo enviado pelo usuário e path traversal.

## 3. Pacotes

- **Anki `.apkg`**: formato SQLite comprimido com semântica de baralho, modelos e agendamento;
  importar exigiria mapear dezenas de campos e aceitar conteúdo de licença desconhecida.
  **Rejeitado** para v1.
- **QTI**: XML extenso, perfis por fornecedor, sem vantagem para o caso de uso.
  **Rejeitado**.
- **JSON + ZIP com manifesto**: auditável, versionável, testável; permite prévia e `dry_run`.
  **Adotado** (`radar-pacote` v1).
- Ameaças tratadas: **Zip-Slip** (normalização de nome), **zip bomb** (limites de tamanho real,
  total, quantidade e razão), mídia inválida (assinatura) e licença não declarada (aviso).

## 4. Alternativas descartadas nesta fase

- Importar bancos comerciais: risco de licença e de dados não verificados.
- Sincronização em nuvem: exigiria autenticação e infraestrutura fora do escopo local.
- Estimativa de nota/probabilidade: sem base estatística; seria promessa falsa.
- Editor rico de questões: o formato atual (enunciado + alternativas + gabarito) cobre o uso.

## 5. Referências consultadas

- Python 3.13 — remoção de módulos da PEP 594 (`imghdr`).
- Especificações públicas de PNG (IHDR), JPEG (marcadores SOF), GIF (descritor lógico) e WebP
  (RIFF/VP8).
- Documentação de `zipfile` sobre nomes de membros e limites de leitura.
- Literatura geral sobre TRI e Elo — usada apenas para justificar a **não** adoção no v1.
