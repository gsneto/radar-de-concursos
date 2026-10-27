"""Contrato de API do Radar de Concursos (Fase 44).

O servidor é stdlib e não usa framework com OpenAPI. Este módulo é a especificação
equivalente, versionada e verificável: cada rota do servidor tem uma entrada com método,
parâmetros, corpo, efeitos, idempotência e resumo. `verify()` compara o registro com as
rotas realmente declaradas em `radar/server.py`, então uma rota nova sem contrato quebra o
teste — documentação e código não divergem em silêncio.

Convenções gerais (válidas para todas as rotas):

- Transporte: HTTP/1.1 em loopback (127.0.0.1), JSON UTF-8.
- Erros: sempre ``{"error": "<mensagem curta>"}``; nunca traceback, caminho local ou segredo.
- Sucesso de leitura: 200 com JSON. Recurso inexistente: 404 sem corpo.
- Validação: 400 para parâmetro/corpo inválido; 415 para corpo não JSON; 403 para origem
  ou Host não loopback; 429 para consulta pesada concorrente; 405 com ``Allow`` para
  método não suportado; 503 para schema pendente.
- Escrita: ``Content-Type: application/json`` obrigatório quando há corpo; ``Origin``, se
  presente, precisa ser loopback na mesma porta. Não há autenticação: o produto é local.
- Paginação: ``limit``/``offset`` quando declarados, com faixa validada pela rota.
- Idempotência: decisões e finalizações repetidas devolvem o mesmo resultado sem duplicar
  registros; importações são transacionais.
"""

from __future__ import annotations

import ast
import io
import re

VERSION = "api_contract_v1"

# (método, caminho documentado, domínio, query, corpo, escrita, idempotência, resumo)
_ENTRIES = [
    # --- Concursos, identidade e oportunidades ---------------------------------
    ("GET", "/api/concursos", "concursos", "", "", False, "n/a",
     "Contrato público v1: lista de concursos com 18 campos, lida de list_records."),
    ("GET", "/api/concursos/{contest_id}/detalhes", "concursos", "", "", False, "n/a",
     "Alias versionado do detalhe documental (UUID validado)."),
    ("GET", "/api/concursos/identidades", "concursos", "", "", False, "n/a",
     "Identidades canônicas de concurso (inclui containers de fonte marcados)."),
    ("GET", "/api/identidade", "concursos", "", "", False, "n/a",
     "Relatório de identidade documental e pendências de reconciliação."),
    ("POST", "/api/identidade/reparar", "concursos", "", "dry_run", True, "sim",
     "Repara vínculos de identidade comprovados; dry_run por padrão."),
    ("GET", "/api/oportunidades", "concursos",
     "conflict,contest_id,document_state,field,has_page,limit,min_priority,offset,search",
     "", False, "n/a", "Fila de oportunidades documentais com filtros combináveis."),
    ("GET", "/api/oportunidades/{role_id}", "concursos", "scope", "", False, "n/a",
     "Dossiê de uma oportunidade (concurso + cargo + escopo)."),
    ("GET", "/api/linha-do-tempo", "concursos", "limit,since", "", False, "n/a",
     "Linha do tempo de eventos documentais, mais recente primeiro."),
    ("GET", "/api/campos-decisivos", "concursos", "contest_id,limit", "", False, "n/a",
     "Cobertura dos campos decisivos por concurso, com estado explícito."),
    ("GET", "/api/quadro-vagas", "concursos", "contest_id,version_id", "", False, "n/a",
     "Quadro de vagas por colunas e modalidades, com validação aritmética."),
    ("GET", "/api/lacunas", "concursos", "limit", "", False, "n/a",
     "Lacunas de dados agrupadas por campo e motivo, sem inventar valor."),

    # --- Documentos e pipeline -------------------------------------------------
    ("GET", "/api/pipeline", "pipeline", "", "", False, "n/a",
     "Visão do pipeline documental por etapa, com contagens reais."),
    ("GET", "/api/pipeline/cobertura", "pipeline", "limit", "", False, "n/a",
     "Cobertura de documentos por concurso e estado de conferência."),
    ("GET", "/api/pipeline/continuidade", "pipeline", "", "", False, "n/a",
     "Continuidade de tabelas entre páginas e versões."),
    ("GET", "/api/pipeline/documentos", "pipeline", "contest_id,limit,pending", "", False,
     "n/a", "Documentos pendentes ou processados, com motivo por estado."),
    ("GET", "/api/pipeline/duplicidades", "pipeline", "limit", "", False, "n/a",
     "Duplicidades documentais candidatas, sem fusão automática."),
    ("GET", "/api/pipeline/escopo-regional", "pipeline", "", "", False, "n/a",
     "Escopos regionais identificados e sua evidência."),
    ("GET", "/api/pipeline/ocr", "pipeline", "limit", "", False, "n/a",
     "Versões sem texto e elegibilidade para OCR opcional."),
    ("GET", "/api/pipeline/parciais", "pipeline", "limit", "", False, "n/a",
     "Versões parcialmente extraídas, com decisão de processar páginas restantes."),
    ("GET", "/api/documentos/bloqueados", "documentos", "contest_id,limit,state", "", False,
     "n/a", "Aquisição bloqueada por política/robots/HTTP, com alternativas."),
    ("GET", "/api/documentos/nominais", "documentos", "limit,offset", "", False, "n/a",
     "Listas nominais detectadas; corpo não é baixado nem extraído."),
    ("GET", "/api/documentos/nominais-destino", "documentos",
     "contest_id,destination,limit,offset", "", False, "n/a",
     "Destino operacional das listas nominais."),
    ("GET", "/api/editais-faltantes", "documentos", "limit,source", "", False, "n/a",
     "Concursos sem edital localizado, com próxima ação de coleta."),
    ("POST", "/api/documentos/importar", "documentos", "",
     "document_id,declared_origin,channel,content_base64,dry_run", True, "condicional",
     "Ingestão manual controlada, com procedência declarada e hash."),
    ("POST", "/api/documentos/reprocessar", "documentos", "",
     "version_ids,dry_run,limit", True, "sim",
     "Reprocessa versões com a versão atual do extrator, sem duplicar propostas."),
    ("POST", "/api/documentos/tipos", "documentos", "",
     "document_id,tipo_documental,reviewer,reason", True, "sim",
     "Reclassifica o tipo documental com justificativa registrada."),

    # --- Cobertura, confirmação e associações ----------------------------------
    ("GET", "/api/cobertura", "cobertura", "", "", False, "n/a",
     "Cobertura de conferência por concurso."),
    ("GET", "/api/cobertura/estados", "cobertura", "limit", "", False, "n/a",
     "Estados de cobertura documental por concurso."),
    ("GET", "/api/cobertura/resumo", "cobertura", "", "", False, "n/a",
     "Resumo agregado de cobertura e pendências."),
    ("POST", "/api/cobertura/papeis", "cobertura", "",
     "contest_id,role_id,state,reviewer,note", True, "sim",
     "Registra conferência de escopo por cargo, sem confirmar campos."),
    ("GET", "/api/confirmacao", "confirmacao", "", "", False, "n/a",
     "Estado da fila de confirmação documental."),
    ("GET", "/api/associacoes", "associacoes", "", "", False, "n/a",
     "Associações documento↔concurso e seu estado."),
    ("GET", "/api/associacoes/fila", "associacoes", "limit,state", "", False, "n/a",
     "Fila de associações pendentes de revisão."),
    ("POST", "/api/associacoes/{association_id}", "associacoes", "",
     "action,reviewer,reason", True, "sim",
     "Confirma ou rejeita uma associação documental."),

    # --- Revisão humana --------------------------------------------------------
    ("GET", "/api/revisao/fila", "revisao",
     "conflict,field,limit,min_priority,offset,reviewed_since,reviewed_until,search,source,"
     "state,until", "", False, "n/a", "Fila de propostas para revisão humana."),
    ("GET", "/api/revisao/grupos", "revisao",
     "contest_id,contexto,document_id,field,limit,linha,offset,state,version_id", "", False,
     "n/a", "Propostas agrupadas pela identidade da evidência (versão, bloco, offsets)."),
    ("GET", "/api/revisao/pilotos", "revisao", "", "", False, "n/a",
     "Concursos com linhas de quadro prontas para o piloto de revisão."),
    ("GET", "/api/revisao/piloto", "revisao", "contest_id,size", "", False, "n/a",
     "Relatório do piloto: fichas, progresso e próximos pendentes."),
    ("GET", "/api/revisao/identidades", "revisao", "contest_id", "", False, "n/a",
     "Sugestões de identidade cargo+formação, sem criar identidade."),
    ("GET", "/api/revisao/evidencia/{evidence_id}", "revisao", "", "", False, "n/a",
     "Trecho literal e contexto da evidência."),
    ("GET", "/api/revisao/lotes/{batch_id}", "revisao", "", "", False, "n/a",
     "Estado e progresso de um lote de revisão."),
    ("GET", "/api/revisao/lotes/{batch_id}/exportar", "revisao", "", "", False, "n/a",
     "Exporta o lote para decisão offline, com hash de evidência."),
    ("POST", "/api/revisao/lotes", "revisao", "",
     "created_by,size,filters", True, "nao",
     "Abre lote determinístico de propostas pendentes."),
    ("POST", "/api/revisao/lotes/{batch_id}", "revisao", "",
     "action,reviewer,reason", True, "condicional",
     "Fecha/importa lote; não aprova em massa."),
    ("GET", "/api/revisao/proposta/{proposal_id}", "revisao", "", "", False, "n/a",
     "Detalhe da proposta, com evidência, hash e histórico de decisões."),
    ("POST", "/api/revisao/proposta/{proposal_id}", "revisao", "",
     "decision,reviewer,reason,value,evidence_sha256,scope_snapshot,lote_id", True,
     "sim", "Decisão humana de um único campo, com hash da evidência vista."),
    ("POST", "/api/revisao/selecionar", "revisao", "",
     "proposal_id,reviewer,reason", True, "sim",
     "Seleciona valor vigente após validação explícita."),
    ("POST", "/api/revisao/importar", "revisao", "", "payload,dry_run", True, "sim",
     "Importa decisões de lote de forma transacional e idempotente."),
    ("GET", "/api/revisao/duplicidades", "revisao", "contest_id,field,limit", "", False,
     "n/a", "Duplicidades textuais candidatas, sem fusão automática."),
    ("GET", "/api/reconciliacao", "reconciliacao",
     "contest_id,limit,min_candidates,nature,offset,state", "", False, "n/a",
     "Candidatos de reconciliação de identidade de cargo."),
    ("GET", "/api/reconciliacao/historico", "reconciliacao", "", "", False, "n/a",
     "Histórico append-only de reconciliações."),
    ("POST", "/api/reconciliacao", "reconciliacao", "",
     "contest_id,label,state,reviewer,reason,role_id,nature,evidence,previous_id,dry_run",
     True, "sim", "Reconcilia rótulo de cargo com identidade canônica."),

    # --- Elegibilidade, carteira e prioridades ---------------------------------
    ("GET", "/api/elegibilidade", "elegibilidade",
     "conflict,conflito,contest_id,eligibility,identity,indigenous,limit,offset,profile,"
     "role_id,search,si,temporal,uf", "", False, "n/a",
     "Matriz de elegibilidade por cargo, formação e reserva indígena."),
    ("GET", "/api/elegibilidade/destaques", "elegibilidade", "limit,profile", "", False,
     "n/a", "Destaques de elegibilidade para um perfil."),
    ("GET", "/api/elegibilidade/pendentes", "elegibilidade",
     "cause,contest_id,limit,offset", "", False, "n/a",
     "Pendências de elegibilidade com causa e próxima ação."),
    ("GET", "/api/elegibilidade/revisao", "elegibilidade", "limit,profile", "", False,
     "n/a", "Revisão de compatibilidade de formação."),
    ("GET", "/api/carteira", "carteira",
     "conflito,contest_id,documental,indigena,limit,offset,prazo,prontidao,role_id,search,si,"
     "uf", "", False, "n/a", "Carteira operacional de oportunidades com prioridade explicada."),
    ("GET", "/api/carteira/destaques", "carteira", "limit", "", False, "n/a",
     "Destaques da carteira."),
    ("GET", "/api/carteira/dossie", "carteira", "role_id,scope", "", False, "n/a",
     "Dossiê completo de uma oportunidade da carteira."),
    ("GET", "/api/prioridades", "prioridades", "limit", "", False, "n/a",
     "Prioridades operacionais calculadas por política determinística."),
    ("GET", "/api/triagem", "triagem", "include_seen,limit", "", False, "n/a",
     "Triagem de alertas e pendências operacionais."),

    # --- Prazos e conflitos ----------------------------------------------------
    ("GET", "/api/prazos", "prazos", "contest_id,group,limit,offset,state", "", False,
     "n/a", "Prazos por grupo e estado temporal."),
    ("GET", "/api/prazos/auditoria", "prazos", "cause,contest_id,group,limit,offset", "",
     False, "n/a", "Auditoria de conflitos de prazo entre documentos/versões."),
    ("GET", "/api/prazos/calendario", "prazos",
     "contest_id,group,limit,offset,state,urgency", "", False, "n/a",
     "Calendário de prazos com urgência calculada no servidor."),
    ("GET", "/api/prazos/caso", "prazos", "escopo", "", False, "n/a",
     "Caso de prazo com evidências e explicação."),
    ("GET", "/api/prazos/revalidacao", "prazos", "limit", "", False, "n/a",
     "Alvos de revalidação de prazo e política da fonte."),
    ("GET", "/api/prazos/revalidacao/historico", "prazos",
     "contest_id,group,limit,offset", "", False, "n/a",
     "Histórico append-only de revalidações."),
    ("POST", "/api/prazos/revalidacao", "prazos", "", "limit,apply", True, "condicional",
     "Executa revalidação de prazos; apply=False apenas simula."),
    ("POST", "/api/prazos/verificar-documento", "prazos", "",
     "version_id,contest_id,group,escopo,dry_run,checked_by", True, "condicional",
     "Verifica um documento oficial já armazenado, sem baixar conteúdo novo."),
    ("GET", "/api/conflitos", "conflitos", "contest_id,limit", "", False, "n/a",
     "Conflitos entre versões documentais."),
    ("GET", "/api/conflitos-revisao", "conflitos",
     "cause,contest_id,field,limit,offset,priority", "", False, "n/a",
     "Conflitos classificados com causa e próxima ação."),

    # --- Fontes, monitoramento, saúde e alertas --------------------------------
    ("GET", "/api/fontes", "fontes", "", "", False, "n/a",
     "Catálogo de fontes com política de persistência e estado real."),
    ("GET", "/api/fontes/{source_id}", "fontes", "", "", False, "n/a",
     "Detalhe da fonte: política por tipo, consumo e revisões."),
    ("GET", "/api/fontes-consumo", "fontes", "limit,source_id", "", False, "n/a",
     "Consumo por fonte (chamadas, créditos, custo) e último resultado."),
    ("GET", "/api/monitoramento", "monitoramento", "", "", False, "n/a",
     "Ciclos de monitoramento, fontes e pendências."),
    ("GET", "/api/saude", "saude", "", "", False, "n/a",
     "Saúde operacional: config, banco, fontes, fila, alertas e último ciclo."),
    ("GET", "/api/saude/prontidao", "saude", "", "", False, "n/a",
     "Relatório único de prontidão do backend com evidência por critério."),
    ("GET", "/api/alertas", "alertas", "limit,unseen", "", False, "n/a",
     "Alertas persistentes, com contagens."),
    ("POST", "/api/alertas/{alert_id}", "alertas", "",
     "action,until", True, "sim",
     "Marca visto/adiado/reaberto/dispensado; não apaga histórico."),
    ("GET", "/api/preferencias", "preferencias", "", "", False, "n/a",
     "Preferências operacionais do usuário."),
    ("POST", "/api/preferencias", "preferencias", "",
     "reference_municipio,reference_uf,interest_states,practical_distance_km,priority", True,
     "sim", "Atualiza preferências usadas na priorização."),

    # --- Estudos: sessões, progresso e conteúdo --------------------------------
    ("GET", "/api/estudos/painel", "estudos", "", "", False, "n/a",
     "Painel de estudos: disciplinas, tópicos, progresso, tempo e revisões."),
    ("GET", "/api/estudos/disciplinas", "estudos", "", "", False, "n/a",
     "Disciplinas de estudo."),
    ("POST", "/api/estudos/disciplinas", "estudos", "", "nome,peso", True, "nao",
     "Cria disciplina de estudo."),
    ("GET", "/api/estudos/topicos", "estudos", "disciplina_id", "", False, "n/a",
     "Tópicos, opcionalmente por disciplina."),
    ("POST", "/api/estudos/topicos", "estudos", "", "disciplina_id,nome,parent_id", True,
     "nao", "Cria tópico de estudo."),
    ("GET", "/api/estudos/progresso", "estudos", "contest_id", "", False, "n/a",
     "Progresso por tópico e por edital."),
    ("POST", "/api/estudos/progresso", "estudos", "", "topico_id,state,contest_id", True,
     "sim", "Define o estado de progresso de um tópico."),
    ("GET", "/api/estudos/sessoes", "estudos", "limit", "", False, "n/a",
     "Histórico de sessões de estudo."),
    ("POST", "/api/estudos/sessoes", "estudos", "",
     "action,id,disciplina_id,topico_id,contest_id,modo", True, "condicional",
     "Inicia/pausa/retoma/conclui/descarta sessão; uma sessão aberta por vez."),
    ("GET", "/api/estudos/sessao-atual", "estudos", "", "", False, "n/a",
     "Sessão aberta e tempo decorrido calculado no servidor."),
    ("GET", "/api/estudos/revisoes", "estudos", "", "", False, "n/a",
     "Revisões espaçadas pendentes."),
    ("POST", "/api/estudos/revisoes", "estudos", "", "progresso_id,resultado", True, "sim",
     "Marca revisão espaçada como concluída."),
    ("GET", "/api/estudos/perfil", "estudos", "", "", False, "n/a",
     "Perfil de conhecimento por conceito."),
    ("POST", "/api/estudos/perfil", "estudos", "",
     "disciplina,rotulo,nivel,revisar,confianca,observacoes,origem", True, "sim",
     "Atualiza o perfil de conhecimento."),
    ("DELETE", "/api/estudos/perfil", "estudos", "conceito_key", "", True, "sim",
     "Remove uma entrada do perfil."),
    ("GET", "/api/estudos/conteudo", "estudos", "contest_id", "", False, "n/a",
     "Conteúdo programático do edital por concurso."),
    ("GET", "/api/estudos/preparacao", "estudos", "contest_id", "", False, "n/a",
     "Preparação: cobertura do conteúdo e perspectivas."),
    ("GET", "/api/estudos/exportar", "estudos", "", "", False, "n/a",
     "Exporta dados pessoais de estudo em JSON versionado."),
    ("POST", "/api/estudos/importar", "estudos", "", "payload,dry_run", True, "sim",
     "Importa dados pessoais de estudo com validação e transação."),
    ("POST", "/api/estudos/lacuna", "estudos", "", "contest_id,conceito_key", True, "sim",
     "Envia lacuna de edital para a trilha de estudo."),

    # --- Estudos: flashcards ---------------------------------------------------
    ("GET", "/api/estudos/flashcards", "flashcards", "incluir_arquivados", "", False,
     "n/a", "Lista flashcards."),
    ("GET", "/api/estudos/flashcards/fila", "flashcards", "limit", "", False, "n/a",
     "Fila de revisão de flashcards (novos + vencidos)."),
    ("GET", "/api/estudos/flashcards/estatisticas", "flashcards", "", "", False, "n/a",
     "Estatísticas de flashcards."),
    ("POST", "/api/estudos/flashcards", "flashcards", "",
     "action,id,frente,verso,disciplina_id,topico_id,contest_id,conceito_key,tags,fonte,"
     "licenca,qualidade,estado", True, "condicional",
     "Cria, atualiza ou revisa flashcard (SM-2-lite)."),
    ("POST", "/api/estudos/flashcards/{flashcard_id}/imagem", "flashcards", "",
     "dados_base64,licenca", True, "sim",
     "Anexa imagem validada por assinatura binária e hash."),
    ("DELETE", "/api/estudos/flashcards/{flashcard_id}/imagem", "flashcards", "", "", True,
     "sim", "Remove a imagem do flashcard."),
    # --- Estáticos (não são API; documentados para o verificador de rotas) ------
    ("GET", "/assets/", "estaticos", "", "", False, "n/a",
     "Assets do build React com hash de conteúdo (cache imutável)."),

    ("GET", "/api/estudos/midia", "flashcards", "", "", False, "n/a",
     "Rota base de mídia: exige id; sem id devolve 400."),
    ("GET", "/api/estudos/midia/{media_id}", "flashcards", "", "", False, "n/a",
     "Serve mídia local com Content-Type fixo e nosniff."),

    # --- Estudos: questões, tentativas e simulados -----------------------------
    ("GET", "/api/estudos/questoes", "questoes", "disciplina,incluir_arquivadas,topico", "",
     False, "n/a", "Banco de questões."),
    ("POST", "/api/estudos/questoes", "questoes", "",
     "action,id,enunciado,alternativas,gabarito,tipo,comentario,disciplina,topico,"
     "dificuldade,tags,fonte,licenca,procedencia,conceito_key", True, "condicional",
     "Cria, atualiza ou arquiva questão; gabarito nunca vai em prova em andamento."),
    ("GET", "/api/estudos/tentativas", "questoes", "limit,simulado_id", "", False, "n/a",
     "Tentativas registradas."),
    ("POST", "/api/estudos/tentativas", "questoes", "",
     "questao_id,resposta,duracao_segundos", True, "nao",
     "Registra tentativa de prática e corrige no servidor."),
    ("GET", "/api/estudos/desempenho", "questoes", "", "", False, "n/a",
     "Desempenho geral, por disciplina e por tópico."),
    ("GET", "/api/estudos/simulados", "simulados", "limit", "", False, "n/a",
     "Lista simulados."),
    ("POST", "/api/estudos/simulados", "simulados", "",
     "modo,nome,limit,duracao_segundos,seed,shuffle,exclude_answered,disciplina,topico,"
     "dificuldade,tags", True, "nao",
     "Cria simulado tradicional ou adaptativo sem duplicar questão."),
    ("GET", "/api/estudos/simulados/{exam_id}", "simulados", "", "", False, "n/a",
     "Simulado com itens, respostas salvas e tempo restante do servidor."),
    ("GET", "/api/estudos/simulados/{exam_id}/resultado", "simulados", "", "", False,
     "n/a", "Resultado corrigido e persistido."),
    ("GET", "/api/estudos/simulados/{exam_id}/questoes", "simulados", "", "", False, "n/a",
     "Questões aplicadas, sem gabarito enquanto a prova está em andamento."),
    ("GET", "/api/estudos/simulados/{exam_id}/resumo", "simulados", "", "", False, "n/a",
     "Resumo de navegação: posição, marcadas e respondidas."),
    ("POST", "/api/estudos/simulados/{exam_id}/responder", "simulados", "",
     "ordem,resposta", True, "sim", "Salva resposta de um item."),
    ("POST", "/api/estudos/simulados/{exam_id}/marcar", "simulados", "",
     "ordem,marcada", True, "sim", "Marca/desmarca item para revisão."),
    ("POST", "/api/estudos/simulados/{exam_id}/posicao", "simulados", "", "ordem", True,
     "sim", "Salva a posição de navegação."),
    ("POST", "/api/estudos/simulados/{exam_id}/proxima", "simulados", "", "", True,
     "sim", "Avança para a próxima questão adaptativa."),
    ("POST", "/api/estudos/simulados/{exam_id}/finalizar", "simulados", "", "", True,
     "sim", "Finaliza e persiste tentativas uma única vez (idempotente)."),

    # --- Estudos: pacotes ------------------------------------------------------
    ("GET", "/api/estudos/pacotes", "pacotes", "limit", "", False, "n/a",
     "Pacotes de conteúdo exportados/importados."),
    ("GET", "/api/estudos/pacotes/exportar", "pacotes", "licenca,nome,tipo", "", False,
     "n/a", "Exporta pacote ZIP com manifesto e direitos declarados."),
    ("POST", "/api/estudos/pacotes/previa", "pacotes", "", "dados_base64", True, "sim",
     "Pré-visualiza pacote sem gravar (limites de tamanho e estrutura)."),
    ("POST", "/api/estudos/pacotes/importar", "pacotes", "", "dados_base64,dry_run", True,
     "sim", "Importa pacote com validação de licença, tamanho e colisões."),
]

_MATCH_OVERRIDES = {
    "/api/estudos/flashcards/{flashcard_id}/imagem": "/api/estudos/flashcards/",
}


def _match(path: str) -> str:
    """Prefixo literal do servidor para rotas dinâmicas; subrotas usam o caminho completo."""
    if path in _MATCH_OVERRIDES:
        return _MATCH_OVERRIDES[path]
    if "{" not in path:
        return path
    prefix, rest = path.split("{", 1)
    tail = rest.split("}", 1)[1]
    return path if tail else prefix


# Rotas declaradas por sufixo (``rest.endswith``/tupla de verbos), não por prefixo literal.
# O marcador é conferido no código-fonte; se o handler mudar, a verificação acusa.
_DYNAMIC_MARKERS = {
    ("GET", "/api/concursos/{contest_id}/detalhes"): 'path.endswith("/detalhes")',
    ("GET", "/api/revisao/lotes/{batch_id}/exportar"): 'remainder.endswith("/exportar")',
    ("GET", "/api/estudos/simulados/{exam_id}/resultado"): 'rest.endswith("/resultado")',
    ("GET", "/api/estudos/simulados/{exam_id}/questoes"): 'rest.endswith("/questoes")',
    ("GET", "/api/estudos/simulados/{exam_id}/resumo"): 'rest.endswith("/resumo")',
    ("POST", "/api/estudos/simulados/{exam_id}/responder"):
        '"responder", "finalizar", "marcar", "posicao", "proxima"',
    ("POST", "/api/estudos/simulados/{exam_id}/finalizar"):
        '"responder", "finalizar", "marcar", "posicao", "proxima"',
    ("POST", "/api/estudos/simulados/{exam_id}/marcar"):
        '"responder", "finalizar", "marcar", "posicao", "proxima"',
    ("POST", "/api/estudos/simulados/{exam_id}/posicao"):
        '"responder", "finalizar", "marcar", "posicao", "proxima"',
    ("POST", "/api/estudos/simulados/{exam_id}/proxima"):
        '"responder", "finalizar", "marcar", "posicao", "proxima"',
}

ROUTES = [
    {"method": method, "path": path, "domain": domain,
     "query": [item for item in query.split(",") if item],
     "body": [item for item in body.split(",") if item],
     "writes": writes, "idempotent": idempotent, "summary": summary,
     "match": _match(path)}
    for method, path, domain, query, body, writes, idempotent, summary in _ENTRIES
]

DOMAIN_LABELS = {
    "concursos": "Concursos, identidade e oportunidades",
    "documentos": "Documentos e aquisição",
    "pipeline": "Pipeline documental",
    "cobertura": "Cobertura e confirmação",
    "confirmacao": "Confirmação documental",
    "associacoes": "Associações documento↔concurso",
    "revisao": "Revisão humana",
    "reconciliacao": "Reconciliação de identidade",
    "elegibilidade": "Elegibilidade",
    "carteira": "Carteira operacional",
    "prioridades": "Prioridades",
    "triagem": "Triagem",
    "prazos": "Prazos",
    "conflitos": "Conflitos",
    "fontes": "Fontes e consumo",
    "monitoramento": "Monitoramento",
    "saude": "Saúde e prontidão",
    "alertas": "Alertas",
    "preferencias": "Preferências",
    "estudos": "Estudos",
    "flashcards": "Flashcards",
    "questoes": "Questões e desempenho",
    "simulados": "Simulados",
    "pacotes": "Pacotes de conteúdo",
    "estaticos": "Estáticos (build e UI legada)",
}


def document() -> dict:
    """Especificação legível por máquina, com totais e convenções."""
    by_domain = {}
    for route in ROUTES:
        by_domain.setdefault(route["domain"], []).append(route)
    return {
        "version": VERSION,
        "total": len(ROUTES),
        "paths": len({route["path"] for route in ROUTES}),
        "domains": {name: len(items) for name, items in sorted(by_domain.items())},
        "conventions": {
            "content_type": "application/json quando há corpo",
            "origin": "Origin, se presente, deve ser loopback na mesma porta",
            "host": "Host deve ser loopback na mesma porta (anti DNS rebinding)",
            "errors": "JSON {\"error\": ...}; 400/403/404/405/415/429/503",
            "pagination": "limit/offset quando declarados",
            "auth": "nenhuma: servidor local em 127.0.0.1",
            "idempotency": "sim|condicional|nao por rota",
        },
        "routes": ROUTES,
    }


def _cell(value) -> str:
    return str(value).replace("|", "\\|")


def markdown() -> str:
    """Gera a documentação versionada (docs/API.md)."""
    lines = [
        "# API do Radar de Concursos",
        "",
        f"Versão do contrato: `{VERSION}`. Rotas: **{len(ROUTES)}** "
        f"({len({r['path'] for r in ROUTES})} caminhos).",
        "",
        "## Convenções",
        "",
        "- Servidor local em `127.0.0.1`; sem autenticação de rede.",
        "- Corpo de escrita em JSON UTF-8 (`Content-Type: application/json`).",
        "- `Origin`, quando enviado, precisa ser loopback na mesma porta; caso contrário, 403.",
        "- `Host` precisa ser loopback na mesma porta; caso contrário, 403 (anti DNS rebinding).",
        "- Erros: `{\"error\": \"...\"}` com 400/403/404/405/415/429/503; nunca traceback.",
        "- Consultas pesadas concorrentes podem receber 429; tente novamente.",
        "- Paginação por `limit`/`offset` quando a rota declara os parâmetros.",
        "- `GET /api/concursos` mantém o contrato v1 com 18 campos (aditivo desde então).",
        "",
    ]
    by_domain = {}
    for route in ROUTES:
        by_domain.setdefault(route["domain"], []).append(route)
    for domain in sorted(by_domain):
        lines += [f"## {DOMAIN_LABELS.get(domain, domain)}", "",
                  "| Método | Caminho | Query | Corpo | Escrita | Idempotência | Descrição |",
                  "|---|---|---|---|---|---|---|"]
        for route in by_domain[domain]:
            lines.append("| {} | `{}` | {} | {} | {} | {} | {} |".format(
                route["method"], _cell(route["path"]),
                ", ".join(route["query"]) or "—",
                ", ".join(route["body"]) or "—",
                "sim" if route["writes"] else "não",
                route["idempotent"], _cell(route["summary"])))
        lines.append("")
    return "\n".join(lines)


def server_routes(server_path: str) -> set[str]:
    """Extrai as rotas literais declaradas em `server.py` (para o teste de cobertura)."""
    with io.open(server_path, encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source)
    lines = source.splitlines()
    handler = next(node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == "_RadarRequestHandler")
    found = set()
    for node in handler.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in (
                "do_GET", "do_POST", "do_DELETE"):
            continue
        method = {"do_GET": "GET", "do_POST": "POST", "do_DELETE": "DELETE"}[node.name]
        body = "\n".join(lines[node.lineno - 1:node.end_lineno])
        literals = set(re.findall(r'path == "([^"]+)"', body))
        literals |= set(re.findall(r'path\.startswith\("([^"]+)"\)', body))
        literals |= set(re.findall(r'parts\.path\.startswith\("([^"]+)"\)', body))
        literals |= set(re.findall(r'parts\.path == "([^"]+)"', body))
        if method == "GET" and 'path.endswith("/detalhes")' in body:
            # O prefixo /api/concursos/ só existe junto de /detalhes.
            literals.discard("/api/concursos/")
        if method == "POST" and 'parts_rest[1] in (' in body:
            # O prefixo só existe para os verbos documentados individualmente.
            literals.discard("/api/estudos/simulados/")
        for literal in literals:
            found.add((method, literal))
    for (method, route), marker in _DYNAMIC_MARKERS.items():
        if marker in source:
            found.add((method, route))
    return found


def verify(server_path: str) -> dict:
    """Compara contrato e servidor; devolve divergências explícitas."""
    declared = {(route["method"], route["match"]) for route in ROUTES}
    actual = server_routes(server_path)
    return {
        "version": VERSION,
        "ok": declared == actual,
        "faltando_no_contrato": [f"{method} {path}" for method, path in sorted(actual - declared)],
        "sobrando_no_contrato": [f"{method} {path}" for method, path in sorted(declared - actual)],
        "rotas_no_servidor": len(actual),
        "rotas_no_contrato": len(declared),
    }
