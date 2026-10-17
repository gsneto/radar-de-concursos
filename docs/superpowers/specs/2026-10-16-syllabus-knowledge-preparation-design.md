# Fase 22 - Conteúdo programático, perfil de conhecimento e preparação

Data: 2026-10-16. Base: `b382a03` (Fase 21), 751 testes OK (baseline confirmada).

## Objetivo

Ligar a infraestrutura documental dos concursos ao módulo de estudos: extrair o **conteúdo
programático** dos editais com evidência, manter um **perfil editável de conhecimentos**,
calcular **cobertura de preparação explicável** e proteger os **dados pessoais** (exportação,
importação, backup e restauração).

## Princípio: dimensões separadas

O sistema mantém **separadas** (nunca fundidas numa pontuação opaca):

| Dimensão | Representação |
|---|---|
| Requisito formal do cargo | `si_compatibility` (Fases 14–15) |
| Conteúdo programático do edital | propostas `conteudo_*` (oficial, com evidência) |
| Conhecimento declarado | `estudo_perfil` (familiaridade subjetiva) |
| Progresso de estudo | `estudo_progresso`/`estudo_sessoes` (Fase 21) |
| Desempenho observado | `estudo_perfil.origem='resultado'` (reservado) |
| Potencial da oportunidade | ranking da Fase 20 (intocado) |
| Preparação estimada | `preparation.coverage` (cobertura explicável) |

Ter cursado Sistemas de Informação **não** é conhecimento declarado; estudar 10 h **não**
comprova domínio; cobertura **não** é probabilidade de aprovação.

## Frente A - Extração do conteúdo programático (`radar/program_content.py`)

Reutiliza o pipeline documental existente: cada item vira uma **proposta** com evidência
(bloco/página/trecho) persistida por `record_analysis` (mesma verificação estrita de citação) e
revisável por `revisoes_campo` (validar/rejeitar). Nada é confirmado automaticamente.

- **Seções reconhecidas** (sobre texto normalizado): `CONTEÚDO PROGRAMÁTICO`, `PROGRAMA DAS
  PROVAS`, `CONHECIMENTOS BÁSICOS/GERAIS/ESPECÍFICOS` (inclusive "BÁSICOS E ESPECÍFICOS"),
  com sufixos ("DAS PROVAS", "POR CARGO") e prefixo "ANEXO N".
- **Níveis**: `conteudo_secao`, `conteudo_disciplina`, `conteudo_topico`, `conteudo_subtopico`.
  A numeração distingue níveis (`1.1` subtópico; `1. TÍTULO` disciplina quando é título em
  maiúsculas; `1 tópico` tópico). Texto corrido é ignorado (precisão > cobertura).
- **Fim de seção**: título de parada (cronograma, inscrições, vagas, requisitos, anexo,
  bibliografia…). Palavras ambíguas que também nomeiam disciplinas ("RECURSOS") exigem
  preposição ("DOS RECURSOS") para não truncar a seção.
- **Estados**: `confirmado` (revisão validada), `rejeitado` (revisão), `extraido_nao_revisado`
  (candidato) e `ambiguo` (tópico sem disciplina de contexto, ou mesma chave com redações
  divergentes sem revisão). `nao_localizado` quando não há seção.
- **Retificações**: as propostas de todas as versões são preservadas; nada é apagado. Uma
  falha de extração **não** marca tópicos antigos como removidos.
- **Limite de segurança**: 400 linhas por seção; ao exceder, a seção é truncada e o estado vira
  `extraido_parcial` (visível), sem inventar conteúdo.

## Frente B - Perfil de conhecimentos (`estudo_perfil`, schema v11)

- **Familiaridade** (`nivel`): `nao_avaliado`, `nao_conheco`, `basico`, `intermediario`,
  `avancado` — avaliação subjetiva e editável.
- **Necessidade de revisão** (`revisar`): coluna própria (0/1), **não** é nível de domínio.
- **Origem** (`origem`): `usuario` ou `resultado` — nunca se confunde declaração com desempenho.
- **Confiança** (`confianca`) e **observações** opcionais.
- Chave estável `conceito_key` = disciplina normalizada + tópico normalizado (sem acentos,
  minúsculas, stopwords removidas). A normalização **sugere** equivalência entre editais, mas
  não a prova: a disciplina faz parte da chave, então "Segurança" em Redes ≠ em Legislação.
- Nada é inferido de formação, cargo, disciplina cadastrada ou tempo de estudo.

## Frente C - Cobertura e perspectivas (`radar/preparation.py`)

`coverage(topics, profile, progresso)` devolve contagens, denominador e `basis` explicando-o.
O denominador são os tópicos **identificados** (confirmados + extraídos; ambíguos, rejeitados e
não extraídos ficam de fora). `sem_perfil` ≠ `nao_conhecidos` (desconhecido não é lacuna
pessoal automática). `pct` é `None` quando não há denominador.

`perspective(...)` classifica em: `boa_aderencia` (formal ok + cobertura ≥60% sem lacunas),
`oportunidade_para_preparar` (formal ok + lacunas), `excepcional_com_lacunas` (formal ok +
fatores excepcionais do ranking + lacunas), `exige_confirmacao` (formal ambíguo/não extraído ou
cobertura não calculável) e `compatibilidade_desfavoravel`. O ranking da Fase 20 **não** é
recalculado; a perspectiva é uma dimensão adicional.

## Frente D - Lacuna → plano de estudos

`knowledge_store.send_gap_to_study(db, contest_id, conceito_key)` cria (idempotente) a
disciplina/tópico no módulo de estudos existente, reutilizando `study_store`; não duplica.

## Frente E - Portabilidade (`radar/study_backup.py`)

- **Exportação** JSON versionada (`format=radar-estudos`, `format_version=1`, `schema_version`,
  `exported_at`, `counts`) apenas dos dados pessoais de estudo (disciplinas, tópicos, progresso,
  sessões, revisões, perfil). Não exporta o acervo documental.
- **Validação** antes de gravar, incluindo campos obrigatórios por entidade.
- **Importação** com `dry_run`, idempotente, preserva dados existentes, reporta conflitos,
  trata FKs ausentes (tópico-pai → raiz; sessão → sem vínculo) sem abortar, e **materializa** o
  tempo de sessão aberta ao finalizá-la.
- **Backup** consistente via API do SQLite (`Connection.backup`) + `PRAGMA integrity_check`;
  recusa destino igual à origem. **Restauração** para banco isolado com verificação.

## API, CLI e interface

- `GET /api/estudos/conteudo?contest_id=`, `GET /api/estudos/preparacao?contest_id=`,
  `GET/POST/DELETE /api/estudos/perfil`, `POST /api/estudos/lacuna`,
  `GET /api/estudos/exportar`, `POST /api/estudos/importar`.
- CLI: `estudos-conteudo`, `estudos-perfil`, `estudos-cobertura`, `estudos-exportar`,
  `estudos-importar`, `estudos-backup`.
- Interface: seção **Preparação e conteúdo programático** (`#prep-panel`, `#perfil-panel`) com
  seletor de concurso, cobertura, estados, páginas, lacunas, "Enviar para estudos" e perfil.

## Compatibilidade

- Contrato v1 (18 campos) **inalterado**; `/api/concursos/{id}/detalhes` não reporta mais
  "conflitos" falsos de conteúdo (campos `conteudo_*` são multi-item).
- Migração **aditiva** v10→v11 (só cria `estudo_perfil`); base real migrada com backup.
- Nenhuma dependência nova (stdlib-only).

## Limitações

- A extração é **conservadora**: seções com formato muito incomum podem não ser reconhecidas
  (`nao_localizado`); preferiu-se precisão a cobertura.
- A base real ainda **não** tem propostas de conteúdo (as versões foram analisadas antes desta
  fase); a extração ocorre nas próximas análises de documentos.
- Não há flashcards/questões nem sincronização entre dispositivos.
