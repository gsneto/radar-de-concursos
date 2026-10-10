# OpenCode e Superpowers

O OpenCode 1.18.35 está instalado com plugin global `superpowers@git+https://github.com/obra/superpowers.git`; não copiamos nem alteramos sua implementação. A skill `brainstorming` foi carregada nesta sessão antes do desenho, e `writing-plans` e `executing-plans` orientaram esta fase. Disponibilidade em sessões futuras deve ser verificada via `opencode debug skill` ou ferramenta `skill` daquela sessão.

Superpowers fornece metodologia, enquanto `AGENTS.md`, os contratos do projeto e permissões locais fixam limites de domínio/execução. Aplicar skills pertinentes, não todas indiscriminadamente: brainstorming para criação/arquitetura; writing-plans para plano; test-driven-development para alterações de comportamento; systematic-debugging para falhas; revisão e verification-before-completion para evidência. Para alterações simples, seguir a classificação real da skill em vez de inventar etapas.

Cada especialista consulta skills efetivamente disponíveis na sua própria sessão. O orquestrador identifica o que é aplicável e inclui isso no prompt específico; não pressupõe propagação automática do conteúdo de skills. Configuração só recarrega em novo processo OpenCode.
