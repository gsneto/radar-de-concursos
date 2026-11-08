"""Enriquecimento pedagógico avançado das aulas do GSN Concursos.

Fornece:
1. Hierarquia Curricular (Disciplina -> Módulo -> Assunto -> Aula, nível, tempo estimado, XP).
2. Videoaulas com Capítulos clicáveis, Checkpoints de Perguntas no meio do vídeo e Slides Animados de Contingência.
3. Quadros Digitais e Explicações Visuais Interativas (estilo Brilliant).
4. Mapas Mentais Interativos com nós clicáveis e expansíveis.
5. Flashcards Multiformato (Pergunta/Resposta, Conceito/Definição, V/F, Complete a Lacuna, Identifique o Erro, Comparação, Caso Prático).
6. Laboratório de Questões Interativas + Resolução detalhada alternativa por alternativa.
7. Professor Virtual Contextual fundamentado estritamente no conteúdo validado da aula.
8. Estatísticas verificáveis de bancas a partir do banco de questões reais.
"""

from __future__ import annotations

from typing import Any

LESSON_CURRICULUM_META: dict[str, dict[str, Any]] = {
    "bd-01": {
        "modulo": "Módulo 1: Projeto e Arquitetura de Dados",
        "assunto": "Modelagem Relacional e Formas Normais",
        "nivel": "Essencial",
        "tempo_estimado_min": 45,
        "xp_recompensa": 120,
        "competencias": [
            "Modelagem Conceitual (MER) e Mapeamento Relacional",
            "Primeira e Segunda Formas Normais (1FN e 2FN)",
            "Terceira Forma Normal (3FN) e Boyce-Codd (BCNF)",
        ],
    },
    "bd-02": {
        "modulo": "Módulo 2: Manipulação e Consultas em Bancos Relacionais",
        "assunto": "SQL ANSI: DDL, DML, Junções e Agregações",
        "nivel": "Intermediário",
        "tempo_estimado_min": 55,
        "xp_recompensa": 150,
        "competencias": [
            "Sublinguagens SQL (DDL, DML, DCL, TCL)",
            "Junções Relacionais (INNER, LEFT, RIGHT, FULL JOIN)",
            "Agrupamentos e Filtros (WHERE vs GROUP BY vs HAVING)",
        ],
    },
    "es-01": {
        "modulo": "Módulo 1: Processos de Desenvolvimento e Agilidade",
        "assunto": "Scrum, Kanban, XP e Práticas DevOps",
        "nivel": "Essencial",
        "tempo_estimado_min": 50,
        "xp_recompensa": 130,
        "competencias": [
            "Papéis, Eventos e Artefatos do Scrum Guide",
            "Gestão de Fluxo Kanban, WIP e Métricas (Lead Time)",
            "Práticas Técnicas de XP e Pipeline CI/CD",
        ],
    },
    "es-02": {
        "modulo": "Módulo 2: Design de Software e Arquitetura Limpa",
        "assunto": "Padrões de Projeto GoF e Princípios SOLID",
        "nivel": "Avançado",
        "tempo_estimado_min": 60,
        "xp_recompensa": 160,
        "competencias": [
            "Padrões GoF Criacionais, Estruturais e Comportamentais",
            "Princípios SOLID de Design Orientado a Objetos",
            "Arquitetura de Microsserviços e Acoplamento",
        ],
    },
    "port-01": {
        "modulo": "Módulo 1: Semântica, Coesão e Estrutura Textual",
        "assunto": "Interpretação, Conectivos e Relações Lógico-Discursivas",
        "nivel": "Essencial",
        "tempo_estimado_min": 50,
        "xp_recompensa": 140,
        "competencias": [
            "Compreensão Explícita vs Inferência Textual",
            "Relações Semânticas (Concessão, Causa, Consequência, Oposição)",
            "Coesão Referencial Anafórica, Catafórica e Pronomes Relativos",
        ],
    },
    "dir-01": {
        "modulo": "Módulo 1: Teoria dos Direitos Fundamentais",
        "assunto": "Artigo 5º da CF/88 e Remédios Constitucionais",
        "nivel": "Essencial",
        "tempo_estimado_min": 50,
        "xp_recompensa": 130,
        "competencias": [
            "Inviolabilidade de Domicílio e Sigilo das Comunicações",
            "Legitimidade e Cabimento dos Remédios Constitucionais",
            "Jurisprudência Sumulada do STF sobre Garantias Fundamentais",
        ],
    },
    "red-01": {
        "modulo": "Módulo 1: Arquitetura de Redes e Protocolos",
        "assunto": "Modelo OSI, Pilha TCP/IP e Camada de Transporte",
        "nivel": "Essencial",
        "tempo_estimado_min": 50,
        "xp_recompensa": 130,
        "competencias": [
            "Camadas e PDUs do Modelo OSI vs TCP/IP",
            "Protocolos TCP (Three-Way Handshake) vs UDP",
            "Portas e Serviços de Aplicação (DNS, HTTP/HTTPS, SSH, DHCP)",
        ],
    },
    "seg-01": {
        "modulo": "Módulo 1: Criptografia, Assinatura Digital e Segurança Web",
        "assunto": "Princípios CIDAN, Chaves Criptográficas e OWASP Top 10",
        "nivel": "Intermediário",
        "tempo_estimado_min": 55,
        "xp_recompensa": 150,
        "competencias": [
            "Princípios Fundamentais (Confidencialidade, Integridade, Disponibilidade, Autenticidade, Não-Repúdio)",
            "Criptografia Simétrica, Assimétrica, Hash e Assinatura Digital",
            "Vulnerabilidades de Aplicações Web (SQL Injection, XSS, CSRF)",
        ],
    },
}


# ==============================================================================
# Quadros Visuais Interativos (Estilo Brilliant) + Mapas Mentais
# ==============================================================================

LESSON_VISUAL_BOARDS: dict[str, dict[str, Any]] = {
    "port-01": {
        "titulo": "Quadro Digital: Arquitetura das Relações Semânticas e Conectivos",
        "subtitulo": "Explore visualmente como cada conectivo articula causa, consequência, concessão e oposição nas provas.",
        "relacoes_conceituais": [
            {
                "id": "rel-concessao",
                "categoria": "CONCESSÃO",
                "cor": "amber",
                "regra_ouro": "Introduz um obstáculo real ou hipotético que NÃO impede a realização do fato principal.",
                "conectivos": ["embora", "conquanto", "ainda que", "mesmo que", "posto que", "se bem que", "apesar de"],
                "fluxo_visual": "embora  ➔  conquanto  ➔  ainda que  ➔  posto que (+ subjuntivo)",
                "exemplo_destacado": "Conquanto o edital fosse extenso [obstáculo], o candidato fechou a prova [fato principal ocorreu].",
                "armadilha_banca": "A FGV e o Cebraspe tentam substituir 'conquanto' (concessivo) por 'porquanto' (causal). Nunca aceite!",
            },
            {
                "id": "rel-causa",
                "categoria": "CAUSA / EXPLICAÇÃO",
                "cor": "emerald",
                "regra_ouro": "Apresenta a origem, motivo ou razão cronologicamente anterior que gera um determinado efeito.",
                "conectivos": ["porque", "visto que", "já que", "como (no início)", "porquanto", "uma vez que", "na medida em que"],
                "fluxo_visual": "porque  ➔  visto que  ➔  já que  ➔  porquanto",
                "exemplo_destacado": "Como revisou por repetição espaçada [causa anterior], lembrou de todas as fórmulas [efeito].",
                "armadilha_banca": "A locução 'na medida em que' é CAUSAL; já 'à medida que' é PROPORCIONAL.",
            },
            {
                "id": "rel-consequencia",
                "categoria": "CONSEQUÊNCIA",
                "cor": "sky",
                "regra_ouro": "Aponta o efeito ou resultado desencadeado pela intensidade da ação declarada na oração principal.",
                "conectivos": ["tanto que", "de modo que", "de sorte que", "tão... que", "tamanho... que"],
                "fluxo_visual": "tão / tanto  ➔  que  ➔  de modo que  ➔  de forma que",
                "exemplo_destacado": "A jurisprudência mudou tanto [causa intensa] que o manual precisou ser reescrito [consequência].",
                "armadilha_banca": "Bancas pedem a reescrita convertendo a oração consecutiva na sua inversa causal.",
            },
            {
                "id": "rel-adversidade",
                "categoria": "OPOSIÇÃO / ADVERSIDADE",
                "cor": "rose",
                "regra_ouro": "Coordena duas ideias contrastantes em que o argumento da segunda oração prevalece.",
                "conectivos": ["mas", "porém", "contudo", "todavia", "entretanto", "no entanto", "não obstante"],
                "fluxo_visual": "mas (fixo no início)  ➔  porém / contudo / todavia / entretanto (deslocáveis entre vírgulas)",
                "exemplo_destacado": "O candidato tinha pouco tempo livre; organizou, contudo, uma rotina disciplinada.",
                "armadilha_banca": "A conjunção 'mas' NUNCA pode ser deslocada para depois do verbo da segunda oração.",
            },
        ],
        "passos_animados": [
            {
                "passo": 1,
                "titulo": "1. Identifique a Oração Principal e a Subordinada",
                "detalhe": "Separe os dois eventos da frase e pergunte: um deles é motivo (causa) ou barreira vencida (concessão)?",
                "destaque_codigo": "[Conquanto chovesse forte] (Barreira) ➔ [a prova ocorreu normalmente] (Fato Principal)",
            },
            {
                "passo": 2,
                "titulo": "2. Aplique o Teste da Comutação Segura",
                "detalhe": "Se o conectivo puder ser trocado por 'EMBORA' mantendo o verbo no subjuntivo, a relação é 100% Concessiva.",
                "destaque_codigo": "Conquanto = Embora = Ainda que = Posto que  (Todos exigem Subjuntivo)",
            },
            {
                "passo": 3,
                "titulo": "3. Verifique a Referência Coesiva (Onde vs Em Que)",
                "detalhe": "Pronome 'ONDE' exige lugar físico palpável. Para ideias, processos ou situações, use sempre 'EM QUE' ou 'NO QUAL'.",
                "destaque_codigo": "ERRADO: 'A fase onde o projeto falhou'  ➔  CORRETO: 'A fase em que o projeto falhou'",
            },
        ],
    },
    "bd-01": {
        "titulo": "Quadro Digital: Pipeline Visual de Normalização (1FN ➔ 2FN ➔ 3FN ➔ BCNF)",
        "subtitulo": "Acompanhe passo a passo como uma tabela com anomalias é purificada até a 3ª Forma Normal.",
        "relacoes_conceituais": [
            {
                "id": "fn-1",
                "categoria": "1ª FORMA NORMAL (1FN)",
                "cor": "amber",
                "regra_ouro": "Proíbe atributos multivalorados, compostos ou tabelas aninhadas. Cada célula guarda 1 valor atômico.",
                "conectivos": ["Atomicidade", "Sem listas", "Sem grupos repetitivos", "Valores indivisíveis"],
                "fluxo_visual": "Tabela Bruta  ➔  Quebra multivalorados  ➔  Atributos 100% Atômicos (1FN)",
                "exemplo_destacado": "Coluna Telefones = '9999-1111, 8888-2222' viola a 1FN! Deve-se criar tabela ou linhas atômicas.",
                "armadilha_banca": "Toda tabela relacional válida já nasce, por definição teórica, na 1FN.",
            },
            {
                "id": "fn-2",
                "categoria": "2ª FORMA NORMAL (2FN)",
                "cor": "emerald",
                "regra_ouro": "Exige estar na 1FN + eliminar Dependência Funcional PARCIAL (nenhum atributo não-chave pode depender só de metade da PK composta).",
                "conectivos": ["Dependência Funcional Total", "Atenção à PK Composta", "PK Simples = Já está na 2FN"],
                "fluxo_visual": "PK Composta (Cod_Pedido, Cod_Produto)  ➔  Nome_Produto depende só de Cod_Produto (Viola 2FN!)",
                "exemplo_destacado": "Se a tabela está na 1FN e sua Chave Primária tem apenas 1 coluna (simples), ela está AUTOMATICAMENTE na 2FN!",
                "armadilha_banca": "Cebraspe cobra exatamente a regra da chave simples em 1FN ser automaticamente 2FN.",
            },
            {
                "id": "fn-3",
                "categoria": "3ª FORMA NORMAL (3FN)",
                "cor": "sky",
                "regra_ouro": "Exige estar na 2FN + eliminar Dependência Funcional TRANSITIVA (atributo não-chave determinando outro não-chave).",
                "conectivos": ["Sem Dependência Transitiva", "Não-Chave ↛ Não-Chave", "Fato sobre a Chave, toda a Chave e nada além da Chave"],
                "fluxo_visual": "PK (Matrícula) ➔ Cod_Depto (Não-Chave) ➔ Nome_Depto (Não-Chave)  [Ponte Transitiva = Viola 3FN!]",
                "exemplo_destacado": "Para corrigir, extraia (Cod_Depto, Nome_Depto) para uma nova relação Departamento.",
                "armadilha_banca": "FGV dá o esquema R(A,B,C,D) com PK(A) e C → D, pedindo qual forma normal foi violada (3FN!).",
            },
        ],
        "passos_animados": [
            {
                "passo": 1,
                "titulo": "1. Olhe para as Células (Teste da 1FN)",
                "detalhe": "Há múltiplos valores separados por vírgula ou listas dentro de um atributo? Se sim, viole a 1FN.",
                "destaque_codigo": "1FN: ∀ atributo A, domínio(A) é atômico e indivisível",
            },
            {
                "passo": 2,
                "titulo": "2. Olhe para a Chave Primária (Teste da 2FN)",
                "detalhe": "A PK é composta por 2+ colunas? Algum campo depende de apenas UMA parte da PK? Se sim, viola a 2FN.",
                "destaque_codigo": "PK(A, B) com B ➔ C  ⟹  Dependência Parcial (Viola 2FN)",
            },
            {
                "passo": 3,
                "titulo": "3. Olhe para os Campos Comuns (Teste da 3FN)",
                "detalhe": "Algum campo não-chave determina outro campo não-chave? Se sim, há dependência transitiva (viola a 3FN).",
                "destaque_codigo": "PK(A) ➔ B (não-chave) ➔ C (não-chave)  ⟹  Dependência Transitiva (Viola 3FN)",
            },
        ],
    },
}


def _build_default_visual_board(lesson: dict[str, Any]) -> dict[str, Any]:
    """Constrói um quadro visual interativo rico a partir da tabela_resumo e pontos críticos da aula."""
    lid = lesson["id"]
    if lid in LESSON_VISUAL_BOARDS:
        return LESSON_VISUAL_BOARDS[lid]

    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []
    colunas = tabela.get("colunas") or []
    cores = ["amber", "emerald", "sky", "rose", "purple"]

    relacoes = []
    for idx, row in enumerate(linhas):
        cat = row[0] if len(row) > 0 else f"Conceito {idx + 1}"
        regra = row[1] if len(row) > 1 else ""
        efeito = row[2] if len(row) > 2 else ""
        pegadinha = row[3] if len(row) > 3 else (lesson.get("pontos_criticos") or [""])[0]
        relacoes.append({
            "id": f"rel-{lid}-{idx}",
            "categoria": cat.upper(),
            "cor": cores[idx % len(cores)],
            "regra_ouro": regra,
            "conectivos": [c.strip() for c in efeito.split(",") if c.strip()][:4] or [cat],
            "fluxo_visual": f"{cat}  ➔  {regra}  ➔  {efeito}",
            "exemplo_destacado": f"{colunas[2] if len(colunas) > 2 else 'Aplicação'}: {efeito}",
            "armadilha_banca": pegadinha,
        })

    passos = []
    for idx, ponto in enumerate(lesson.get("pontos_criticos") or []):
        passos.append({
            "passo": idx + 1,
            "titulo": f"Ponto Chave {idx + 1}: Regra de Prova",
            "detalhe": ponto,
            "destaque_codigo": (lesson.get("objetivos") or [ponto])[min(idx, len(lesson.get("objetivos") or [ponto]) - 1)],
        })

    return {
        "titulo": f"Quadro Digital: {tabela.get('titulo') or lesson['titulo']}",
        "subtitulo": "Esquema visual interativo com relações de causa-efeito, regras de ouro e armadilhas de prova.",
        "relacoes_conceituais": relacoes,
        "passos_animados": passos,
    }


def _build_mind_map(lesson: dict[str, Any]) -> dict[str, Any]:
    """Gera a estrutura de Mapa Mental Interativo com nós clicáveis e expansíveis."""
    lid = lesson["id"]
    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []
    cores = ["amber", "emerald", "sky", "purple", "rose"]

    nos = []
    for idx, row in enumerate(linhas):
        titulo_no = row[0] if len(row) > 0 else f"Tópico {idx + 1}"
        desc_no = row[1] if len(row) > 1 else ""
        aplicacao = row[2] if len(row) > 2 else ""
        alerta = row[3] if len(row) > 3 else ""
        nos.append({
            "id": f"mm-{lid}-{idx}",
            "titulo": titulo_no,
            "categoria": lesson["disciplina"],
            "cor": cores[idx % len(cores)],
            "descricao": desc_no,
            "exemplo": aplicacao,
            "dica_banca": alerta or (lesson.get("pontos_criticos") or [""])[0],
            "subnos": [
                {"id": f"mm-{lid}-{idx}-a", "label": f"Essência: {desc_no[:70]}"},
                {"id": f"mm-{lid}-{idx}-b", "label": f"Prática: {aplicacao[:70]}"},
            ],
        })

    return {
        "no_central": lesson["titulo"].split(":")[-1].strip(),
        "disciplina": lesson["disciplina"],
        "nos": nos,
    }


def _enrich_videos(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    """Enriquece as videoaulas com capítulos clicáveis, perguntas de checkpoint durante o vídeo e slides guiados."""
    videos = lesson.get("videoaulas") or []
    objetivos = lesson.get("objetivos") or []
    pontos = lesson.get("pontos_criticos") or []
    fcs = lesson.get("flashcards") or []

    enriched = []
    for v_idx, v in enumerate(videos):
        v_copy = dict(v)
        if "capitulos" not in v_copy:
            v_copy["capitulos"] = [
                {
                    "id": f"cap-{lesson['id']}-{v_idx}-1",
                    "titulo": "01. Introdução & Visão Geral na Prova",
                    "tempo_seg": 0,
                    "tempo_label": "00:00",
                    "resumo": objetivos[0] if len(objetivos) > 0 else "Contextualização dos conceitos fundamentais.",
                },
                {
                    "id": f"cap-{lesson['id']}-{v_idx}-2",
                    "titulo": "02. Teoria Estruturada & Mecanismos Chave",
                    "tempo_seg": 420,
                    "tempo_label": "07:00",
                    "resumo": objetivos[1] if len(objetivos) > 1 else "Análise detalhada dos conceitos cobrados em edital.",
                },
                {
                    "id": f"cap-{lesson['id']}-{v_idx}-3",
                    "titulo": "03. Pegadinhas de Banca & Casos Práticos",
                    "tempo_seg": 960,
                    "tempo_label": "16:00",
                    "resumo": pontos[0] if len(pontos) > 0 else "Como FGV e Cebraspe cobram o tema em provas reais.",
                },
                {
                    "id": f"cap-{lesson['id']}-{v_idx}-4",
                    "titulo": "04. Revisão Final & Resolução de Questões",
                    "tempo_seg": 1380,
                    "tempo_label": "23:00",
                    "resumo": objetivos[-1] if len(objetivos) > 0 else "Consolidação e checklist final para gabaritar.",
                },
            ]

        if "perguntas_video" not in v_copy:
            fc_ref = fcs[v_idx % len(fcs)] if fcs else None
            v_copy["perguntas_video"] = [
                {
                    "id": f"pv-{lesson['id']}-{v_idx}-1",
                    "momento_seg": 420,
                    "momento_label": "07:00",
                    "capitulo_ref": "02. Teoria Estruturada",
                    "pergunta": fc_ref["frente"] if fc_ref else f"Qual é a regra crítica sobre {lesson['disciplina']} abordada neste trecho?",
                    "alternativas": [
                        fc_ref["verso"] if fc_ref else (pontos[0] if pontos else "Regra fundamental do tópico."),
                        "A banca permite ignorar a restrição formal quando o sistema opera em lote.",
                        "O conceito aplica-se apenas a arquiteturas legadas sem chave primária.",
                        "A regra inverte-se completamente quando avaliada pela banca FGV.",
                    ],
                    "correta_idx": 0,
                    "explicacao": (
                        f"{fc_ref['verso']} ({fc_ref.get('mnemonico', '')})"
                        if fc_ref
                        else (pontos[0] if pontos else "Conceito central validado.")
                    ),
                }
            ]

        if "slides_guiados" not in v_copy:
            tabela = lesson.get("tabela_resumo") or {}
            slides = [
                {
                    "ordem": 1,
                    "tag": "OBJETIVO DA AULA",
                    "titulo": v_copy["titulo"],
                    "conteudo": v_copy.get("descricao") or lesson["titulo"],
                    "destaque": objetivos[0] if objetivos else "",
                }
            ]
            for r_idx, row in enumerate((tabela.get("linhas") or [])[:4]):
                slides.append({
                    "ordem": r_idx + 2,
                    "tag": f"CONCEITO CHAVE #{r_idx + 1}",
                    "titulo": row[0] if len(row) > 0 else f"Conceito {r_idx + 1}",
                    "conteudo": f"{row[1] if len(row) > 1 else ''} — {row[2] if len(row) > 2 else ''}",
                    "destaque": f"Alerta de Prova: {row[3]}" if len(row) > 3 else (pontos[0] if pontos else ""),
                })
            v_copy["slides_guiados"] = slides

        enriched.append(v_copy)
    return enriched


def _enrich_flashcards(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    """Enriquece os flashcards existentes e adiciona formatos interativos variados (V/F, Complete a Lacuna, Identifique o Erro)."""
    lid = lesson["id"]
    base_cards = [dict(fc) for fc in (lesson.get("flashcards") or [])]
    tipos_base = ["pergunta_resposta", "conceito_definicao", "comparacao", "exemplo_pratico"]

    for idx, card in enumerate(base_cards):
        if "tipo" not in card:
            card["tipo"] = tipos_base[idx % len(tipos_base)]
        if "dificuldade_sugerida" not in card:
            card["dificuldade_sugerida"] = "media"

    pontos = lesson.get("pontos_criticos") or []
    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []

    # Adicionar cartão Verdadeiro ou Falso
    if pontos:
        base_cards.append({
            "id": f"fc-{lid}-vf",
            "tipo": "verdadeiro_falso",
            "frente": f"[Julgue V ou F] {pontos[0]}",
            "verso": f"VERDADEIRO! Esta é uma regra de ouro essencial desta aula: {pontos[0]}",
            "mnemonico": "Afirmativa 100% alinhada com a jurisprudência/norma técnica das bancas.",
            "tag": lesson["disciplina"],
            "dificuldade_sugerida": "facil",
            "resposta_vf": "V",
        })

    # Adicionar cartão Complete a Lacuna
    if linhas and len(linhas[0]) >= 2:
        conceito_alvo = linhas[0][0]
        definicao_alvo = linhas[0][1]
        opcoes = [linhas[i][0] for i in range(min(4, len(linhas)))]
        if len(opcoes) < 3:
            opcoes = [conceito_alvo, "Exceção Secundária", "Regra Inversa"]
        base_cards.append({
            "id": f"fc-{lid}-lacuna",
            "tipo": "complete_lacuna",
            "frente": f"Complete a lacuna técnica: O conceito de [_______] exige como requisito fundamental: '{definicao_alvo}'.",
            "verso": f"Resposta correta: {conceito_alvo}. ({definicao_alvo})",
            "mnemonico": f"{conceito_alvo} ➔ {definicao_alvo[:50]}",
            "tag": lesson["disciplina"],
            "dificuldade_sugerida": "media",
            "lacuna_correta": conceito_alvo,
            "lacuna_opcoes": opcoes,
        })

    # Adicionar cartão Identifique o Erro
    if len(linhas) >= 2 and len(linhas[0]) >= 2 and len(linhas[1]) >= 2:
        c1, d1 = linhas[0][0], linhas[0][1]
        c2, d2 = linhas[1][0], linhas[1][1]
        base_cards.append({
            "id": f"fc-{lid}-erro",
            "tipo": "identifique_erro",
            "frente": f"Identifique o ERRO na afirmativa de prova: 'O mecanismo {c1} caracteriza-se por {d2.lower()}.'",
            "verso": f"ERRO DETECTADO: A banca inverteu os conceitos! '{d2}' pertence a {c2}, enquanto {c1} exige '{d1}'.",
            "mnemonico": f"Não deixe a banca trocar {c1} por {c2}!",
            "tag": lesson["disciplina"],
            "dificuldade_sugerida": "dificil",
            "erro_trecho": d2,
            "correcao": d1,
        })

    return base_cards


def _build_interactive_exercises(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    """Constrói exercícios interativos estilo H5P/Brilliant para o Laboratório da Aula."""
    lid = lesson["id"]
    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []
    pontos = lesson.get("pontos_criticos") or []

    exercicios: list[dict[str, Any]] = []

    # 1. Associação de Conceitos
    if len(linhas) >= 3:
        pares = [
            {"id": f"par-{idx}", "conceito": row[0], "definicao": row[1]}
            for idx, row in enumerate(linhas[:4])
            if len(row) >= 2
        ]
        exercicios.append({
            "id": f"ex-{lid}-associacao",
            "tipo": "associacao_conceitos",
            "titulo": "Desafio Interativo: Associação Rápida de Conceitos",
            "enunciado": "Conecte cada conceito técnico à sua definição exata cobrada em prova:",
            "pares": pares,
            "explicacao": "Dominar a distinção exata entre as definições evita cair na armadilha de inversão conceitual da FGV e do Cebraspe.",
        })

    # 2. Complete a Lacuna Contextualizada
    if len(linhas) >= 2:
        row0 = linhas[0]
        opcoes = [r[0] for r in linhas[:4]]
        exercicios.append({
            "id": f"ex-{lid}-lacuna",
            "tipo": "complete_lacuna",
            "titulo": "Preenchimento de Precisão Técnica",
            "enunciado": f"Em provas de {lesson['disciplina']}, quando o enunciado exige '{row0[1]}', a resposta obrigatória é [_______], cuja aplicação principal elimina/garante: '{row0[2] if len(row0) > 2 else row0[1]}'.",
            "opcoes": opcoes,
            "resposta_correta": row0[0],
            "explicacao": f"{row0[0]} é definido diretamente por '{row0[1]}'. Atenção: {row0[3] if len(row0) > 3 else (pontos[0] if pontos else '')}",
        })

    # 3. Ordenação / Sequência Lógica
    if len(linhas) >= 3:
        etapas = [f"{idx + 1}º — {row[0]}: {row[1]}" for idx, row in enumerate(linhas[:4])]
        exercicios.append({
            "id": f"ex-{lid}-ordenacao",
            "tipo": "ordenacao_etapas",
            "titulo": "Sequenciamento Lógico da Matéria",
            "enunciado": "Analise a progressão estrutural abaixo e confirme a ordem hierárquica correta dos conceitos estudados:",
            "etapas_corretas": etapas,
            "explicacao": "A compreensão da hierarquia e ordem de precedência resolve questões de análise de cenários complexos.",
        })

    return exercicios


def _build_tutor_contextual(lesson: dict[str, Any]) -> dict[str, Any]:
    """Constrói a base de conhecimento verificada do Professor Virtual da aula."""
    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []
    pontos = lesson.get("pontos_criticos") or []
    objetivos = lesson.get("objetivos") or []
    bancas = lesson.get("radiografia_bancas") or {}

    comparacao_txt = "\n".join(
        [f"• {r[0]}: {r[1]} (Foco: {r[2] if len(r) > 2 else ''})" for r in linhas[:4]]
    )

    return {
        "explicar_simples": (
            f"Pense em '{lesson['titulo']}' de forma prática: o objetivo central não é decorar termos soltos, "
            f"mas resolver um problema real. {objetivos[0] if objetivos else ''} "
            f"Na prática, sempre que a banca apresentar um cenário, verifique primeiro: {pontos[0] if pontos else ''}"
        ),
        "exemplo_pratico": (
            f"Cenário real de prova ({lesson['disciplina']}):\n"
            f"Imagine que o examinador da FGV apresente uma situação onde {linhas[0][1].lower() if linhas else 'o requisito básico é testado'}. "
            f"A aplicação imediata é identificar '{linhas[0][0] if linhas else lesson['titulo']}' porque {linhas[0][2] if linhas and len(linhas[0]) > 2 else 'atende à regra matriz'}. "
            f"Armadilha para evitar: {linhas[0][3] if linhas and len(linhas[0]) > 3 else (pontos[0] if pontos else '')}"
        ),
        "comparar_conceitos": (
            f"Comparativo Direto para não confundir na hora da prova:\n{comparacao_txt}"
        ),
        "resumo_1_minuto": (
            "Checklist Relâmpago de Revisão:\n"
            + "\n".join([f"✓ {p}" for p in pontos])
            + f"\n✓ FGV: {bancas.get('fgv', 'Foco em estudo de caso aplicado.')}"
            + f"\n✓ Cebraspe: {bancas.get('cebraspe', 'Atenção à inversão de conceitos literais.')}"
        ),
    }


def enrich_lesson_detail(lesson: dict[str, Any]) -> dict[str, Any]:
    """Retorna uma cópia enriquecida da aula com todos os módulos interativos e questões resolvidas."""
    from radar.real_exam_questions import _REAL_QUESTIONS

    out = dict(lesson)
    lid = out["id"]

    # 1. Metadados curriculares
    meta = LESSON_CURRICULUM_META.get(lid, {
        "modulo": f"Módulo Essencial: {out['disciplina']}",
        "assunto": out["titulo"],
        "nivel": "Essencial",
        "tempo_estimado_min": 45,
        "xp_recompensa": 120,
        "competencias": out.get("objetivos", [])[:3],
    })
    for k, v in meta.items():
        out.setdefault(k, v)

    # 2. Videoaulas enriquecidas
    out["videoaulas"] = _enrich_videos(out)

    # 3. Quadro Digital Visual & Mapa Mental
    out["quadro_visual"] = _build_default_visual_board(out)
    out["mapa_mental"] = _build_mind_map(out)

    # 4. Flashcards Multiformato
    out["flashcards"] = _enrich_flashcards(out)

    # 5. Questões Reais Detalhadas (resolvidas diretamente por id_ref para nunca ficar vazio!)
    q_map = {q["id_ref"]: q for q in _REAL_QUESTIONS}
    competencias = out.get("competencias") or ["Domínio Geral da Aula"]
    questoes_detalhadas = []

    for idx, qid in enumerate(out.get("questoes_ids") or []):
        q_raw = q_map.get(qid)
        if not q_raw:
            continue
        q_item = dict(q_raw)
        q_item["id"] = qid
        q_item["subtopico"] = competencias[idx % len(competencias)]

        # Extrair banca da tag (ex: banca:fgv -> FGV)
        banca_tag = next((t.split(":")[1].upper() for t in q_item.get("tags", []) if t.startswith("banca:")), "OFICIAL")
        q_item["banca_sigla"] = banca_tag

        # Formatar alternativas padronizadas [{letra, texto, justificativa}]
        if q_item.get("tipo") == "verdadeiro_falso":
            gabarito = q_item.get("gabarito", "V")
            q_item["alternativas_formatadas"] = [
                {
                    "letra": "V",
                    "texto": "Certo (Verdadeiro)",
                    "correta": gabarito == "V",
                    "justificativa": q_item["comentario"] if gabarito == "V" else f"Incorreto: a assertiva é falsa. {q_item['comentario']}",
                },
                {
                    "letra": "F",
                    "texto": "Errado (Falso)",
                    "correta": gabarito == "F",
                    "justificativa": q_item["comentario"] if gabarito == "F" else f"Incorreto: a assertiva é verdadeira. {q_item['comentario']}",
                },
            ]
        else:
            letras = ["A", "B", "C", "D", "E"]
            gabarito = q_item.get("gabarito", "A")
            alts = q_item.get("alternativas") or []
            formatadas = []
            for a_idx, texto_alt in enumerate(alts):
                letra = letras[a_idx] if a_idx < len(letras) else str(a_idx + 1)
                is_corr = letra == gabarito
                formatadas.append({
                    "letra": letra,
                    "texto": texto_alt,
                    "correta": is_corr,
                    "justificativa": (
                        f"ALTERNATIVA CORRETA ({letra}): {q_item['comentario']}"
                        if is_corr
                        else f"Alternativa {letra} incorreta: contradiz a regra técnica da aula ({q_item['comentario'][:140]}...)."
                    ),
                })
            q_item["alternativas_formatadas"] = formatadas

        questoes_detalhadas.append(q_item)

    out["questoes_detalhadas"] = questoes_detalhadas
    out["questoes_count"] = len(questoes_detalhadas)
    out["total_questoes"] = len(questoes_detalhadas)

    # 6. Exercícios Interativos do Laboratório
    out["exercicios_interativos"] = _build_interactive_exercises(out)

    # 7. Professor Virtual Contextual
    out["tutor_contextual"] = _build_tutor_contextual(out)

    # 8. Estatísticas verificáveis de bancas a partir do banco real de questões da disciplina
    disc_questions = [
        q for q in _REAL_QUESTIONS
        if q.get("disciplina", "").strip().lower() == out["disciplina"].strip().lower()
        or q["id_ref"] in (out.get("questoes_ids") or [])
    ]
    contagem_bancas: dict[str, int] = {}
    tipos_bancas: dict[str, set[str]] = {}
    for dq in disc_questions:
        b_sigla = next((t.split(":")[1].lower() for t in dq.get("tags", []) if t.startswith("banca:")), "outra")
        contagem_bancas[b_sigla] = contagem_bancas.get(b_sigla, 0) + 1
        tipos_bancas.setdefault(b_sigla, set()).add(
            "Certo/Errado" if dq.get("tipo") == "verdadeiro_falso" else "Múltipla Escolha (A-E)"
        )

    out["estatisticas_bancas_verificaveis"] = {
        "total_questoes_acervo_disciplina": len(disc_questions),
        "total_questoes_aula": len(questoes_detalhadas),
        "por_banca": {
            b: {
                "questoes_registradas": qtd,
                "formatos_verificados": sorted(list(tipos_bancas.get(b, set()))),
            }
            for b, qtd in contagem_bancas.items()
        },
    }

    return out


_CUSTOM_LESSONS: list[dict[str, Any]] = []


def summarize_lesson(l: dict[str, Any]) -> dict[str, Any]:
    meta = LESSON_CURRICULUM_META.get(l["id"], {})
    q_count = len(l.get("questoes_ids", []))
    return {
        "id": l["id"],
        "disciplina": l["disciplina"],
        "modulo": l.get("modulo") or meta.get("modulo") or f"Módulo 1: {l['disciplina']}",
        "assunto": l.get("assunto") or meta.get("assunto") or l["titulo"],
        "nivel": l.get("nivel") or meta.get("nivel") or "Essencial",
        "tempo_estimado_min": l.get("tempo_estimado_min") or meta.get("tempo_estimado_min") or 45,
        "xp_recompensa": l.get("xp_recompensa") or meta.get("xp_recompensa") or 120,
        "titulo": l["titulo"],
        "objetivos": l["objetivos"],
        "total_questoes": q_count,
        "questoes_count": q_count,
        "videoaulas_count": len(l.get("videoaulas", [])),
        "flashcards_count": len(l.get("flashcards", [])) + 3,
    }


def list_lessons_enriched(base_lessons: list[dict[str, Any]], disciplina: str | None = None) -> list[dict[str, Any]]:
    all_items = list(base_lessons) + _CUSTOM_LESSONS
    if not disciplina:
        return [summarize_lesson(l) for l in all_items]
    disc_norm = disciplina.strip().lower()
    return [
        summarize_lesson(l)
        for l in all_items
        if l["disciplina"].strip().lower() == disc_norm
    ]


def get_lesson_enriched(base_lessons: list[dict[str, Any]], lesson_id: str) -> dict[str, Any] | None:
    for l in list(base_lessons) + _CUSTOM_LESSONS:
        if l["id"] == lesson_id:
            return enrich_lesson_detail(l)
    return None


def create_custom_lesson(base_lessons: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    from uuid import uuid4

    titulo = str(payload.get("titulo") or "").strip()
    disciplina = str(payload.get("disciplina") or "").strip()
    if not titulo or not disciplina:
        raise ValueError("titulo e disciplina são obrigatórios para criar uma aula")

    lesson_id = str(payload.get("id") or f"custom-{uuid4().hex[:8]}").strip()
    new_lesson: dict[str, Any] = {
        "id": lesson_id,
        "disciplina": disciplina,
        "modulo": str(payload.get("modulo") or f"Módulo Customizado: {disciplina}").strip(),
        "assunto": str(payload.get("assunto") or titulo).strip(),
        "nivel": str(payload.get("nivel") or "Essencial").strip(),
        "tempo_estimado_min": int(payload.get("tempo_estimado_min") or 45),
        "xp_recompensa": int(payload.get("xp_recompensa") or 120),
        "titulo": titulo,
        "objetivos": list(payload.get("objetivos") or [f"Dominar os fundamentos de {titulo}."]),
        "teoria_resumida": str(payload.get("teoria_resumida") or f"Resumo estruturado sobre {titulo}."),
        "pontos_criticos": list(payload.get("pontos_criticos") or ["Atenção à literalidade e aos casos práticos da banca."]),
        "radiografia_bancas": dict(payload.get("radiografia_bancas") or {
            "fgv": "Cobra aplicação contextual em cenários práticos.",
            "cebraspe": "Avalia assertivas sobre conceitos e exceções.",
        }),
        "tabela_resumo": payload.get("tabela_resumo") or {
            "titulo": f"Síntese Comparativa: {titulo}",
            "colunas": ["Conceito", "Definição", "Aplicação", "Alerta de Prova"],
            "linhas": [
                [titulo, "Conceito central da aula", "Aplicado em provas de alto nível", "Evitar extrapolações"],
            ],
        },
        "videoaulas": list(payload.get("videoaulas") or []),
        "flashcards": list(payload.get("flashcards") or []),
        "questoes_ids": list(payload.get("questoes_ids") or []),
    }
    _CUSTOM_LESSONS.append(new_lesson)
    return get_lesson_enriched(base_lessons, lesson_id) or new_lesson

