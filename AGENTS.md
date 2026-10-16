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

Inspecionar Git e alterações locais antes de editar. Criar prompts específicos antes de cada delegação; conferir arquivos, diffs, comandos e testes reais após retornos. Não aprovar com base em relato de subagente. Não versionar segredos nem imprimir credenciais. Não declarar testes aprovados sem execução.

## Política de autonomia Git

O usuário autoriza commits e pushes **rotineiros** sem confirmação individual. Ao concluir uma etapa:

1. Executar os testes pertinentes e as verificações de segurança.
2. Conferir o diff, a branch atual e o estado do repositório.
3. Se estiver tudo aprovado, criar um commit com mensagem descritiva e fazer push para a **branch de trabalho e o remoto já configurados**.
4. Verificar o resultado real do push e registrar hash, testes, branch e situação do repositório.
5. Se houver falhas, credenciais expostas, conflitos inesperados ou risco de perda de trabalho, **interromper a operação afetada e reportar**.

Continuam exigindo **autorização específica** (nunca implícita): merge em `main`, deploy, publicação em outro destino, exclusão irreversível/destrutiva, force-push, troca de repositório remoto e migração da base de produção real. Nunca afirmar que publicou sem confirmação do Git.
