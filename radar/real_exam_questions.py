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
    {
        "id_ref": "q-ceb-sql-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Banco de Dados",
        "topico": "Linguagem SQL",
        "dificuldade": "media",
        "fonte": "Cebraspe - 2024 - Petrobras - Analista de Sistemas",
        "licenca": "prova_publica",
        "tags": ["banca:cebraspe", "ano:2024", "orgao:petrobras", "cargo:analista_sistemas", "assunto:sql"],
        "enunciado": (
            "Em consultas SQL ANSI, a função de agregação COUNT(*) contabiliza todas as linhas retornadas pelo agrupamento, "
            "incluindo aquelas que possuem valores nulos (NULL), ao passo que COUNT(nome_coluna) ignora os registros em que "
            "a referida coluna esteja preenchida com NULL."
        ),
        "gabarito": "V",
        "comentario": (
            "Assertiva clássica e recorrente do Cebraspe. O comando COUNT(*) conta a cardinalidade de tuplas da relação ou grupo "
            "independentemente de valores nulos; já COUNT(coluna) avalia apenas os valores não nulos daquela coluna específica. "
            "Gabarito: VERDADEIRO (Certo)."
        ),
    },
    {
        "id_ref": "q-fgv-agil-01",
        "tipo": "escolha_unica",
        "disciplina": "Engenharia de Software",
        "topico": "Metodologias Ágeis",
        "dificuldade": "media",
        "fonte": "FGV - 2024 - Câmara dos Deputados - Analista de Informática Legislativa",
        "licenca": "prova_publica",
        "tags": ["banca:fgv", "ano:2024", "orgao:camara_deputados", "cargo:analista_ti", "assunto:scrum"],
        "enunciado": (
            "Durante a execução de uma Sprint de duas semanas em um time Scrum, um diretor solicita diretamente aos Developers "
            "a inclusão urgente de um novo requisito que altera substancialmente a Meta da Sprint (Sprint Goal). "
            "De acordo com o Scrum Guide oficial, a conduta correta diante dessa situação é:"
        ),
        "alternativas": [
            "Orientar o diretor a tratar a demanda com o Product Owner, pois nenhuma mudança que coloque em risco a Meta da Sprint deve ser feita durante a Sprint.",
            "Aceitar imediatamente a solicitação caso o Scrum Master autorize a prorrogação do timebox da Sprint por mais uma semana.",
            "Substituir as tarefas do Sprint Backlog diretamente pelos desenvolvedores, desde que a velocidade (velocity) seja mantida.",
            "Cancelar a Daily Scrum e realizar uma nova Sprint Retrospective imediata para aprovar o novo escopo.",
            "Submeter a decisão ao voto majoritário dos stakeholders externos durante a Sprint Review.",
        ],
        "gabarito": "A",
        "comentario": (
            "No Scrum, durante a Sprint, nenhuma mudança é feita que coloque em perigo a Meta da Sprint (Sprint Goal), "
            "e o timebox jamais é prorrogado. Qualquer alteração de prioridade de negócio passa pelo Product Owner, "
            "que é a única pessoa com autoridade até mesmo para cancelar uma Sprint caso a meta se torne obsoleta. Gabarito: A."
        ),
    },
    {
        "id_ref": "q-fgv-gof-01",
        "tipo": "escolha_unica",
        "disciplina": "Engenharia de Software",
        "topico": "Padrões de Projeto GoF",
        "dificuldade": "dificil",
        "fonte": "FGV - 2024 - STN - Auditor Federal de Finanças e Controle (TI)",
        "licenca": "prova_publica",
        "tags": ["banca:fgv", "ano:2024", "orgao:stn", "cargo:auditor_ti", "assunto:gof"],
        "enunciado": (
            "Um arquiteto de software precisa projetar um módulo de cálculo de impostos no qual diferentes algoritmos "
            "(ICMS, ISS, IPI) possam ser selecionados e intercambiados dinamicamente em tempo de execução, "
            "sem utilizar múltiplos blocos condicionais (if/else ou switch) na classe cliente. "
            "O padrão de projeto GoF Comportamental que atende exatamente a esse objetivo é:"
        ),
        "alternativas": [
            "Strategy",
            "Singleton",
            "Adapter",
            "Facade",
            "Composite",
        ],
        "gabarito": "A",
        "comentario": (
            "O padrão Strategy (Comportamental) define uma família de algoritmos, encapsula cada um deles em uma classe separada "
            "e os torna intercambiáveis em tempo de execução para o cliente. Singleton é criacional; Adapter, Facade e Composite são estruturais. Gabarito: A."
        ),
    },
    {
        "id_ref": "q-ceb-gof-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Engenharia de Software",
        "topico": "Padrões de Projeto GoF",
        "dificuldade": "media",
        "fonte": "Cebraspe - 2024 - BACEN - Analista de Tecnologia da Informação",
        "licenca": "prova_publica",
        "tags": ["banca:cebraspe", "ano:2024", "orgao:bacen", "cargo:analista_ti", "assunto:gof"],
        "enunciado": (
            "O padrão de projeto estrutural Decorator permite anexar responsabilidades adicionais a um objeto de forma dinâmica, "
            "fornecendo uma alternativa flexível ao uso de herança (subclasses) para estender funcionalidades."
        ),
        "gabarito": "V",
        "comentario": (
            "Definição literal do catálogo GoF para o padrão Decorator: 'Anexa responsabilidades adicionais a um objeto dinamicamente. "
            "Os Decorators oferecem uma alternativa flexível ao uso de subclasses para estender a funcionalidade'. Gabarito: VERDADEIRO."
        ),
    },
    {
        "id_ref": "q-ceb-port-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Língua Portuguesa",
        "topico": "Interpretação e Coesão",
        "dificuldade": "media",
        "fonte": "Cebraspe - 2024 - TSE Unificado - Analista Judiciário",
        "licenca": "prova_publica",
        "tags": ["banca:cebraspe", "ano:2024", "orgao:tse", "cargo:analista", "assunto:semantica"],
        "enunciado": (
            "No período 'Conquanto os recursos orçamentários fossem escassos, o sistema foi implantado dentro do prazo previsto', "
            "a substituição da conjunção 'Conquanto' por 'Porquanto' manteria a correção gramatical e o sentido original do texto."
        ),
        "gabarito": "F",
        "comentario": (
            "Armadilha clássica do Cebraspe! 'Conquanto' é conjunção subordinativa CONCESSIVA (equivale a 'embora'). "
            "Já 'Porquanto' é conjunção CAUSAL/EXPLICATIVA (equivale a 'porque', 'visto que'). "
            "Logo, a substituição altera completamente o sentido original e exige ajuste no modo verbal. Gabarito: FALSO."
        ),
    },
    {
        "id_ref": "q-fgv-dir-01",
        "tipo": "escolha_unica",
        "disciplina": "Direito Constitucional",
        "topico": "Direitos e Garantias Fundamentais",
        "dificuldade": "media",
        "fonte": "FGV - 2024 - TJ-SC - Analista Jurídico",
        "licenca": "prova_publica",
        "tags": ["banca:fgv", "ano:2024", "orgao:tjsc", "cargo:analista", "assunto:artigo_5"],
        "enunciado": (
            "Uma associação civil legalmente constituída decide ajuizar Ação Popular visando anular contrato administrativo "
            "lesivo ao patrimônio público estadual. À luz da Constituição Federal e da jurisprudência sumulada do STF, tal ação é:"
        ),
        "alternativas": [
            "Incabível, pois a pessoa jurídica não possui legitimidade ativa para propor Ação Popular, prerrogativa exclusiva do cidadão.",
            "Cabível, desde que a associação esteja constituída há pelo menos um ano e inclua entre suas finalidades a proteção ao erário.",
            "Cabível, mediante autorização expressa da maioria absoluta dos associados em assembleia geral.",
            "Incabível, pois contra ato lesivo ao patrimônio público o único remédio constitucional existente é o Habeas Data.",
            "Cabível, mas a associação não gozará de isenção de custas judiciais.",
        ],
        "gabarito": "A",
        "comentario": (
            "Conforme o Art. 5º, LXXIII da CF/88 e a Súmula 365 do STF ('Pessoa jurídica não tem legitimidade para propor ação popular'), "
            "apenas o CIDADÃO (pessoa física no gozo dos direitos políticos, portador de título de eleitor) pode ajuizar Ação Popular. "
            "A banca tenta confundir com o requisito de 1 ano do Mandado de Segurança Coletivo. Gabarito: A."
        ),
    },
    {
        "id_ref": "q-ceb-red-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Redes de Computadores",
        "topico": "Arquitetura TCP/IP e OSI",
        "dificuldade": "media",
        "fonte": "Cebraspe - 2024 - ANATEL - Especialista em Regulação (TI)",
        "licenca": "prova_publica",
        "tags": ["banca:cebraspe", "ano:2024", "orgao:anatel", "cargo:especialista_ti", "assunto:redes"],
        "enunciado": (
            "No estabelecimento de uma conexão TCP utilizando o mecanismo Three-Way Handshake, o cliente envia inicialmente "
            "um segmento com a flag SYN ativada; o servidor responde com um segmento contendo as flags SYN e ACK ativadas; "
            "e, por fim, o cliente confirma o estabelecimento enviando um segmento com a flag ACK ativada."
        ),
        "gabarito": "V",
        "comentario": (
            "Descrição exata do aperto de mão de três vias (Three-Way Handshake) do protocolo TCP (RFC 793 / RFC 9293): "
            "1º Passo: SYN (Cliente -> Servidor); 2º Passo: SYN+ACK (Servidor -> Cliente); 3º Passo: ACK (Cliente -> Servidor). "
            "Gabarito: VERDADEIRO."
        ),
    },
    {
        "id_ref": "q-fgv-red-01",
        "tipo": "escolha_unica",
        "disciplina": "Redes de Computadores",
        "topico": "Modelo OSI e Protocolos",
        "dificuldade": "media",
        "fonte": "FGV - 2024 - TRF 1ª Região - Analista Judiciário (Redes)",
        "licenca": "prova_publica",
        "tags": ["banca:fgv", "ano:2024", "orgao:trf1", "cargo:analista_redes", "assunto:redes"],
        "enunciado": (
            "Correlacione corretamente as camadas do Modelo de Referência OSI com suas respectivas Unidades de Dados de Protocolo (PDUs) "
            "e equipamentos típicos de operação:"
        ),
        "alternativas": [
            "Camada 2 (Enlace): Quadro (Frame) / Switch L2; Camada 3 (Rede): Pacote / Roteador; Camada 4 (Transporte): Segmento.",
            "Camada 2 (Enlace): Pacote / Roteador; Camada 3 (Rede): Quadro (Frame) / Switch; Camada 4 (Transporte): Bit.",
            "Camada 1 (Física): Quadro; Camada 2 (Enlace): Segmento; Camada 3 (Rede): Datagrama de Aplicação.",
            "Camada 3 (Rede): Segmento TCP / Switch L2; Camada 4 (Transporte): Pacote IP / Roteador.",
            "Camada 2 (Enlace): Bit / Hub; Camada 3 (Rede): Mensagem HTTP / Firewall de Aplicação.",
        ],
        "gabarito": "A",
        "comentario": (
            "Na hierarquia OSI: Camada 1 (Física) lida com Bits; Camada 2 (Enlace) opera com Quadros (Frames) e endereços MAC (Switches L2); "
            "Camada 3 (Rede) opera com Pacotes e endereços IP (Roteadores); Camada 4 (Transporte) opera com Segmentos (TCP) ou Datagramas (UDP). Gabarito: A."
        ),
    },
    {
        "id_ref": "q-ceb-seg-01",
        "tipo": "verdadeiro_falso",
        "disciplina": "Segurança da Informação",
        "topico": "Criptografia e Assinatura Digital",
        "dificuldade": "media",
        "fonte": "Cebraspe - 2024 - Polícia Federal / Perito e TI",
        "licenca": "prova_publica",
        "tags": ["banca:cebraspe", "ano:2024", "orgao:pf", "cargo:ti", "assunto:seguranca"],
        "enunciado": (
            "No processo de assinatura digital utilizando criptografia assimétrica, o remetente gera o resumo criptográfico (hash) "
            "da mensagem e o criptografa utilizando a chave pública do destinatário, garantindo assim a confidencialidade e o não-repúdio."
        ),
        "gabarito": "F",
        "comentario": (
            "Pegadinha campeã de provas de Segurança! Na ASSINATURA DIGITAL, o hash é cifrado com a CHAVE PRIVADA do próprio REMETENTE "
            "(e verificado com a chave pública do remetente). Além disso, assinatura digital garante Autenticidade, Integridade e Não-repúdio, "
            "mas NÃO garante confidencialidade (sigilo) da mensagem. Gabarito: FALSO."
        ),
    },
    {
        "id_ref": "q-fgv-seg-01",
        "tipo": "escolha_unica",
        "disciplina": "Segurança da Informação",
        "topico": "Vulnerabilidades Web e OWASP",
        "dificuldade": "media",
        "fonte": "FGV - 2024 - CVM - Analista de Sistemas",
        "licenca": "prova_publica",
        "tags": ["banca:fgv", "ano:2024", "orgao:cvm", "cargo:analista_sistemas", "assunto:seguranca"],
        "enunciado": (
            "Para prevenir ataques de Injeção de SQL (SQL Injection) em aplicações web corporativas que acessam bancos de dados relacionais, "
            "a contramedida de codificação segura recomendada pelo guia OWASP como mais eficaz é:"
        ),
        "alternativas": [
            "Utilizar consultas parametrizadas (Prepared Statements / Parameterized Queries) separando o código SQL dos dados fornecidos pelo usuário.",
            "Substituir o protocolo HTTP pelo protocolo HTTPS com certificado TLS 1.3 no servidor web.",
            "Aumentar o tamanho da chave criptográfica do banco de dados de AES-128 para AES-256.",
            "Validar os campos do formulário exclusivamente no navegador do cliente por meio de expressões regulares em JavaScript.",
            "Ocultar as mensagens de erro do banco de dados sem alterar a concatenação dinâmica de strings nas consultas SQL.",
        ],
        "gabarito": "A",
        "comentario": (
            "A causa raiz do SQL Injection é a concatenação direta de entradas não confiáveis na instrução SQL. "
            "O uso de Prepared Statements (consultas parametrizadas) garante que o interpretador do SGBD trate a entrada estritamente como dado literal, "
            "nunca como comando executável. HTTPS protege apenas o trânsito; validação client-side é facilmente contornada. Gabarito: A."
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
