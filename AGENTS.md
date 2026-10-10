# Radar de Concursos — regras compartilhadas

O usuário conversa com o orquestrador do OpenCode para desenvolver um radar de concursos públicos brasileiros. A configuração dos agentes foi validada na fase 2; a fase 3 implementa um único fluxo vertical mínimo conforme `docs/superpowers/specs/2026-10-09-primeira-fonte-radar-design.md`. O desenho original da orquestração permanece em `docs/superpowers/specs/2026-10-09-radar-orquestracao-opencode-design.md` como histórico.

## Fontes e precedência

Documentos canônicos do produto e contratos acordados definem regras específicas de domínio; estas regras compartilhadas valem para todos os agentes; definições de cada agente delimitam seu papel; prompts delegados detalham tarefas concretas sem ampliar permissões nem revogar contratos. Inspecione a stack e arquivos antes de presumir tecnologia.

## Regras de domínio

- Distinguir vagas imediatas de cadastro de reserva; local de prova de local de exercício; zero de valor desconhecido.
- Não somar modalidades ou localidades sem regra de contagem validada; manter cargo, especialidade e cotas separados quando exigido pela fonte.
- Preservar fonte oficial, evidência e data da última verificação; registrar histórico de retificações. Informação extraída por IA não fica confirmada automaticamente.
- Não apresentar informação antiga como atual; não inventar vagas, datas ou informações ausentes.
- Verificar requisitos documentados antes de considerar uma formação compatível com um cargo, inclusive bacharelado em Sistemas de Informação.
- Preservar preferências configuráveis, inclusive oportunidades indígenas e deslocamento desde Paulo Afonso, Bahia.

## Execução segura

Inspecionar Git e alterações locais antes de editar. Criar prompts específicos antes de cada delegação; conferir arquivos, diffs, comandos e testes reais após retornos. Não aprovar com base em relato de subagente. Não versionar segredos nem imprimir credenciais. Não fazer push, merge em `main`, publicação, exclusão irreversível ou migração destrutiva sem autorização explícita. Não declarar testes aprovados sem execução.
