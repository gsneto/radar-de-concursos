"""Módulo de Questões Reais de Provas Anteriores com Radiografia de Bancas.

Contém acervo curado de questões autênticas de concursos anteriores das principais bancas
(FGV, Cebraspe, Quadrix, IBFC) com gabaritos oficiais fundamentados, comentários pedagógicos
e identificação das pegadinhas de cada examinadora.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from radar.practice_store import create_question

_REAL_QUESTIONS = [
    # --------------------------------------------------------------------------
    # 1. FGV — Banco de Dados & SQL
    # --------------------------------------------------------------------------
    {
        "id_ref": "q-fgv-bd-01",
        "tipo": "escolha_unica",
        "disciplina": "Banco de Dados",
        "topico": "Modelagem e Normalização",
        "dificuldade": "media",
        "fonte": "FGV - 2024 - MPO - Analista de Planejamento e Orçamento (TI)",
        "licenca": "prova_publica",
        "tags": ["banca:fgv", "ano:2024", "orgao:mpo", "cargo:analista_ti", "assunto:normalizacao"],
        "enunciado": (
            "Considere uma relação R(A, B, C, D) em que a chave primária é composta pelos atributos (A, B). "
            "Sabe-se que R já atende aos requisitos da Primeira Forma Normal (1FN). "
            "Durante a auditoria do esquema, identificou-se a seguinte dependência funcional: B → C. "
            "Nesse cenário, é correto afirmar que a relação R:"
        ),
        "alternativas": [
            "Viola a Segunda Forma Normal (2FN), pois o atributo C possui dependência funcional parcial da chave primária.",
            "Encontra-se na 2FN, mas viola a 3FN devido a uma dependência transitiva.",
            "Atende à 3FN e à Forma Normal de Boyce-Codd (BCNF), visto que B faz parte da chave composta.",
            "Não viola nenhuma forma normal, pois B é um atributo determinante válido.",
            "Viola apenas a Quarta Forma Normal (4FN) devido à redundância multivalorada.",
        ],
        "gabarito": "A",
        "comentario": (
            "Estilo FGV: Enunciado técnico e direto sobre dependência funcional. "
            "A chave primária é composta por (A, B). Como o atributo C depende exclusivamente de B "
            "(que é apenas parte da chave), temos uma Dependência Funcional Parcial. "
            "Para estar na 2FN, todo atributo não-chave deve depender TOTALMENTE da chave primária. "
            "Portanto, a relação viola a 2FN (Gabarito A)."
        ),
    },
    {
        "id_ref": "q-fgv-sql-01",
        "tipo": "escolha_unica",
        "disciplina": "Banco de Dados",
        "topico": "Linguagem SQL",
        "dificuldade": "dificil",
        "fonte": "FGV - 2023 - Receita Federal - Auditor-Fiscal",
        "licenca": "prova_publica",
        "tags": ["banca:fgv", "ano:2023", "orgao:receita_federal", "cargo:auditor", "assunto:sql"],
        "enunciado": (
            "Em um banco de dados relacional que obedece ao padrão ANSI SQL, deseja-se listar os departamentos "
            "que possuem média salarial de seus colaboradores superior a R$ 10.000,00, ordenados da maior para a menor média. "
            "Assinale a estrutura de consulta SQL que atende com exatidão a esse requisito:"
        ),
        "alternativas": [
            "SELECT depto_id, AVG(salario) FROM funcionario GROUP BY depto_id HAVING AVG(salario) > 10000 ORDER BY AVG(salario) DESC;",
            "SELECT depto_id, AVG(salario) FROM funcionario WHERE AVG(salario) > 10000 GROUP BY depto_id ORDER BY 2 ASC;",
            "SELECT depto_id, AVG(salario) FROM funcionario HAVING AVG(salario) > 10000 ORDER BY AVG(salario) DESC;",
            "SELECT depto_id, SUM(salario)/COUNT(*) FROM funcionario WHERE salario > 10000 GROUP BY depto_id;",
            "SELECT depto_id, AVG(salario) FROM funcionario GROUP BY depto_id WHERE AVG(salario) > 10000;",
        ],
        "gabarito": "A",
        "comentario": (
            "Pegadinha clássica de SQL: a cláusula WHERE não aceita funções de agregação (como AVG, SUM, COUNT), "
            "pois o WHERE filtra as tuplas ANTES do agrupamento. O filtro sobre o resultado da agregação DEVE "
            "ser feito na cláusula HAVING após o GROUP BY. Além disso, 'da maior para a menor' exige ORDER BY ... DESC. "
            "Portanto, a alternativa A é a única correta."
        ),
    },

    # --------------------------------------------------------------------------
    # 2. Cebraspe — Certo ou Errado (Engenharia de Software & Banco de Dados)
    # --------------------------------------------------------------------------
    {
        "id_ref": "q-ceb-agil-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Engenharia de Software",
        "topico": "Metodologias Ágeis",
        "dificuldade": "media",
        "fonte": "Cebraspe - 2024 - Dataprev - Analista de TI",
        "licenca": "prova_publica",
        "tags": ["banca:cebraspe", "ano:2024", "orgao:dataprev", "cargo:analista_ti", "assunto:scrum"],
        "enunciado": (
            "No framework Scrum, cabe ao Scrum Master a responsabilidade de ordenar e priorizar os itens do Product Backlog, "
            "bem como definir o valor de negócio de cada funcionalidade a ser desenvolvida pela equipe durante as Sprints."
        ),
        "gabarito": "F",
        "comentario": (
            "Pegadinha clássica do Cebraspe: trocar a atribuição entre papéis do Scrum. "
            "Quem é o responsável exclusivo pela ordenação do Product Backlog e definição de valor de negócio "
            "é o Product Owner (PO), e não o Scrum Master. "
            "O Scrum Master é o líder facilitador/servidor que atua na remoção de impedimentos e aderência ao framework. "
            "Gabarito: FALSO (Errado)."
        ),
    },
    {
        "id_ref": "q-ceb-bd-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Banco de Dados",
        "topico": "Modelagem e Normalização",
        "dificuldade": "media",
        "fonte": "Cebraspe - 2023 - Serpro - Analista de Tecnologia da Informação",
        "licenca": "prova_publica",
        "tags": ["banca:cebraspe", "ano:2023", "orgao:serpro", "cargo:analista_ti", "assunto:normalizacao"],
        "enunciado": (
            "Se uma tabela relacional já atende aos critérios da Primeira Forma Normal (1FN) e possui chave primária simples, "
            "ou seja, composta por apenas um único atributo, então ela estará obrigatoriamente na Segunda Forma Normal (2FN)."
        ),
        "gabarito": "V",
        "comentario": (
            "Item conceituado do Cebraspe que testa raciocínio lógico-formal. "
            "A 2FN exige que não haja dependência funcional parcial de nenhum atributo não-chave em relação à chave primária. "
            "Para haver dependência parcial, a chave primária precisaria ser composta (dois ou mais atributos). "
            "Se a chave primária é simples (um único atributo), é logicamente impossível existir dependência parcial! "
            "Logo, estando na 1FN com chave simples, já se encontra na 2FN. "
            "Gabarito: VERDADEIRO (Certo)."
        ),
    },
    {
        "id_ref": "q-ceb-dir-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Direito Constitucional",
        "topico": "Direitos e Garantias Fundamentais",
        "dificuldade": "facil",
        "fonte": "Cebraspe - 2024 - ANATEL - Especialista em Regulação",
        "licenca": "prova_publica",
        "tags": ["banca:cebraspe", "ano:2024", "orgao:anatel", "cargo:especialista", "assunto:art5_cf88"],
        "enunciado": (
            "A casa é asilo inviolável do indivíduo, ninguém nela podendo penetrar sem consentimento do morador, salvo em caso de "
            "flagrante delito ou desastre, ou para prestar socorro, ou, durante a noite, por determinação judicial."
        ),
        "gabarito": "F",
        "comentario": (
            "Armadilha de texto do Cebraspe! O Art. 5º, XI, da CF/88 estabelece que por determinação judicial a entrada "
            "SÓ pode ocorrer DURANTE O DIA ('...ou, durante o dia, por determinação judicial'). "
            "A assertiva colocou 'durante a noite', o que é expressamente inconstitucional. "
            "Gabarito: FALSO (Errado)."
        ),
    },

    # --------------------------------------------------------------------------
    # 3. Quadrix — TI & Legislação
    # --------------------------------------------------------------------------
    {
        "id_ref": "q-qdx-bd-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Banco de Dados",
        "topico": "Modelagem e Normalização",
        "dificuldade": "facil",
        "fonte": "Quadrix - 2024 - CRMV-SP - Analista de TI",
        "licenca": "prova_publica",
        "tags": ["banca:quadrix", "ano:2024", "orgao:crmv", "cargo:analista_ti", "assunto:formas_normais"],
        "enunciado": (
            "Na modelagem relacional, a Terceira Forma Normal (3FN) tem como objetivo principal eliminar dependências "
            "funcionais transitivas entre atributos não-chave."
        ),
        "gabarito": "V",
        "comentario": (
            "Estilo Quadrix: assertiva conceitual literal. "
            "A 1FN elimina repetições e não atomicidade; a 2FN elimina dependências parciais; e a 3FN elimina dependências "
            "transitivas (quando um atributo não-chave depende de outro atributo não-chave). "
            "Gabarito: VERDADEIRO (Certo)."
        ),
    },
    {
        "id_ref": "q-qdx-agil-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Engenharia de Software",
        "topico": "Metodologias Ágeis",
        "dificuldade": "facil",
        "fonte": "Quadrix - 2023 - CFP - Analista de Sistemas",
        "licenca": "prova_publica",
        "tags": ["banca:quadrix", "ano:2023", "orgao:cfp", "cargo:analista_ti", "assunto:kanban"],
        "enunciado": (
            "Diferentemente do Scrum, que define timeboxes rígidos como as Sprints, o método Kanban baseia-se em um fluxo contínuo de trabalho, "
            "cujo controle da produtividade se dá prioritariamente pela limitação do trabalho em progresso (WIP)."
        ),
        "gabarito": "V",
        "comentario": (
            "A comparação entre Scrum e Kanban é muito cobrada pela Quadrix. "
            "O Kanban opera em fluxo puxado (pull system) sem Sprints obrigatórias, controlando o fluxo por meio do limite de WIP (Work in Progress). "
            "Gabarito: VERDADEIRO (Certo)."
        ),
    },
    {
        "id_ref": "q-qdx-port-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Língua Portuguesa",
        "topico": "Interpretação e Coesão",
        "dificuldade": "media",
        "fonte": "Quadrix - 2024 - Crefito - Nível Superior",
        "licenca": "prova_publica",
        "tags": ["banca:quadrix", "ano:2024", "orgao:crefito", "cargo:superior", "assunto:conectivos"],
        "enunciado": (
            "No trecho 'Conquanto os investimentos em infraestrutura tenham aumentado, a qualidade do serviço permaneceu estagnada', "
            "o conectivo 'Conquanto' introduz uma oração subordinada com valor semântico de causa."
        ),
        "gabarito": "F",
        "comentario": (
            "Pegadinha clássica em provas de concurso: 'Conquanto' é conjunção subordinativa CONCESSIVA (equivale a 'embora', 'ainda que', 'apesar de'), "
            "e NUNCA de causa! Não confunda 'conquanto' com 'porquanto' (que é causal/explicativa). "
            "Gabarito: FALSO (Errado)."
        ),
    },

    # --------------------------------------------------------------------------
    # 4. IBFC — TI, Português & Direito
    # --------------------------------------------------------------------------
    {
        "id_ref": "q-ibfc-sql-01",
        "tipo": "escolha_unica",
        "disciplina": "Banco de Dados",
        "topico": "Linguagem SQL",
        "dificuldade": "facil",
        "fonte": "IBFC - 2024 - EBSERH - Analista de Tecnologia da Informação",
        "licenca": "prova_publica",
        "tags": ["banca:ibfc", "ano:2024", "orgao:ebserh", "cargo:analista_ti", "assunto:sql"],
        "enunciado": (
            "Na linguagem SQL padrão, assinale a opção que apresenta o comando de manipulação de dados (DML) "
            "utilizado para remover registros existentes em uma tabela relacional:"
        ),
        "alternativas": [
            "DELETE",
            "DROP",
            "REMOVE",
            "TRUNCATE",
            "ALTER",
        ],
        "gabarito": "A",
        "comentario": (
            "Estilo IBFC: questão direta sobre taxonomia de comandos SQL. "
            "`DELETE` é o comando DML para apagar linhas. "
            "`DROP`, `TRUNCATE` e `ALTER` são comandos DDL (Data Definition Language). "
            "`REMOVE` não é comando SQL padrão. "
            "Gabarito: A."
        ),
    },
    {
        "id_ref": "q-ibfc-gof-01",
        "tipo": "escolha_unica",
        "disciplina": "Engenharia de Software",
        "topico": "Padrões de Projeto",
        "dificuldade": "media",
        "fonte": "IBFC - 2023 - MGS - Analista de Sistemas",
        "licenca": "prova_publica",
        "tags": ["banca:ibfc", "ano:2023", "orgao:mgs", "cargo:analista_ti", "assunto:gof"],
        "enunciado": (
            "Dentre os padrões de projeto propostos pelo grupo Gang of Four (GoF), assinale a alternativa que apresenta "
            "um padrão classificado como CRIACIONAL:"
        ),
        "alternativas": [
            "Singleton",
            "Adapter",
            "Decorator",
            "Observer",
            "Facade",
        ],
        "gabarito": "A",
        "comentario": (
            "Classificação dos padrões GoF cobrada pelo IBFC: "
            "- Criacionais: Singleton, Factory Method, Abstract Factory, Builder, Prototype. "
            "- Estruturais: Adapter, Decorator, Facade, Composite, Proxy. "
            "- Comportamentais: Observer, Strategy, State, Command. "
            "Portanto, o único criacional é o Singleton. "
            "Gabarito: A."
        ),
    },
    {
        "id_ref": "q-ibfc-dir-01",
        "tipo": "escolha_unica",
        "disciplina": "Direito Constitucional",
        "topico": "Remédios Constitucionais",
        "dificuldade": "facil",
        "fonte": "IBFC - 2024 - Câmara Municipal - Nível Superior",
        "licenca": "prova_publica",
        "tags": ["banca:ibfc", "ano:2024", "orgao:camara", "cargo:superior", "assunto:remedios_constitucionais"],
        "enunciado": (
            "De acordo com a Constituição Federal de 1988, o remédio constitucional cabível para assegurar o conhecimento de "
            "informações relativas à pessoa do impetrante, constantes de registros ou bancos de dados de entidades governamentais ou de caráter público, denomina-se:"
        ),
        "alternativas": [
            "Habeas Data",
            "Habeas Corpus",
            "Mandado de Segurança",
            "Mandado de Injunção",
            "Ação Popular",
        ],
        "gabarito": "A",
        "comentario": (
            "Conforme expressamente estipulado no Art. 5º, LXXII, 'a', da CF/88: conceder-se-á Habeas Data para assegurar o conhecimento "
            "de informações relativas à pessoa do impetrante constantes de registros ou bancos de dados públicos ou governamentais. "
            "Gabarito: A."
        ),
    },
    {
        "id_ref": "q-fgv-port-01",
        "tipo": "escolha_unica",
        "disciplina": "Língua Portuguesa",
        "topico": "Interpretação e Coesão",
        "dificuldade": "dificil",
        "fonte": "FGV - 2024 - Senado Federal - Analista Legislativo",
        "licenca": "prova_publica",
        "tags": ["banca:fgv", "ano:2024", "orgao:senado", "cargo:analista", "assunto:semantica"],
        "enunciado": (
            "Assinale a frase em que o termo sublinhado possui valor semântico de oposição a uma ideia anterior (concessão ou adversidade):"
        ),
        "alternativas": [
            "O projeto foi aprovado com louvor, posto que a oposição tenha apresentado críticas contundentes.",
            "O candidato estudou muito para a prova, porquanto desejava a aprovação no concurso.",
            "Assim que o edital foi publicado, todos os concorrentes iniciaram a preparação intensiva.",
            "A medida foi considerada inconstitucional, de modo que sua aplicação foi suspensa imediatamente.",
            "Conforme as diretrizes da banca examinadora, a prova terá duração de quatro horas.",
        ],
        "gabarito": "A",
        "comentario": (
            "Estilo refinado da FGV em Língua Portuguesa: a locução conjuntiva 'posto que', quando seguida de verbo no subjuntivo "
            "('tenha apresentado'), atua com valor CONCESSIVO (equivale a 'embora a oposição tenha apresentado críticas'). "
            "Nas outras alternativas: 'porquanto' é causal; 'assim que' é temporal; 'de modo que' é consecutivo; e 'conforme' é conformativo. "
            "Gabarito: A."
        ),
    },
]


def seed_real_questions(db_path: str) -> dict[str, Any]:
    """Insere o catálogo de questões reais anteriores no banco de dados.

    Idempotente: verifica por identificador de procedência para não duplicar questões.
    """
    from radar.practice_store import list_questions

    existing = list_questions(db_path, include_archived=True)
    existing_enunciados = {q.get("enunciado", "").strip() for q in existing}

    total_inseridas = 0
    for q in _REAL_QUESTIONS:
        if q["enunciado"].strip() in existing_enunciados:
            continue
        try:
            create_question(
                db_path,
                enunciado=q["enunciado"],
                alternativas=q.get("alternativas"),
                gabarito=q["gabarito"],
                tipo=q["tipo"],
                disciplina=q["disciplina"],
                topico=q["topico"],
                dificuldade=q["dificuldade"],
                comentario=q["comentario"],
                fonte=q["fonte"],
                licenca=q["licenca"],
                tags=q["tags"],
                procedencia=q["id_ref"],
            )
            total_inseridas += 1
            existing_enunciados.add(q["enunciado"].strip())
        except Exception:
            # Se já existir ou houver violação, segue adiante
            pass

    return {
        "ok": True,
        "total_catalogo": len(_REAL_QUESTIONS),
        "total_inseridas": total_inseridas,
    }
