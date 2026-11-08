"""Enriquecimento pedagógico avançado das aulas do GSN Concursos.

Fornece:
1. Hierarquia Curricular (Disciplina -> Módulo -> Assunto -> Aula, nível, tempo estimado, XP).
2. Videoaulas verificadas com Capítulos clicáveis, Checkpoints de Perguntas e Slides Guiados.
3. Quadros Digitais e Explicações Visuais Interativas (sem repetição de texto).
4. Mapas Mentais Interativos com nós clicáveis e expansíveis.
5. Flashcards Visuais Estilo Jotta (Mapas Visuais de Bolso com gatilhos de letras, contrastes lado a lado e regras de ouro) + integração SM-2.
6. Laboratório de Questões Interativas + Resolução detalhada alternativa por alternativa.
7. Professor Virtual Contextual fundamentado estritamente no conteúdo validado da aula.
8. Estatísticas verificáveis de bancas a partir do banco de questões reais.
"""

from __future__ import annotations

from pathlib import Path
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
        "assunto": "Interpretação, Conectivos, Pontuação e Homônimos",
        "nivel": "Essencial",
        "tempo_estimado_min": 50,
        "xp_recompensa": 140,
        "competencias": [
            "Compreensão Explícita vs Inferência Textual",
            "Relações Semânticas (Concessão, Causa, Consequência, Oposição)",
            "Ortografia Oficial, Homônimos (Sessão/Cessão/Seção) e Aposto Explicativo",
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
# Flashcards Visuais Estilo Jotta (Mapas Visuais Esquematizados de Alta Retenção)
# ==============================================================================

JOTTA_VISUAL_CARDS: dict[str, list[dict[str, Any]]] = {
    "port-01": [
        {
            "id": "fc-port-jotta-01",
            "tipo": "comparacao",
            "tag": "Português · Ortografia",
            "dificuldade_sugerida": "facil",
            "frente": "Como nunca mais confundir SESSÃO, CESSÃO e SEÇÃO na prova?",
            "verso": "SESSÃO (SS) = Reunião / Tempo (Cinema, Câmara). CESSÃO (C) = Ato de Ceder / Doar. SEÇÃO (Ç) = Separar / Repartição / Setor.",
            "mnemonico": "SS = Sentar na Reunião | C = Ceder | Ç = Cortar/Repartir",
            "esquema_jotta": {
                "selo": "DICA DO GSN · #01",
                "titulo": "SESSÃO x CESSÃO x SEÇÃO",
                "subtitulo": "Olhe para as letras do meio: elas entregam o significado na hora!",
                "colunas": [
                    {
                        "termo": "SESSÃO",
                        "destaque_letra": "S + SS",
                        "gatilho": 'REUNIÃO DE "S, S, S"',
                        "explicacao": "Vamos à SESSÃO (reunião) das nove e meia no cinema ou plenário.",
                        "cor": "amber",
                    },
                    {
                        "termo": "CESSÃO",
                        "destaque_letra": "C inicial",
                        "gatilho": '"C" DE "CEDER"',
                        "explicacao": "Vamos fazer uma CESSÃO de direitos (ceder bens ou servidor).",
                        "cor": "sky",
                    },
                    {
                        "termo": "SEÇÃO",
                        "destaque_letra": "S + Ç",
                        "gatilho": 'SEPARAR / REPARTIR',
                        "explicacao": "Qual é a sua SEÇÃO (repartição / departamento) eleitoral?",
                        "cor": "emerald",
                    },
                ],
                "regra_rodape": "VIU 'CEDER'? USE CESSÃO. VIU 'REPARTIÇÃO/SETOR'? USE SEÇÃO. VIU 'REUNIÃO'? USE SESSÃO!",
            },
        },
        {
            "id": "fc-port-jotta-02",
            "tipo": "exemplo_pratico",
            "tag": "Português · Vírgula",
            "dificuldade_sugerida": "facil",
            "frente": "Você sabia que 'POR EXEMPLO', 'ISTO É' e 'OU SEJA' exigem vírgula obrigatória?",
            "verso": "Expressões explicativas ou retificativas funcionam como aposto/termo explicativo e devem ficar SEMPRE isoladas por vírgula (ou travessões), em qualquer posição da frase.",
            "mnemonico": "Não importa a posição na frase: tem que ficar separado por vírgula!",
            "esquema_jotta": {
                "selo": "DICA DO GSN · #02",
                "titulo": 'VOCÊ SABIA QUE "POR EXEMPLO" É TERMO EXPLICATIVO?',
                "subtitulo": "Veja como a pontuação se comporta nas 3 posições possíveis da frase:",
                "colunas": [
                    {
                        "termo": "NO MEIO DA FRASE",
                        "destaque_letra": ", por exemplo,",
                        "gatilho": "ENTRE DUAS VÍRGULAS",
                        "explicacao": "O candidato, POR EXEMPLO, revisou todas as aulas antes do edital.",
                        "cor": "amber",
                    },
                    {
                        "termo": "NO INÍCIO DA FRASE",
                        "destaque_letra": "Por exemplo,",
                        "gatilho": "VÍRGULA LOGO APÓS",
                        "explicacao": "POR EXEMPLO, o candidato revisou todas as aulas antes do edital.",
                        "cor": "emerald",
                    },
                    {
                        "termo": "NO FINAL DA FRASE",
                        "destaque_letra": ", por exemplo.",
                        "gatilho": "VÍRGULA ANTES",
                        "explicacao": "O candidato revisou todas as aulas antes do edital, POR EXEMPLO.",
                        "cor": "sky",
                    },
                ],
                "regra_rodape": "NÃO IMPORTA EM QUE POSIÇÃO ESTEJA NA FRASE: TEM QUE FICAR SEPARADO POR VÍRGULA!",
            },
        },
        {
            "id": "fc-port-01",
            "tipo": "comparacao",
            "tag": "Português · Conectivos",
            "dificuldade_sugerida": "media",
            "frente": "Qual a diferença entre CONQUANTO e PORQUANTO nas provas da FGV e Cebraspe?",
            "verso": "'Conquanto' = CONCESSÃO (equivale a 'embora'). 'Porquanto' = CAUSA / EXPLICAÇÃO (equivale a 'porque').",
            "mnemonico": "CONquanto = CONcessão (Embora) | PORquanto = PORque (Causa)",
            "esquema_jotta": {
                "selo": "DICA DO GSN · #03",
                "titulo": "CONQUANTO x PORQUANTO",
                "subtitulo": "A troca mais cobrada pelo Cebraspe e pela FGV em reescrita de frases:",
                "colunas": [
                    {
                        "termo": "CONQUANTO",
                        "destaque_letra": "CON-",
                        "gatilho": '"CON" DE CONCESSÃO',
                        "explicacao": "Equivale a EMBORA, AINDA QUE, POSTO QUE. Exige verbo no subjuntivo!",
                        "cor": "amber",
                    },
                    {
                        "termo": "PORQUANTO",
                        "destaque_letra": "POR-",
                        "gatilho": '"POR" DE PORQUE',
                        "explicacao": "Equivale a PORQUE, VISTO QUE, JÁ QUE. Indica Causa ou Explicação!",
                        "cor": "emerald",
                    },
                ],
                "regra_rodape": "JAMAIS ACEITE TROCAR 'CONQUANTO' POR 'PORQUANTO': ALTERA TOTALMENTE O SENTIDO!",
            },
        },
        {
            "id": "fc-port-02",
            "tipo": "conceito_definicao",
            "tag": "Português · Coesão",
            "dificuldade_sugerida": "media",
            "frente": "Quando usar ONDE, AONDE e EM QUE segundo a norma culta?",
            "verso": "ONDE = Lugar físico fixo (quem está, está EM). AONDE = Lugar físico com movimento (quem vai, vai A). EM QUE = Situações abstratas (tempo, processos, ideias).",
            "mnemonico": "Onde = Fixo físico | Aonde = Movimento (Ir A) | Em que = Abstrato",
            "esquema_jotta": {
                "selo": "DICA DO GSN · #04",
                "titulo": "ONDE x AONDE x EM QUE",
                "subtitulo": "Teste o verbo e verifique se o referente é lugar físico concreto:",
                "colunas": [
                    {
                        "termo": "ONDE",
                        "destaque_letra": "FIXO FÍSICO",
                        "gatilho": "LUGAR SEM MOVIMENTO",
                        "explicacao": '"A sala ONDE fiz a prova era silenciosa." (Estar EM algum lugar).',
                        "cor": "sky",
                    },
                    {
                        "termo": "AONDE",
                        "destaque_letra": "A + ONDE",
                        "gatilho": 'VERBO PEDE "A" (MOVIMENTO)',
                        "explicacao": '"O tribunal AONDE você irá trabalhar." (Ir A algum lugar).',
                        "cor": "amber",
                    },
                    {
                        "termo": "EM QUE",
                        "destaque_letra": "ABSTRATO",
                        "gatilho": "NÃO É LUGAR FÍSICO",
                        "explicacao": '"O edital EM QUE passei." (Proibido usar ONDE para edital, fase ou época!).',
                        "cor": "rose",
                    },
                ],
                "regra_rodape": "SÓ USE 'ONDE' SE VOCÊ PUDER PISAR NO LUGAR! CASO CONTRÁRIO, USE 'EM QUE' / 'NO QUAL'.",
            },
        },
    ],
    "bd-01": [
        {
            "id": "fc-bd-01",
            "tipo": "comparacao",
            "tag": "Banco de Dados · Normalização",
            "dificuldade_sugerida": "facil",
            "frente": "Como memorizar 1FN, 2FN e 3FN em 10 segundos para a prova?",
            "verso": "1FN = Elimina multivalorados (exige átomos). 2FN = Elimina dependência PARCIAL da PK composta. 3FN = Elimina dependência TRANSITIVA entre campos não-chave.",
            "mnemonico": "1FN = Átomo | 2FN = Todo da PK | 3FN = Nada além da PK",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · BANCO DE DADOS",
                "titulo": "1FN x 2FN x 3FN (ESQUEMA DEFINITIVO)",
                "subtitulo": "O que cada Forma Normal proíbe na modelagem relacional:",
                "colunas": [
                    {
                        "termo": "1ª FN",
                        "destaque_letra": "ATÔMICA",
                        "gatilho": 'CÉLULA INDIVISÍVEL',
                        "explicacao": "Proíbe listas, vetores ou 2 telefones na mesma célula separados por vírgula.",
                        "cor": "amber",
                    },
                    {
                        "termo": "2ª FN",
                        "destaque_letra": "TOTAL DA PK",
                        "gatilho": 'SEM DEP. PARCIAL',
                        "explicacao": "Coluna comum não pode depender só de metade da Chave Primária composta.",
                        "cor": "emerald",
                    },
                    {
                        "termo": "3ª FN",
                        "destaque_letra": "DIRETA NA PK",
                        "gatilho": 'SEM DEP. TRANSITIVA',
                        "explicacao": "Coluna não-chave NUNCA pode determinar outra coluna não-chave.",
                        "cor": "sky",
                    },
                ],
                "regra_rodape": "DICA DE OURO CEBRASPE: SE A TABELA ESTÁ NA 1FN E TEM CHAVE SIMPLES (1 COLUNA), JÁ ESTÁ NA 2FN!",
            },
        },
        {
            "id": "fc-bd-02",
            "tipo": "conceito_definicao",
            "tag": "Banco de Dados · Chaves",
            "dificuldade_sugerida": "media",
            "frente": "Qual a diferença entre Chave Primária (PK), Candidata, Superchave e Estrangeira (FK)?",
            "verso": "Superchave = Qualquer conjunto que identifica a tupla. Candidata = Superchave mínima (sem sobras). PK = A candidata escolhida. FK = Referencia a PK de outra tabela (aceita NULL por padrão).",
            "mnemonico": "PK = Única + NOT NULL | FK = Aponta para PK + Aceita NULL",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · CHAVES RELACIONAIS",
                "titulo": "PK x FK x CANDIDATA",
                "subtitulo": "Regras de integridade que despencam em FGV e Cebraspe:",
                "colunas": [
                    {
                        "termo": "PRIMARY KEY",
                        "destaque_letra": "PK",
                        "gatilho": "IDENTIDADE DE ENTIDADE",
                        "explicacao": "Única por tabela. Jamais aceita valor NULL nem valores repetidos.",
                        "cor": "amber",
                    },
                    {
                        "termo": "FOREIGN KEY",
                        "destaque_letra": "FK",
                        "gatilho": "INTEGRIDADE REFERENCIAL",
                        "explicacao": "Aponta para a PK de outra tabela. PODE aceitar NULL (salvo restrição explícita).",
                        "cor": "sky",
                    },
                    {
                        "termo": "CANDIDATA",
                        "destaque_letra": "MÍNIMA",
                        "gatilho": "SUPERCHAVE IRREDUTÍVEL",
                        "explicacao": "Identifica a linha sem nenhum atributo supérfluo (ex: CPF ou Matrícula).",
                        "cor": "emerald",
                    },
                ],
                "regra_rodape": "PEGADINHA DE PROVA: CHAVE ESTRANGEIRA (FK) PODE TER VALORES REPETIDOS E PODE SER NULL!",
            },
        },
    ],
    "bd-02": [
        {
            "id": "fc-sql-01",
            "tipo": "comparacao",
            "tag": "SQL · Comandos",
            "dificuldade_sugerida": "facil",
            "frente": "Qual a diferença entre DELETE, TRUNCATE e DROP no SQL?",
            "verso": "DELETE (DML) apaga linhas específicas com WHERE e permite ROLLBACK. TRUNCATE (DDL) esvazia toda a tabela rapidamente sem WHERE. DROP (DDL) destrói a própria tabela e sua estrutura.",
            "mnemonico": "DELETE = Cirúrgico (WHERE) | TRUNCATE = Zera dados | DROP = Demole a tabela",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · SQL",
                "titulo": "DELETE x TRUNCATE x DROP",
                "subtitulo": "Nunca mais erre a classificação DDL vs DML na prova:",
                "colunas": [
                    {
                        "termo": "DELETE",
                        "destaque_letra": "DML",
                        "gatilho": "ACEITA CLÁUSULA WHERE",
                        "explicacao": "Apaga linha por linha, grava log detalhado e dispara triggers.",
                        "cor": "emerald",
                    },
                    {
                        "termo": "TRUNCATE",
                        "destaque_letra": "DDL",
                        "gatilho": "ESVAZIA A TABELA INTEIRA",
                        "explicacao": "Não aceita WHERE! Limpa todos os registros de uma vez e mantém a estrutura.",
                        "cor": "amber",
                    },
                    {
                        "termo": "DROP",
                        "destaque_letra": "DDL",
                        "gatilho": "APAGA DADOS + ESTRUTURA",
                        "explicacao": "Elimina a tabela inteira do catálogo do banco de dados.",
                        "cor": "rose",
                    },
                ],
                "regra_rodape": "SE A QUESTÃO COLOCAR 'TRUNCATE TABLE ALUNOS WHERE ID = 1', MARQUE ERRADO NA HORA!",
            },
        },
        {
            "id": "fc-sql-02",
            "tipo": "comparacao",
            "tag": "SQL · Filtros",
            "dificuldade_sugerida": "media",
            "frente": "Quando usar WHERE e quando usar HAVING em uma consulta SQL?",
            "verso": "WHERE filtra linhas individuais ANTES do GROUP BY e proíbe funções de agregação. HAVING filtra grupos DEPOIS do GROUP BY e aceita COUNT, SUM, AVG.",
            "mnemonico": "WHERE = Antes do grupo (sem COUNT) | HAVING = Depois do grupo (com COUNT)",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · AGRUPAMENTO SQL",
                "titulo": "WHERE x HAVING",
                "subtitulo": "A ordem de execução define quem filtra linhas e quem filtra grupos:",
                "colunas": [
                    {
                        "termo": "WHERE",
                        "destaque_letra": "LINHAS",
                        "gatilho": "ANTES DO GROUP BY",
                        "explicacao": "Filtra registros brutos da tabela. PROIBIDO usar COUNT(), SUM(), AVG() direto nele!",
                        "cor": "sky",
                    },
                    {
                        "termo": "HAVING",
                        "destaque_letra": "GRUPOS",
                        "gatilho": "DEPOIS DO GROUP BY",
                        "explicacao": "Filtra o resultado agrupado. É o lugar certo para HAVING COUNT(*) > 5!",
                        "cor": "amber",
                    },
                ],
                "regra_rodape": "ORDEM REAL DE EXECUÇÃO: FROM ➔ WHERE ➔ GROUP BY ➔ HAVING ➔ SELECT ➔ ORDER BY!",
            },
        },
    ],
    "es-01": [
        {
            "id": "fc-es-01",
            "tipo": "comparacao",
            "tag": "Engenharia de Software · Scrum",
            "dificuldade_sugerida": "facil",
            "frente": "Quem faz o quê no Scrum? (Product Owner vs Scrum Master vs Developers)",
            "verso": "Product Owner = Maximiza valor e prioriza o Product Backlog. Scrum Master = Líder servidor que garante o processo e remove impedimentos. Developers = Estimam e entregam o Incremento.",
            "mnemonico": "PO = O Quê (Negócio) | Dev = Como/Quanto (Técnico) | SM = Processo/Fluxo",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · SCRUM GUIDE",
                "titulo": "PRODUCT OWNER x SCRUM MASTER x DEVS",
                "subtitulo": "As bancas adoram inverter as responsabilidades dos 3 papéis:",
                "colunas": [
                    {
                        "termo": "PRODUCT OWNER",
                        "destaque_letra": "PO",
                        "gatilho": "DONO DO PRODUCT BACKLOG",
                        "explicacao": "Prioriza itens por valor de negócio. Único que pode cancelar uma Sprint!",
                        "cor": "amber",
                    },
                    {
                        "termo": "SCRUM MASTER",
                        "destaque_letra": "SM",
                        "gatilho": "GUARDIÃO DO MÉTODO",
                        "explicacao": "NÃO é chefe! Não distribui tarefas. Remove impedimentos e treina o time.",
                        "cor": "emerald",
                    },
                    {
                        "termo": "DEVELOPERS",
                        "destaque_letra": "TIME",
                        "gatilho": "DONOS DO SPRINT BACKLOG",
                        "explicacao": "Auto-organizados: somente eles definem COMO fazer e estimam o esforço.",
                        "cor": "sky",
                    },
                ],
                "regra_rodape": "SE A PROVA DISSER QUE O SCRUM MASTER PRIORIZA O BACKLOG OU CHEFIA O TIME, ESTÁ ERRADO!",
            },
        },
    ],
    "es-02": [
        {
            "id": "fc-gof-01",
            "tipo": "comparacao",
            "tag": "Padrões de Projeto · GoF",
            "dificuldade_sugerida": "media",
            "frente": "Como diferenciar ADAPTER, FACADE e DECORATOR (Padrões Estruturais GoF)?",
            "verso": "Adapter CONVERTE uma interface incompatível. Facade SIMPLIFICA um subsistema complexo. Decorator ADICIONA responsabilidades dinamicamente mantendo a mesma interface.",
            "mnemonico": "Adapter = Conversor de tomada | Facade = Recepção simples | Decorator = Camada extra",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · PADRÕES GOF",
                "titulo": "ADAPTER x FACADE x DECORATOR",
                "subtitulo": "Os 3 padrões estruturais mais cobrados pela FGV e Cebraspe:",
                "colunas": [
                    {
                        "termo": "ADAPTER",
                        "destaque_letra": "CONVERTE",
                        "gatilho": "INTERFACE INCOMPATÍVEL",
                        "explicacao": "Faz um sistema novo conversar com um legado (como um adaptador de tomada).",
                        "cor": "amber",
                    },
                    {
                        "termo": "FACADE",
                        "destaque_letra": "SIMPLIFICA",
                        "gatilho": "FACHADA ÚNICA LIMPA",
                        "explicacao": "Esconde 10 classes complexas atrás de 1 método simples de alto nível.",
                        "cor": "sky",
                    },
                    {
                        "termo": "DECORATOR",
                        "destaque_letra": "EXPANDE",
                        "gatilho": "SEM USAR HERANÇA",
                        "explicacao": "Empacota o objeto para adicionar comportamento em tempo de execução.",
                        "cor": "emerald",
                    },
                ],
                "regra_rodape": "PALAVRA-CHAVE NA PROVA: 'INCOMPATIBILIDADE' = ADAPTER | 'SIMPLIFICAR SUBSISTEMA' = FACADE!",
            },
        },
    ],
    "dir-01": [
        {
            "id": "fc-dir-01",
            "tipo": "comparacao",
            "tag": "Constitucional · Art. 5º",
            "dificuldade_sugerida": "facil",
            "frente": "Qual remédio constitucional usar em cada caso do Art. 5º da CF/88?",
            "verso": "HC = Locomoção. HD = Dados pessoais em bancos públicos (exige recusa prévia). MS = Direito líquido e certo residual (120 dias). MI = Falta de norma regulamentadora. Ação Popular = Cidadão contra lesão ao patrimônio público.",
            "mnemonico": "HC e HD = Gratuitos! Ação Popular = Só CIDADÃO (Título de Eleitor)!",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · CONSTITUCIONAL",
                "titulo": "OS 5 REMÉDIOS CONSTITUCIONAIS",
                "subtitulo": "Associação imediata entre palavra-gatilho e o remédio correto:",
                "colunas": [
                    {
                        "termo": "HABEAS CORPUS / DATA",
                        "destaque_letra": "GRATUITOS",
                        "gatilho": "LOCOMOÇÃO vs DADOS",
                        "explicacao": "HC = Ir e vir (não precisa advogado). HD = Ver/retificar dado próprio (exige recusa prévia).",
                        "cor": "emerald",
                    },
                    {
                        "termo": "MANDADO SEG. / INJ.",
                        "destaque_letra": "MS x MI",
                        "gatilho": "LÍQUIDO E CERTO vs OMISSÃO",
                        "explicacao": "MS = Prova documental pré-constituída (120 dias). MI = Falta de lei regulamentadora.",
                        "cor": "amber",
                    },
                    {
                        "termo": "AÇÃO POPULAR",
                        "destaque_letra": "CIDADÃO",
                        "gatilho": "PATRIMÔNIO E MORALIDADE",
                        "explicacao": "Exige título de eleitor! Pessoa Jurídica NÃO pode propor (Súmula 365 STF).",
                        "cor": "sky",
                    },
                ],
                "regra_rodape": "CASA INVIOLÁVEL: À NOITE SÓ ENTRA EM FLAGRANTE, DESASTRE OU SOCORRO (ORDEM JUDICIAL = SÓ DE DIA)!",
            },
        },
    ],
    "red-01": [
        {
            "id": "fc-red-01",
            "tipo": "comparacao",
            "tag": "Redes · Transporte",
            "dificuldade_sugerida": "facil",
            "frente": "Quais as diferenças vitais entre TCP e UDP na Camada de Transporte?",
            "verso": "TCP = Orientado a conexão (SYN, SYN-ACK, ACK), confiável, controle de fluxo e congestionamento. UDP = Sem conexão, baixa latência, cabeçalho leve de 8 bytes, ideal para DNS e streaming.",
            "mnemonico": "TCP = Entrega Garantida (Handshake) | UDP = Velocidade Máxima (Sem Handshake)",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · REDES DE COMPUTADORES",
                "titulo": "TCP x UDP & UNIDADES DE DADOS (PDU)",
                "subtitulo": "O quadro que resolve 80% das questões de Redes em concursos:",
                "colunas": [
                    {
                        "termo": "PROTOCOLO TCP",
                        "destaque_letra": "CONEXÃO",
                        "gatilho": "SYN ➔ SYN-ACK ➔ ACK",
                        "explicacao": "Garante entrega, ordem e controle de fluxo. Usado em HTTP(80), HTTPS(443), SSH(22).",
                        "cor": "emerald",
                    },
                    {
                        "termo": "PROTOCOLO UDP",
                        "destaque_letra": "VELOCIDADE",
                        "gatilho": "SEM CONFIRMAÇÃO",
                        "explicacao": "Não faz handshake nem retransmissão. Usado em DNS(53), DHCP(67/68) e VoIP.",
                        "cor": "amber",
                    },
                    {
                        "termo": "PDUs DO MODELO OSI",
                        "destaque_letra": "CAMADAS 4-3-2",
                        "gatilho": "SEGMENTO · PACOTE · QUADRO",
                        "explicacao": "C4 Transporte = Segmento | C3 Rede = Pacote (IP) | C2 Enlace = Quadro (MAC).",
                        "cor": "sky",
                    },
                ],
                "regra_rodape": "MNEMÔNICO DAS 7 CAMADAS OSI (1 A 7): F-E-R-T-S-A-A (Física, Enlace, Rede, Transporte, Sessão, Apres., Aplicação)!",
            },
        },
    ],
    "seg-01": [
        {
            "id": "fc-seg-01",
            "tipo": "comparacao",
            "tag": "Segurança · Criptografia",
            "dificuldade_sugerida": "facil",
            "frente": "Qual chave cifra no Sigilo e qual chave cifra na Assinatura Digital?",
            "verso": "Para CONFIDENCIALIDADE (Sigilo), cifra com a chave PÚBLICA do destinatário. Para ASSINATURA DIGITAL (Autenticidade/Não-repúdio), cifra o hash com a chave PRIVADA do remetente.",
            "mnemonico": "Sigilo = Pública do Destino | Assinatura = Privada do Autor",
            "esquema_jotta": {
                "selo": "MAPA VISUAL · CRIPTOGRAFIA",
                "titulo": "SIGILO x ASSINATURA DIGITAL x HASH",
                "subtitulo": "A pegadinha nº 1 das bancas de TI desmascarada visualmente:",
                "colunas": [
                    {
                        "termo": "SIGILO ASSIMÉTRICO",
                        "destaque_letra": "PÚBLICA",
                        "gatilho": "DO DESTINATÁRIO",
                        "explicacao": "Qualquer um tranca com a Pública do destino; só ele abre com a Privada dele.",
                        "cor": "sky",
                    },
                    {
                        "termo": "ASSINATURA DIGITAL",
                        "destaque_letra": "PRIVADA",
                        "gatilho": "DO PRÓPRIO REMETENTE",
                        "explicacao": "O autor assina o Hash com sua Privada; todos conferem com a Pública dele.",
                        "cor": "amber",
                    },
                    {
                        "termo": "FUNÇÃO HASH",
                        "destaque_letra": "SHA-256",
                        "gatilho": "SEM CHAVE · UNIDIRECIONAL",
                        "explicacao": "Garante INTEGRIDADE (qualquer vírgula alterada muda todo o resumo hash).",
                        "cor": "emerald",
                    },
                ],
                "regra_rodape": "ATENÇÃO: ASSINATURA DIGITAL NÃO ESCONDE O DOCUMENTO (NÃO GARANTE CONFIDENCIALIDADE SOZINHA)!",
            },
        },
    ],
}


# ==============================================================================
# Quadros Visuais Interativos (Sem repetição de texto, claros e objetivos)
# ==============================================================================

LESSON_VISUAL_BOARDS: dict[str, dict[str, Any]] = {
    "port-01": {
        "titulo": "Quadro Esquematizado: Conectivos e Relações Semânticas",
        "subtitulo": "Compare o valor semântico, os conectivos equivalentes e a armadilha clássica de cada grupo.",
        "relacoes_conceituais": [
            {
                "id": "rel-concessao",
                "categoria": "CONCESSÃO (Quebra de Expectativa)",
                "cor": "amber",
                "regra_ouro": "Introduz um obstáculo que NÃO impede o fato principal de acontecer.",
                "conectivos": ["embora", "conquanto", "ainda que", "mesmo que", "posto que", "apesar de"],
                "fluxo_visual": "Obstáculo vencido  ➔  Verbo no Subjuntivo",
                "exemplo_destacado": "Conquanto a prova fosse difícil, o candidato foi aprovado.",
                "armadilha_banca": "Nunca troque 'conquanto' (concessivo) por 'porquanto' (causal).",
            },
            {
                "id": "rel-causa",
                "categoria": "CAUSA / EXPLICAÇÃO (Origem)",
                "cor": "emerald",
                "regra_ouro": "Indica o motivo cronologicamente anterior que gera um resultado.",
                "conectivos": ["porque", "já que", "visto que", "porquanto", "uma vez que", "na medida em que"],
                "fluxo_visual": "Motivo (Antes)  ➔  Efeito (Depois)",
                "exemplo_destacado": "Como estudou pelas aulas esquematizadas, acertou 95% da prova.",
                "armadilha_banca": "'Na medida em que' = Causa | 'À medida que' = Proporção.",
            },
            {
                "id": "rel-adversidade",
                "categoria": "OPOSIÇÃO / ADVERSIDADE (Contraste)",
                "cor": "rose",
                "regra_ouro": "Opõe duas ideias coordenadas fazendo prevalecer o segundo argumento.",
                "conectivos": ["mas", "porém", "contudo", "todavia", "entretanto", "no entanto"],
                "fluxo_visual": "Ideia A  ➔  [MAS / PORÉM]  ➔  Ideia B (Prevalece)",
                "exemplo_destacado": "Tinha pouco tempo livre; manteve, contudo, a constância diária.",
                "armadilha_banca": "'Mas' só aparece no início da oração; os demais podem vir entre vírgulas.",
            },
            {
                "id": "rel-consequencia",
                "categoria": "CONSEQUÊNCIA (Resultado)",
                "cor": "sky",
                "regra_ouro": "Aponta o efeito inevitável provocado pela intensidade da oração anterior.",
                "conectivos": ["tanto que", "de modo que", "tão... que", "de forma que"],
                "fluxo_visual": "Intensidade (Tão/Tanto)  ➔  QUE (Resultado)",
                "exemplo_destacado": "Treinou tanto com questões reais que dominou o estilo da banca.",
                "armadilha_banca": "Reescrever invertendo as orações transforma a consecutiva em causal.",
            },
        ],
        "passos_animados": [
            {
                "passo": 1,
                "titulo": "Passo 1: Diferencie Conquanto vs Porquanto",
                "detalhe": "Olhe o prefixo: CONquanto = CONcessão (Embora). PORquanto = PORque (Causa).",
                "destaque_codigo": "Conquanto (Embora) ≠ Porquanto (Porque)",
            },
            {
                "passo": 2,
                "titulo": "Passo 2: Verifique Sessão vs Cessão vs Seção",
                "detalhe": "Sessão (SS) = Reunião/Tempo. Cessão (C) = Ato de ceder. Seção (Ç) = Setor/Repartição.",
                "destaque_codigo": "Sessão (Reunião) · Cessão (Ceder) · Seção (Setor)",
            },
            {
                "passo": 3,
                "titulo": "Passo 3: Isole Expressões Explicativas por Vírgulas",
                "detalhe": "'Por exemplo', 'isto é' e 'ou seja' ficam sempre separados por vírgula em qualquer posição.",
                "destaque_codigo": "..., por exemplo, ... | Por exemplo, ... | ..., por exemplo.",
            },
        ],
    },
    "bd-01": {
        "titulo": "Quadro Esquematizado: Evolução das Formas Normais (1FN ➔ 2FN ➔ 3FN)",
        "subtitulo": "Entenda exatamente qual anomalia cada etapa elimina sem repetir conceitos.",
        "relacoes_conceituais": [
            {
                "id": "fn-1",
                "categoria": "1ª FORMA NORMAL (1FN)",
                "cor": "amber",
                "regra_ouro": "Cada célula da tabela deve conter apenas 1 valor atômico (indivisível).",
                "conectivos": ["Atributos Atômicos", "Sem Listas", "Sem Grupos Repetitivos"],
                "fluxo_visual": "Célula com 2 telefones  ➔  Divide em linhas atômicas",
                "exemplo_destacado": "Transformar Telefones='9999-1111, 8888-2222' em registros individuais.",
                "armadilha_banca": "Toda relação formal no modelo relacional já exige a 1FN como ponto de partida.",
            },
            {
                "id": "fn-2",
                "categoria": "2ª FORMA NORMAL (2FN)",
                "cor": "emerald",
                "regra_ouro": "Elimina Dependência Parcial: colunas não-chave devem depender de TODA a chave composta.",
                "conectivos": ["Estar na 1FN", "Sem Dependência Parcial", "Foco na PK Composta"],
                "fluxo_visual": "PK(Pedido, Produto)  ➔  Nome_Produto só depende de Produto (Extrair!)",
                "exemplo_destacado": "Se a PK tem apenas 1 coluna (simples) e está na 1FN, já está automaticamente na 2FN.",
                "armadilha_banca": "Cebraspe cobra frequentemente que tabela em 1FN com PK simples já está na 2FN.",
            },
            {
                "id": "fn-3",
                "categoria": "3ª FORMA NORMAL (3FN)",
                "cor": "sky",
                "regra_ouro": "Elimina Dependência Transitiva: nenhuma coluna comum pode determinar outra coluna comum.",
                "conectivos": ["Estar na 2FN", "Sem Dependência Transitiva", "Não-Chave ↛ Não-Chave"],
                "fluxo_visual": "PK(Matrícula) ➔ Cod_Depto ➔ Nome_Depto (Separar tabela Depto!)",
                "exemplo_destacado": "Mover Nome_Depto para uma tabela própria referenciada por Cod_Depto.",
                "armadilha_banca": "FGV apresenta R(A,B,C) onde PK=(A) e B → C, perguntando a violação (3FN).",
            },
        ],
        "passos_animados": [
            {
                "passo": 1,
                "titulo": "Passo 1: Cheque se há listas na célula (1FN)",
                "detalhe": "Se houver valores múltiplos na mesma coluna, decomponha para atingir a 1FN.",
                "destaque_codigo": "1FN = Apenas valores atômicos e indivisíveis",
            },
            {
                "passo": 2,
                "titulo": "Passo 2: Olhe para a Chave Primária (2FN)",
                "detalhe": "PK simples? Já passou na 2FN! PK composta? Garanta que tudo dependa do par inteiro.",
                "destaque_codigo": "2FN = Elimina Dependência Parcial (PK Composta)",
            },
            {
                "passo": 3,
                "titulo": "Passo 3: Procure pontes entre colunas comuns (3FN)",
                "detalhe": "Se uma coluna não-chave define outra não-chave (ex: CEP define Cidade), separe em outra tabela.",
                "destaque_codigo": "3FN = Elimina Dependência Transitiva (Não-Chave ➔ Não-Chave)",
            },
        ],
    },
    "es-02": {
        "titulo": "Quadro Esquematizado: Padrões de Projeto GoF & Princípios SOLID",
        "subtitulo": "Divisão clara entre Criacionais, Estruturais e Comportamentais com o caso exato de prova.",
        "relacoes_conceituais": [
            {
                "id": "gof-criacionais",
                "categoria": "PADRÕES CRIACIONAIS",
                "cor": "amber",
                "regra_ouro": "Abstraem o processo de instanciação, desacoplando o sistema de como os objetos são criados.",
                "conectivos": ["Singleton", "Factory Method", "Abstract Factory", "Builder", "Prototype"],
                "fluxo_visual": "Código Cliente  ➔  Fábrica / Construtor  ➔  Objeto Instanciado",
                "exemplo_destacado": "Singleton garante instância única (ex: Pool de Conexão ou Logger global).",
                "armadilha_banca": "Abstract Factory cria FAMÍLIAS de objetos relacionados; Builder constrói objetos complexos passo a passo.",
            },
            {
                "id": "gof-estruturais",
                "categoria": "PADRÕES ESTRUTURAIS",
                "cor": "emerald",
                "regra_ouro": "Organizam a composição de classes e interfaces para formar estruturas flexíveis.",
                "conectivos": ["Adapter", "Facade", "Decorator", "Proxy", "Composite", "Bridge"],
                "fluxo_visual": "Interface A  ➔  [Adapter / Facade / Decorator]  ➔  Sistema B",
                "exemplo_destacado": "Decorator adiciona novas funções ao objeto dinamicamente sem usar herança.",
                "armadilha_banca": "Adapter CONVERTE interface incompatível; Facade SIMPLIFICA subsistema complexo.",
            },
            {
                "id": "gof-comportamentais",
                "categoria": "PADRÕES COMPORTAMENTAIS",
                "cor": "sky",
                "regra_ouro": "Gerenciam algoritmos, notificações e distribuição de responsabilidades entre objetos.",
                "conectivos": ["Strategy", "Observer", "Command", "State", "Template Method", "Mediator"],
                "fluxo_visual": "Contexto  ➔  Troca de Algoritmo (Strategy) ou Notificação (Observer)",
                "exemplo_destacado": "Strategy permite trocar a regra de cálculo de imposto em tempo de execução.",
                "armadilha_banca": "Observer implementa Pub/Sub (1-para-N); Command encapsula uma requisição como objeto.",
            },
        ],
        "passos_animados": [
            {
                "passo": 1,
                "titulo": "Passo 1: Identifique se o problema é de Criação, Estrutura ou Comportamento",
                "detalhe": "Instanciar sem new explícito = Criacional. Conectar interfaces = Estrutural. Trocar algoritmo/evento = Comportamental.",
                "destaque_codigo": "Criacional (Instanciar) · Estrutural (Compor) · Comportamental (Interagir)",
            },
            {
                "passo": 2,
                "titulo": "Passo 2: Não confunda Adapter, Facade e Decorator",
                "detalhe": "Adapter compatibiliza; Facade oferece porta única simplificada; Decorator empacota responsabilidades extras.",
                "destaque_codigo": "Adapter (Converte) ≠ Facade (Simplifica) ≠ Decorator (Expande)",
            },
            {
                "passo": 3,
                "titulo": "Passo 3: Aplique o SOLID (Foco em O e D)",
                "detalhe": "Open/Closed = Aberto para extensão, fechado para modificação. Dependency Inversion = Dependa de interfaces.",
                "destaque_codigo": "S.O.L.I.D ➔ Baixo acoplamento e alta coesão",
            },
        ],
    },
}


def _build_default_visual_board(lesson: dict[str, Any]) -> dict[str, Any]:
    """Constrói um quadro visual limpo e sem repetição de frases."""
    lid = lesson["id"]
    if lid in LESSON_VISUAL_BOARDS:
        return LESSON_VISUAL_BOARDS[lid]

    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []
    cores = ["amber", "emerald", "sky", "rose", "purple"]
    pontos = lesson.get("pontos_criticos") or []

    relacoes = []
    for idx, row in enumerate(linhas):
        cat = row[0] if len(row) > 0 else f"Conceito {idx + 1}"
        col1 = row[1] if len(row) > 1 else ""
        col2 = row[2] if len(row) > 2 else ""
        col3 = row[3] if len(row) > 3 else (pontos[idx % len(pontos)] if pontos else "")

        tags_extraidas = [c.strip() for c in col1.split(",") if c.strip()]
        if len(tags_extraidas) <= 1:
            tags_extraidas = [cat]

        relacoes.append({
            "id": f"rel-{lid}-{idx}",
            "categoria": cat.upper(),
            "cor": cores[idx % len(cores)],
            "regra_ouro": col2 if col2 else col1,
            "conectivos": tags_extraidas[:5],
            "fluxo_visual": f"{cat}  ➔  {col1}",
            "exemplo_destacado": col3 if col3 else col2,
            "armadilha_banca": pontos[idx % len(pontos)] if pontos else col3,
        })

    passos = []
    for idx, ponto in enumerate(pontos):
        passos.append({
            "passo": idx + 1,
            "titulo": f"Passo {idx + 1}: Verificação de Prova",
            "detalhe": ponto,
            "destaque_codigo": (lesson.get("objetivos") or [ponto])[min(idx, len(lesson.get("objetivos") or [ponto]) - 1)],
        })

    return {
        "titulo": f"Quadro Esquematizado: {tabela.get('titulo') or lesson['titulo']}",
        "subtitulo": "Síntese visual direta para memorização rápida antes das questões.",
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
                {"id": f"mm-{lid}-{idx}-a", "label": f"Conceito: {desc_no[:70]}"},
                {"id": f"mm-{lid}-{idx}-b", "label": f"Na Prova: {aplicacao[:70]}"},
            ],
        })

    return {
        "no_central": lesson["titulo"].split(":")[-1].strip(),
        "disciplina": lesson["disciplina"],
        "nos": nos,
    }


def _enrich_videos(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    """Enriquece as videoaulas com capítulos clicáveis, perguntas de checkpoint e slides guiados."""
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
                    "tempo_seg": 180,
                    "tempo_label": "03:00",
                    "resumo": objetivos[1] if len(objetivos) > 1 else "Análise detalhada dos conceitos cobrados em edital.",
                },
                {
                    "id": f"cap-{lesson['id']}-{v_idx}-3",
                    "titulo": "03. Pegadinhas de Banca & Casos Práticos",
                    "tempo_seg": 420,
                    "tempo_label": "07:00",
                    "resumo": pontos[0] if len(pontos) > 0 else "Como FGV e Cebraspe cobram o tema em provas reais.",
                },
                {
                    "id": f"cap-{lesson['id']}-{v_idx}-4",
                    "titulo": "04. Revisão Final & Resolução de Questões",
                    "tempo_seg": 660,
                    "tempo_label": "11:00",
                    "resumo": objetivos[-1] if len(objetivos) > 0 else "Consolidação e checklist final para gabaritar.",
                },
            ]

        if "perguntas_video" not in v_copy:
            fc_ref = fcs[v_idx % len(fcs)] if fcs else None
            v_copy["perguntas_video"] = [
                {
                    "id": f"pv-{lesson['id']}-{v_idx}-1",
                    "momento_seg": 180,
                    "momento_label": "03:00",
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


def _synthesize_jotta_schema(card: dict[str, Any], lesson: dict[str, Any], idx: int) -> dict[str, Any]:
    """Gera automaticamente um esquema visual estilo Jotta caso o cartão não possua um específico."""
    if "esquema_jotta" in card and card["esquema_jotta"]:
        return card["esquema_jotta"]

    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []
    cores = ["amber", "sky", "emerald", "rose"]

    colunas = []
    if len(linhas) >= 2:
        for c_idx, row in enumerate(linhas[:3]):
            colunas.append({
                "termo": str(row[0]).upper(),
                "destaque_letra": f"REGRA #{c_idx + 1}",
                "gatilho": str(row[1])[:42].upper(),
                "explicacao": str(row[2] if len(row) > 2 else row[1]),
                "cor": cores[c_idx % len(cores)],
            })
    else:
        colunas = [
            {
                "termo": card.get("tag", lesson["disciplina"]).upper(),
                "destaque_letra": "CONCEITO CHAVE",
                "gatilho": (card.get("mnemonico") or "MEMORIZAÇÃO DIRETA")[:42].upper(),
                "explicacao": card.get("verso", ""),
                "cor": "amber",
            }
        ]

    return {
        "selo": f"MAPA VISUAL GSN · #{idx + 1:02d}",
        "titulo": card.get("frente", lesson["titulo"]),
        "subtitulo": card.get("verso", ""),
        "colunas": colunas,
        "regra_rodape": (card.get("mnemonico") or (lesson.get("pontos_criticos") or ["Domine esta distinção para a prova!"])[0]).upper(),
    }


def _enrich_flashcards(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    """Retorna os flashcards enriquecidos com o Esquema Visual Estilo Jotta + formatos de treino."""
    lid = lesson["id"]
    jotta_cards = [dict(c) for c in JOTTA_VISUAL_CARDS.get(lid, [])]
    seen_ids = {c["id"] for c in jotta_cards}

    base_cards = list(jotta_cards)
    tipos_base = ["pergunta_resposta", "conceito_definicao", "comparacao", "exemplo_pratico"]

    for idx, raw_fc in enumerate(lesson.get("flashcards") or []):
        if raw_fc["id"] in seen_ids:
            continue
        card = dict(raw_fc)
        if "tipo" not in card:
            card["tipo"] = tipos_base[idx % len(tipos_base)]
        if "dificuldade_sugerida" not in card:
            card["dificuldade_sugerida"] = "media"
        card["esquema_jotta"] = _synthesize_jotta_schema(card, lesson, len(base_cards))
        base_cards.append(card)
        seen_ids.add(card["id"])

    pontos = lesson.get("pontos_criticos") or []
    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []

    # Adicionar cartão Verdadeiro ou Falso
    if pontos:
        vf_card: dict[str, Any] = {
            "id": f"fc-{lid}-vf",
            "tipo": "verdadeiro_falso",
            "frente": f"[Julgue V ou F] {pontos[0]}",
            "verso": f"VERDADEIRO! Esta é uma regra de ouro essencial desta aula: {pontos[0]}",
            "mnemonico": "Afirmativa 100% alinhada com a jurisprudência/norma técnica das bancas.",
            "tag": lesson["disciplina"],
            "dificuldade_sugerida": "facil",
            "resposta_vf": "V",
        }
        vf_card["esquema_jotta"] = _synthesize_jotta_schema(vf_card, lesson, len(base_cards))
        base_cards.append(vf_card)

    # Adicionar cartão Complete a Lacuna
    if linhas and len(linhas[0]) >= 2:
        conceito_alvo = linhas[0][0]
        definicao_alvo = linhas[0][1]
        opcoes = [linhas[i][0] for i in range(min(4, len(linhas)))]
        if len(opcoes) < 3:
            opcoes = [conceito_alvo, "Exceção Secundária", "Regra Inversa"]
        lac_card: dict[str, Any] = {
            "id": f"fc-{lid}-lacuna",
            "tipo": "complete_lacuna",
            "frente": f"Complete a lacuna técnica: O conceito de [_______] exige como requisito fundamental: '{definicao_alvo}'.",
            "verso": f"Resposta correta: {conceito_alvo}. ({definicao_alvo})",
            "mnemonico": f"{conceito_alvo} ➔ {definicao_alvo[:50]}",
            "tag": lesson["disciplina"],
            "dificuldade_sugerida": "media",
            "lacuna_correta": conceito_alvo,
            "lacuna_opcoes": opcoes,
        }
        lac_card["esquema_jotta"] = _synthesize_jotta_schema(lac_card, lesson, len(base_cards))
        base_cards.append(lac_card)

    for idx, c in enumerate(base_cards):
        c["aula_id"] = lid
        c["aula_titulo"] = lesson["titulo"]
        c["disciplina"] = lesson["disciplina"]
        if "esquema_jotta" not in c:
            c["esquema_jotta"] = _synthesize_jotta_schema(c, lesson, idx)

    return base_cards


def _build_interactive_exercises(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    """Constrói exercícios interativos estilo H5P/Brilliant para o Laboratório da Aula."""
    lid = lesson["id"]
    tabela = lesson.get("tabela_resumo") or {}
    linhas = tabela.get("linhas") or []
    pontos = lesson.get("pontos_criticos") or []

    exercicios: list[dict[str, Any]] = []

    if len(linhas) >= 3:
        pares = [
            {"id": f"par-{idx}", "conceito": row[0], "definicao": row[1]}
            for idx, row in enumerate(linhas[:4])
            if len(row) >= 2
        ]
        exercicios.append({
            "id": f"ex-{lid}-associacao",
            "tipo": "associacao_conceitos",
            "titulo": "Desafio Rápido: Associação de Conceitos",
            "enunciado": "Confira a associação direta entre cada conceito e sua palavra-gatilho de prova:",
            "pares": pares,
            "explicacao": "Dominar a distinção exata entre as definições evita cair na armadilha de inversão conceitual da FGV e do Cebraspe.",
        })

    if len(linhas) >= 2:
        row0 = linhas[0]
        opcoes = [r[0] for r in linhas[:4]]
        exercicios.append({
            "id": f"ex-{lid}-lacuna",
            "tipo": "complete_lacuna",
            "titulo": "Fixação Rápida: Complete a Lacuna",
            "enunciado": f"Em provas de {lesson['disciplina']}, quando o enunciado exige '{row0[1]}', a resposta correta é [_______].",
            "opcoes": opcoes,
            "resposta_correta": row0[0],
            "explicacao": f"{row0[0]} caracteriza-se diretamente por '{row0[1]}'. Atenção: {row0[3] if len(row0) > 3 else (pontos[0] if pontos else '')}",
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

    # 4. Flashcards Visuais Estilo Jotta
    out["flashcards"] = _enrich_flashcards(out)

    # 5. Questões Reais Detalhadas
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

        banca_tag = next((t.split(":")[1].upper() for t in q_item.get("tags", []) if t.startswith("banca:")), "OFICIAL")
        q_item["banca_sigla"] = banca_tag

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

    # 8. Estatísticas verificáveis de bancas
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
    enriched_fcs = _enrich_flashcards(l)
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
        "flashcards_count": len(enriched_fcs),
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


def list_all_visual_flashcards(base_lessons: list[dict[str, Any]], disciplina: str | None = None) -> list[dict[str, Any]]:
    """Retorna todos os Flashcards Visuais Estilo Jotta de todas as aulas (unificando Aulas e menu lateral Flashcards)."""
    cards: list[dict[str, Any]] = []
    disc_norm = disciplina.strip().lower() if disciplina else None
    for l in list(base_lessons) + _CUSTOM_LESSONS:
        if disc_norm and l["disciplina"].strip().lower() != disc_norm:
            continue
        cards.extend(_enrich_flashcards(l))
    return cards


def seed_default_flashcards(db_path: Path | str, base_lessons: list[dict[str, Any]]) -> int:
    """Popula o deck SM-2 (pratica_flashcards) com os cartões essenciais caso esteja vazio."""
    from radar.practice_store import create_flashcard, flashcard_stats

    stats = flashcard_stats(db_path)
    if stats.get("total", 0) > 0:
        return 0

    inserted = 0
    for l in base_lessons:
        for fc in JOTTA_VISUAL_CARDS.get(l["id"], [])[:2]:
            create_flashcard(
                db_path,
                frente=fc["frente"],
                verso=f"{fc['verso']}\n\n💡 Mnemônico: {fc.get('mnemonico', '')}",
                tags=[l["disciplina"], fc.get("tag", "Visual")],
                fonte=l["titulo"],
            )
            inserted += 1
    return inserted


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
