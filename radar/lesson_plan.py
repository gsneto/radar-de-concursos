"""Módulo de Planos de Aula estruturados e Radiografia de Bancas Examinadoras.

Transforma o edital bruto em um roteiro pedagógico sequencial com teoria resumida,
pontos críticos e análise comparativa de como cada banca examinadora (FGV, Cebraspe,
Quadrix, IBFC) cobra cada disciplina e assunto.
"""

from __future__ import annotations

from typing import Any

# ==============================================================================
# 1. Radiografia e Perfis Comparativos de Bancas
# ==============================================================================

_BANCAS: dict[str, dict[str, Any]] = {
    "fgv": {
        "id": "fgv",
        "nome": "Fundação Getulio Vargas (FGV)",
        "estilo_predominante": "Múltipla Escolha (5 alternativas A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Enunciados longos estruturados em estudos de caso e cenários práticos reais.",
            "Alta exigência de interpretação contextual e raciocínio analítico, não mera decoreba.",
            "Em Língua Portuguesa, é considerada a mais imprevisível: forte foco em semântica, ambiguidade, polissemia e reescrita.",
            "Em Tecnologia da Informação, prioriza arquitetura de microsserviços, modelagem relacional/NoSQL, SQL analítico e padrões de projeto GoF.",
        ],
        "dicas_ti": [
            "Atenção para cenários de concorrência, níveis de isolamento e transações ACID em banco de dados.",
            "Em engenharia de software, avalie a intenção dos padrões de projeto (GoF) em vez de apenas memorizar os nomes das classes.",
            "Questões de código exigem rastreamento de complexidade de tempo/espaço (Big-O) e princípios SOLID.",
        ],
        "dicas_gerais": [
            "Administre o tempo de prova: os enunciados longos e textos densos cansam se você demorar muito no início.",
            "Em caso de dúvida entre duas alternativas, procure a nuance de contexto ou a palavra que limita sutilmente o escopo.",
        ],
        "palavras_chave_alerta": [
            "Considere o seguinte cenário hipotético",
            "Assinale a opção que apresenta a justificativa correta",
            "Infere-se necessariamente do texto",
            "À luz das boas práticas de engenharia",
        ],
    },
    "cebraspe": {
        "id": "cebraspe",
        "nome": "Cebraspe (Centro Brasileiro de Pesquisa em Avaliação e Seleção)",
        "estilo_predominante": "Certo/Errado (Itens individuais assertivos) ou Múltipla Escolha",
        "regras_pontuacao": "Regra Cespe tradicional: 1 acerto = +1 ponto; 1 erro = -1 ponto (penalidade: uma errada anula uma certa); em branco = 0",
        "caracteristicas": [
            "Formato de itens assertivos que demandam julgamento objetivo: Certo ou Errado.",
            "Rigor conceitual com cobrança de doutrina consagrada e jurisprudência pacificada (STF/STJ) em Direito.",
            "Em Língua Portuguesa, cobra concordância complexa, regência, pontuação expressiva e coesão textual referencial.",
            "Em Tecnologia da Informação, tem tradição em Segurança da Informação (ISO 27001/27002), Redes (roteamento BGP/OSPF, TCP/UDP), Governança (ITIL 4, COBIT) e Nuvem/DevOps.",
        ],
        "dicas_ti": [
            "Cuidado máximo com termos absolutistas ('sempre', 'nunca', 'exclusivamente', 'somente', 'em qualquer hipótese') — na esmagadora maioria dos casos tornam o item Errado.",
            "Atenção à troca cirúrgica de conceitos irmãos (ex: criptografia simétrica x assimétrica; integridade x confidencialidade).",
            "Gestão estratégica de risco: se a dúvida persistir após análise detalhada, deixar em branco é uma decisão técnica de sobrevivência na prova.",
        ],
        "dicas_gerais": [
            "Leia cada item isoladamente: um item não costuma anular a lógica do anterior.",
            "A primeira frase do item muitas vezes traz uma verdade para induzir ao erro na conclusão.",
        ],
        "palavras_chave_alerta": [
            "exclusivamente",
            "sempre",
            "em qualquer hipótese",
            "dispensa a necessidade",
            "independe de",
            "vedado",
        ],
    },
    "quadrix": {
        "id": "quadrix",
        "nome": "Instituto Quadrix",
        "estilo_predominante": "Certo ou Errado (padrão conselhos regionais) e Múltipla Escolha (A-E)",
        "regras_pontuacao": "Geralmente 1 ponto por acerto; alguns editais adotam fator de penalidade reduzido (0.5 a 1.0 por erro)",
        "caracteristicas": [
            "Inspira-se fortemente na estrutura e estilo do Cebraspe para os itens C/E.",
            "Forte tendência à literalidade de manuais oficiais, normas técnicas e legislação dos conselhos profissionais (CRM, CRMV, CRP, CRA).",
            "Em Língua Portuguesa, segue a gramática normativa tradicional (crase, pontuação, acentuação, classes de palavras).",
            "Em Tecnologia da Informação, prioriza comandos de sistemas operacionais (Linux/Windows), redes locais e banco de dados relacional (SQL).",
        ],
        "dicas_ti": [
            "Memorize a sintaxe e os parâmetros mais comuns de comandos de shell Linux (grep, chmod, chown, ps, netstat, find).",
            "Em SQL, questões de múltipla escolha ou C/E testam cláusulas GROUP BY, HAVING, ORDER BY e diferenças entre LEFT JOIN e INNER JOIN.",
            "A banca costuma alterar uma única palavra na definição do conceito técnico para invalidar o item.",
        ],
        "dicas_gerais": [
            "Atenção redobrada para a legislação institucional do conselho ou órgão contratante.",
            "Banca previsível para quem domina a teoria fundamental e a lei seca.",
        ],
        "palavras_chave_alerta": [
            "segundo o regimento",
            "ao passo que",
            "caracteriza-se prioritariamente por",
            "compete privativamente ao",
        ],
    },
    "ibfc": {
        "id": "ibfc",
        "nome": "Instituto Brasileiro de Formação e Capacitação (IBFC)",
        "estilo_predominante": "Múltipla Escolha (4 alternativas A-D ou 5 A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Enunciados diretos, objetivos e sem rodeios conceituais longos.",
            "Cobrança focada na literalidade da norma, definições de livros clássicos e listas enumeradas.",
            "Em Português, questões diretas de acentuação gráfica, concordância verbal/nominal e identificação de figuras de linguagem.",
            "Em Tecnologia da Informação, costuma cobrar modelos de ciclo de vida (Cascata, Espiral, Ágil), camadas do modelo OSI e portas padrão de protocolos.",
        ],
        "dicas_ti": [
            "Memorize tabelas clássicas: portas padrão (HTTP 80, HTTPS 443, SSH 22, DNS 53, FTP 20/21, SMTP 25/587).",
            "Em Engenharia de Software, decore as fases do RUP e as cerimônias/papéis do Scrum.",
            "Questões de SQL costumam ser breves, pedindo para identificar o comando que realiza determinada operação simples.",
        ],
        "dicas_gerais": [
            "Ideal para resolução rápida de prova. Não invente dificuldades onde o enunciado foi simples.",
            "Atenção ao comando do enunciado ('Assinale a INCORRETA' ou 'EXCETO').",
        ],
        "palavras_chave_alerta": [
            "Assinale a alternativa correta",
            "Assinale a alternativa que apresenta a exceção",
            "Respectivamente",
            "São exemplos de, EXCETO",
        ],
    },
    "fcc": {
        "id": "fcc",
        "nome": "Fundação Carlos Chagas (FCC)",
        "estilo_predominante": "Múltipla Escolha (5 alternativas A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro; cálculo por desvio-padrão / nota padronizada em alguns certames de ponta",
        "caracteristicas": [
            "Banca histórica em Tribunais (TRTs, TRFs, TJs) e carreiras fiscais/de controle.",
            "Consistência e previsibilidade: enunciados claros, sem pegadinhas capciosas ou ambíguas.",
            "Em Língua Portuguesa, rigor gramatical com forte ênfase em equivalência e reescrita de frases, crase e flexão verbal.",
            "Em Tecnologia da Informação, cobra frameworks consolidados (ITIL, COBIT, PMBOK), arquitetura Java/Spring, modelagem relacional avançada e segurança de redes.",
        ],
        "dicas_ti": [
            "Em Java e Programação Orientada a Objetos, estude coleções (List, Set, Map), tratamento de exceções e modificadores de acesso.",
            "Em Banco de Dados, domine funções de agregação, subconsultas correlacionadas e gatilhos (triggers).",
            "Mantenha domínio seguro das fases e processos das versões cobradas no edital (ex: ITIL v3 ou ITIL 4; PMBOK 6ª ou 7ª edição).",
        ],
        "dicas_gerais": [
            "A FCC costuma premiar candidatos com alto percentual de acertos em conhecimentos básicos.",
            "Em Tribunais, a nota de corte costuma ser alta: precisão rápida é fundamental.",
        ],
        "palavras_chave_alerta": [
            "O verbo flexionado nos mesmos tempo e modo",
            "Está clara e correta a redação do seguinte período",
            "Atende aos requisitos de integridade referencial",
            "Em conformidade com as diretrizes do guia",
        ],
    },
    "cesgranrio": {
        "id": "cesgranrio",
        "nome": "Fundação Cesgranrio",
        "estilo_predominante": "Múltipla Escolha (5 alternativas A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Banca oficial das grandes estatais brasileiras (Petrobras, Transpetro, Banco do Brasil, Caixa, BNDES) e do Concurso Público Nacional Unificado (CPNU).",
            "Enunciados diretos, objetivos e bem fundamentados na literatura técnica acadêmica.",
            "Em Língua Portuguesa, interpretação de textos jornalísticos e contemporâneos, aliada à morfossintaxe prática.",
            "Em Tecnologia da Informação, cobra Ciência de Dados (Python, Pandas, Scikit-learn), Engenharia de Software ágil (DevOps, CI/CD, Git) e Banco de Dados (SQL e NoSQL).",
        ],
        "dicas_ti": [
            "Para Ciência de Dados, estude métricas de avaliação de modelos (Precision, Recall, F1-Score, Curva ROC/AUC, matriz de confusão).",
            "Em Engenharia de Dados e Nuvem, foco em ecossistemas de mensageria (Kafka, RabbitMQ) e contêineres Docker/Kubernetes.",
            "Em lógica e algoritmos, atenção para manipulação de arrays/estruturas em Python ou Java com complexidade O(n).",
        ],
        "dicas_gerais": [
            "Provas bem dosadas no tempo. Fazer as questões fáceis primeiro garante a base de pontuação.",
            "Excelente equilíbrio entre teoria e resolução de problemas práticos.",
        ],
        "palavras_chave_alerta": [
            "De acordo com a norma-padrão",
            "O valor da métrica F1-score",
            "O padrão arquitetural que atende ao requisito",
            "Com base nas informações apresentadas",
        ],
    },
    "esaf": {
        "id": "esaf",
        "nome": "ESAF / ENAP (Escola Nacional de Administração Pública)",
        "estilo_predominante": "Múltipla Escolha (5 alternativas A-E) com complexidade interdisciplinar",
        "regras_pontuacao": "1 ponto por acerto; tradicionalmente exigia mínimos por disciplina (mínimo de 40% a 50% por matéria)",
        "caracteristicas": [
            "Banca formadora dos grandes quadros da Administração Pública Federal (Receita Federal, Tesouro Nacional, EPGG).",
            "Enunciados densos, técnicos e que exigem capacidade analítica de políticas públicas e governança estatal.",
            "Em TI, pioneira na cobrança de Governança de TI no Setor Público (TCU, IN01/IN04 da SLTI, Guia do SISP) e auditoria de sistemas.",
            "Em Raciocínio Lógico e Matemática, questões com alto grau de elaboração formal.",
        ],
        "dicas_ti": [
            "Forte foco nos acórdãos do Tribunal de Contas da União (TCU) sobre contratações públicas de soluções de TI.",
            "Em auditoria de sistemas, domine trilhas de auditoria, segregação de funções e gestão de riscos em TI.",
            "Fique atento à exigência de pontuação mínima em cada grupo temático.",
        ],
        "dicas_gerais": [
            "Nunca zere nem negligencie nenhuma disciplina básica para focar só nas específicas.",
            "A interpretação do problema exige visão sistêmica do Estado e da legalidade administrativa.",
        ],
        "palavras_chave_alerta": [
            "Sob a ótica dos acórdãos do TCU",
            "Considerando a Instrução Normativa",
            "É correto afirmar que",
            "Constitui requisito de governança pública",
        ],
    },
    "vunesp": {
        "id": "vunesp",
        "nome": "Fundação VUNESP",
        "estilo_predominante": "Múltipla Escolha (5 alternativas A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Banca hegemônica no Estado de São Paulo (Tribunal de Justiça de SP, Polícia Civil de SP, Prefeituras Paulistas, Universidades Estaduais).",
            "Enunciados claros e objetivos, com grande apego à literalidade dos textos normativos e dos conceitos teóricos.",
            "Em Língua Portuguesa, textos de crônicas e jornais com questões gramaticais muito padronizadas (regência, crase, concordância).",
            "Em Tecnologia da Informação, prioriza infraestrutura de redes, fundamentos de hardware, comandos de sistemas operacionais e desenvolvimento web básico/médio.",
        ],
        "dicas_ti": [
            "Memorize atalhos, comandos e configurações práticas de ambientes Windows e Linux.",
            "Em Redes de Computadores, decore topologias físicas/lógicas, máscaras de sub-rede e equipamentos de rede (switches, roteadores, firewalls).",
            "Em Bancos de Dados, questões diretas cobrando a sintaxe exata de comandos DDL (CREATE, ALTER, DROP) e DML (INSERT, UPDATE, DELETE).",
        ],
        "dicas_gerais": [
            "A 'banca da lei seca': a alternativa correta é quase sempre a transcrição exata da lei ou do manual oficial.",
            "Atenção para não perder pontos em detalhes de texto de lei.",
        ],
        "palavras_chave_alerta": [
            "Em conformidade com a Lei",
            "Assinale a alternativa que preenche correta e respectivamente",
            "O comando utilizado para",
            "Nos termos do artigo",
        ],
    },
    "fundatec": {
        "id": "fundatec",
        "nome": "FUNDATEC (Fundação Universidade Empresa de Tecnologia e Ciências)",
        "estilo_predominante": "Múltipla Escolha (5 alternativas A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Grande expressão no Sul do Brasil (Rio Grande do Sul e Santa Catarina), atuando em prefeituras, autarquias e conselhos.",
            "Cobrança técnica pragmática, enunciados com perguntas pontuais sobre atribuições de cargos e procedimentos operacionais.",
            "Em Língua Portuguesa, questões focadas em morfologia, funções sintáticas e acentuação gráfica do Novo Acordo Ortográfico.",
            "Em Tecnologia da Informação, foco em suporte técnico, redes de computadores, noções de segurança e manutenção de sistemas corporativos.",
        ],
        "dicas_ti": [
            "Domine cabeamento estruturado (Normas TIA/EIA 568A e 568B, cabos UTP cat 5e, 6 e fibra óptica).",
            "Em segurança da informação, estude tipos de malwares (trojan, ransomware, phishing, spyware) e backups (completo, incremental, diferencial).",
            "Em banco de dados, foco nas operações fundamentais de consultas SQL com joins.",
        ],
        "dicas_gerais": [
            "Provas com tempo confortável para resolução.",
            "Excelente para quem treina com baterias de provas anteriores da região Sul.",
        ],
        "palavras_chave_alerta": [
            "Analise as assertivas a seguir",
            "Está correto o que se afirma em",
            "É correto afirmar que",
            "A respeito do conceito de",
        ],
    },
    "comissao_propria": {
        "id": "comissao_propria",
        "nome": "Comissão Própria (Certames Conduzidos pelo Próprio Órgão)",
        "estilo_predominante": "Múltipla Escolha ou Prova Discursiva/Prática",
        "regras_pontuacao": "Definida no edital específico de cada órgão",
        "caracteristicas": [
            "Comum em Universidades Públicas (UFRJ, USP, UNICAMP), Tribunais locais e Câmaras Legislativas municipais.",
            "Questões elaboradas pelo corpo técnico ou docente do próprio órgão, gerando alta especificidade para a rotina do cargo.",
            "Forte exigência dos regimentos internos, organogramas, resoluções e atribuições práticas diárias da instituição.",
            "Em TI, foca nos sistemas legados e na stack tecnológica real utilizada no dia a dia da repartição pública.",
        ],
        "dicas_ti": [
            "Investigue o portal de transparência e o plano diretor de TI (PDTI) do órgão para descobrir a stack real de tecnologias em uso.",
            "Estude a legislação específica de criação e regimento da instituição pública contratante.",
            "Prepare-se para questões práticas de estudo de caso ou resolução discursiva.",
        ],
        "dicas_gerais": [
            "Não limite o estudo à teoria abstrata: leia o regulamento interno e o estatuto dos servidores locais.",
            "O estilo da prova reflete a cultura acadêmica ou funcional do comitê examinador interno.",
        ],
        "palavras_chave_alerta": [
            "De acordo com o Regimento Interno",
            "São competências da Diretoria de",
            "Considerando as normas internas da Instituição",
            "Na rotina administrativa do Órgão",
        ],
    },
    "ibam": {
        "id": "ibam",
        "nome": "IBAM (Instituto Brasileiro de Administração Municipal)",
        "estilo_predominante": "Múltipla Escolha (4 alternativas A-D)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Forte presença histórica na gestão municipal de todo o Brasil (Prefeituras e Câmaras de Vereadores).",
            "Questões compactas de 4 alternativas, com foco direto na Lei Orgânica Municipal e Estatuto dos Servidores Municipais.",
            "Em Língua Portuguesa, estilo clássico com interpretação de texto e gramática direta.",
            "Em Tecnologia da Informação, cobra rotinas de suporte ao usuário, noções de sistemas operacionais, redes de computadores e aplicativos de escritório.",
        ],
        "dicas_ti": [
            "Foco nas funções do pacote Office e LibreOffice (atalhos, fórmulas como PROCV, SOMASE, SE).",
            "Conceitos de periféricos de entrada/saída, arquitetura de microcomputadores e protocolos básicos de internet (TCP/IP, DNS, DHCP).",
            "Noções de Lei de Acesso à Informação (LAI) e Lei Geral de Proteção de Dados (LGPD) no contexto municipal.",
        ],
        "dicas_gerais": [
            "Como são apenas 4 alternativas, a eliminação de alternativas absurdas acelera muito a resolução da prova.",
            "Gabarite as questões de legislação municipal, pois costumam definir a nota de corte.",
        ],
        "palavras_chave_alerta": [
            "Assinale a alternativa que NÃO",
            "Segundo a Lei Orgânica Municipal",
            "É considerado um dispositivo de",
            "Dentre as opções abaixo, a única correta é",
        ],
    },
    "consesp": {
        "id": "consesp",
        "nome": "CONSESP Concursos",
        "estilo_predominante": "Múltipla Escolha (4 alternativas A-D)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Banca com forte atuação no interior de São Paulo, Paraná e Minas Gerais em órgãos municipais.",
            "Enunciados curtos e cobrança baseada estritamente na letra da lei e definições literais de dicionários e apostilas.",
            "Em Língua Portuguesa, muita acentuação, ortografia, pontuação e identificação de classes gramaticais.",
            "Em TI, questões de hardware, configuração de redes locais, manutenção preventiva de microcomputadores e pacote office.",
        ],
        "dicas_ti": [
            "Atenção para especificações de memória (RAM, ROM, Cache, SSD vs HD) e tipos de barramento.",
            "Estude formatação de células e atalhos de teclado no Windows e no Pacote Office.",
            "Comandos básicos de prompt de comando (ipconfig, ping, tracert).",
        ],
        "dicas_gerais": [
            "Prova rápida e dinâmica. Evite gastar tempo excessivo em uma única questão.",
            "Cuidado com pegadinhas de digitação ou inversão de palavras na letra da lei.",
        ],
        "palavras_chave_alerta": [
            "É CORRETO afirmar que",
            "Assinale a opção INCORRETA",
            "Corresponde a um componente de hardware",
            "A principal finalidade do comando",
        ],
    },
    "idib": {
        "id": "idib",
        "nome": "IDIB (Instituto de Desenvolvimento Institucional Brasileiro)",
        "estilo_predominante": "Múltipla Escolha (4 alternativas A-D ou 5 A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Banca em grande expansão nacional em conselhos profissionais, prefeituras médias e órgãos estaduais no Nordeste e Sudeste.",
            "Estrutura de prova que mescla enunciados de tamanho intermediário com questões práticas de caso de aplicação.",
            "Em Língua Portuguesa, gosta de cobrar funções sintáticas do 'que' e do 'se', figuras de linguagem e tipologia textual.",
            "Em Tecnologia da Informação, cobra desenvolvimento de sistemas, engenharia de software, modelagem de banco de dados e noções de segurança da informação.",
        ],
        "dicas_ti": [
            "Estude diagramas da UML 2.5 (Casos de Uso, Classes, Sequência, Atividades).",
            "Em banco de dados relacional, preste atenção em integridade de dados e comandos SQL DDL/DML.",
            "Conceitos de nuvem (IaaS, PaaS, SaaS) e princípios de segurança (CIA: Confidencialidade, Integridade, Disponibilidade).",
        ],
        "dicas_gerais": [
            "Resolva o máximo de provas recentes (2024–2026) da banca para pegar o padrão recorrente de questões.",
            "Fique atento à distribuição de peso das matérias no edital específico.",
        ],
        "palavras_chave_alerta": [
            "A respeito dos conceitos de",
            "Assinale a alternativa que apresenta a sequência correta",
            "Considerando o trecho acima, infere-se",
            "O diagrama da UML que representa",
        ],
    },
    "fepese": {
        "id": "fepese",
        "nome": "FEPESE (Fundação de Estudos e Pesquisas Socioeconômicos)",
        "estilo_predominante": "Múltipla Escolha (5 alternativas A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Ligada historicamente à Universidade Federal de Santa Catarina (UFSC), com padrão acadêmico rigoroso.",
            "Banca responsável por certames de grande relevância em SC (Receita Estadual/SEF-SC, Polícia Civil-SC, Prefeituras de grande porte).",
            "Enunciados bem redigidos, com alto rigor teórico e baixa taxa de recursos deferidos.",
            "Em Tecnologia da Informação, aprofundamento em Estrutura de Dados, Algoritmos, Redes de Computadores e Engenharia de Software.",
        ],
        "dicas_ti": [
            "Em algoritmos e estrutura de dados, domine listas encadeadas, pilhas, filas, árvores binárias de busca (BST) e grafos.",
            "Em banco de dados, estude planos de execução, otimização de consultas e álgebra relacional formal.",
            "Em redes, aprofunde-se no protocolo TCP (janela deslizante, handshake em 3 vias, controle de congestionamento).",
        ],
        "dicas_gerais": [
            "Estudo aprofundado em bibliografia universitária clássica (Tanenbaum para Redes; Silberschatz para Banco de Dados; Pressman/Sommerville para Software).",
            "Banca técnica e séria: recompensa quem tem base acadêmica sólida.",
        ],
        "palavras_chave_alerta": [
            "Constata-se que",
            "Identifique a afirmativa correta",
            "Assinale a alternativa que expressa o conceito",
            "O custo computacional do algoritmo no pior caso",
        ],
    },
    "legalle": {
        "id": "legalle",
        "nome": "Legalle Concursos",
        "estilo_predominante": "Múltipla Escolha (5 alternativas A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Banca com expressiva atuação em municípios e órgãos regionais do Rio Grande do Sul e Santa Catarina.",
            "Questões objetivas com foco em atribuições do cargo e legislação municipal aplicável.",
            "Em Língua Portuguesa, questões práticas de concordância, regência e vocabulário contextual.",
            "Em Tecnologia da Informação, questões voltadas para montagem e manutenção, sistemas operacionais, suporte técnico e rotinas de backup.",
        ],
        "dicas_ti": [
            "Estude padrões de portas USB, conexões de vídeo (HDMI, DisplayPort, VGA) e tipos de conectores de rede (RJ-45, fibra óptica).",
            "Noções de Active Directory, permissões NTFS e compartilhamento de arquivos em redes Windows.",
            "Políticas de senhas e procedimentos de segurança contra engenharia social.",
        ],
        "dicas_gerais": [
            "Provas bem estruturadas e com linguagem acessível ao candidato.",
            "Praticar com as provas mais recentes da banca garante ótimo índice de acerto.",
        ],
        "palavras_chave_alerta": [
            "Assinale a alternativa que traz uma afirmação correta",
            "Em relação ao sistema operacional",
            "Considerando as afirmações acima, é correto dizer que",
            "Diz respeito ao conceito de",
        ],
    },
    "consulpam": {
        "id": "consulpam",
        "nome": "Instituto Consulpam",
        "estilo_predominante": "Múltipla Escolha (4 alternativas A-D ou 5 A-E)",
        "regras_pontuacao": "1 ponto por acerto, sem penalidade por erro",
        "caracteristicas": [
            "Banca tradicional em prefeituras e câmaras no Ceará, Nordeste, Minas Gerais e São Paulo.",
            "Enunciados diretos com perguntas literais e foco prático na rotina do servidor público municipal.",
            "Em Língua Portuguesa, crase, concordância, encontros vocálicos e classes de palavras.",
            "Em Tecnologia da Informação, conceitos de microinformática, noções de redes locais, segurança básica e banco de dados relacional.",
        ],
        "dicas_ti": [
            "Conceitos elementares de internet, intranet, extranet e protocolos da suíte TCP/IP.",
            "Diferença entre memórias voláteis e não voláteis (RAM vs ROM/Flash/Disco).",
            "Segurança da informação: vírus, firewall, antivírus e certificado digital.",
        ],
        "dicas_gerais": [
            "Muito objetiva: leia o enunciado com atenção e responda diretamente sem hesitar.",
            "Excelente para consolidar a base teórica e pontuar bem nas matérias gerais.",
        ],
        "palavras_chave_alerta": [
            "Assinale a alternativa que contém apenas",
            "É um exemplo de software aplicativo",
            "A definição correta para",
            "Quanto à segurança da informação, é correto afirmar",
        ],
    },
}


def get_banca_profiles() -> dict[str, dict[str, Any]]:
    """Retorna os perfis analíticos comparativos de estilo de exame de cada banca."""
    return _BANCAS


# ==============================================================================
# 2. Catálogo de Planos de Aula Estruturados
# ==============================================================================

_LESSONS: list[dict[str, Any]] = [
    {
        "id": "bd-01",
        "disciplina": "Banco de Dados",
        "titulo": "Aula 01: Modelagem Conceitual, Relacional e Formas Normais (1FN, 2FN, 3FN e BCNF)",
        "objetivos": [
            "Compreender a transição do Modelo Entidade-Relacionamento (MER) para o Modelo Relacional.",
            "Identificar chaves primárias, estrangeiras e candidatas.",
            "Dominar as regras de normalização para eliminar redundâncias e anomalias de atualização.",
        ],
        "teoria_resumida": """
O processo de projeto de banco de dados inicia na modelagem conceitual (MER - Entidades, Atributos e Relacionamentos com cardinalidades 1:1, 1:N, N:M) e avança para a modelagem lógica relacional (Tabelas, Tuplas, Atributos e Chaves).

As Formas Normais (FN) visam evitar anomalias de inserção, exclusão e modificação:
- **1FN (Primeira Forma Normal):** Todos os atributos devem ser atômicos (indivisíveis) e não pode haver atributos multivalorados ou grupos repetitivos.
- **2FN (Segunda Forma Normal):** Deve estar na 1FN E todos os atributos não-chave devem depender totalmente da chave primária (elimina dependência funcional parcial, relevante quando há chave primária composta).
- **3FN (Terceira Forma Normal):** Deve estar na 2FN E não pode haver dependência transitiva entre atributos não-chave (atributo não-chave não pode depender de outro atributo não-chave).
- **BCNF (Boyce-Codd):** Caso especial mais rigoroso da 3FN onde todo determinante de dependência funcional deve ser uma chave candidata.
""",
        "radiografia_bancas": {
            "fgv": "A FGV apresenta tabelas com dados de exemplo e pede para você identificar qual forma normal foi violada e como ficaria a decomposição correta sem perda de informação.",
            "cebraspe": "O Cebraspe adora assertivas conceituais afirmando, por exemplo, que 'uma tabela com chave simples (apenas um atributo) que já se encontra na 1FN está automaticamente na 2FN' (o que é CORRETO, pois não pode haver dependência parcial).",
            "quadrix": "A Quadrix foca em enunciados diretos testando a definição de dependência funcional transitiva (3FN) ou atomicidade (1FN).",
            "ibfc": "O IBFC costuma listar definições nas colunas e pedir a correlação numérica entre 1FN, 2FN e 3FN.",
        },
        "pontos_criticos": [
            "Se a chave primária for simples (apenas uma coluna), ela nunca terá dependência funcional parcial. Logo, se estiver na 1FN, já estará na 2FN!",
            "Não confunda chave primária (PK) com chave estrangeira (FK): a chave estrangeira pode aceitar valores nulos (a menos que haja restrição NOT NULL).",
            "Normalização reduz redundância, mas excesso de joins em consultas pode degradar performance, gerando a necessidade de desnormalização controlada em data warehouses.",
        ],
        "questoes_ids": ["q-fgv-bd-01", "q-ceb-bd-01", "q-qdx-bd-01"],
    },
    {
        "id": "bd-02",
        "disciplina": "Banco de Dados",
        "titulo": "Aula 02: Linguagem SQL Avançada (DML, DDL, DCL, Subconsultas, Agrupamentos e Joins)",
        "objetivos": [
            "Dominar as divisões do SQL: DDL (CREATE, ALTER, DROP), DML (SELECT, INSERT, UPDATE, DELETE), DCL (GRANT, REVOKE) e TCL (COMMIT, ROLLBACK).",
            "Diferenciar perfeitamente INNER JOIN, LEFT JOIN, RIGHT JOIN e FULL OUTER JOIN.",
            "Entender a ordem lógica de execução: FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY.",
        ],
        "teoria_resumida": """
A linguagem SQL (Structured Query Language) opera sobre conjuntos relacionais:

- **Junções (Joins):**
  - `INNER JOIN`: Retorna apenas os registros onde há correspondência em ambas as tabelas.
  - `LEFT OUTER JOIN`: Retorna todos os registros da tabela à esquerda e os correspondentes da direita (ou NULL onde não houver).
  - `RIGHT OUTER JOIN`: Inverso do LEFT JOIN.
  - `FULL JOIN`: Retorna todos os registros de ambos os lados, preenchendo com NULL onde faltar correspondência.

- **Filtros e Agrupamentos:**
  - `WHERE`: Filtra linhas **antes** de qualquer agrupamento. Não pode conter funções de agregação (`COUNT`, `SUM`, `AVG`, etc.).
  - `HAVING`: Filtra grupos **após** a aplicação do `GROUP BY` e pode utilizar funções de agregação.
""",
        "radiografia_bancas": {
            "fgv": "A FGV coloca consultas com subqueries complexas ou Window Functions (`ROW_NUMBER() OVER (...)`) e pergunta exatamente quantas linhas e quais valores a query irá retornar.",
            "cebraspe": "O Cebraspe coloca itens assertivos como 'A cláusula HAVING só pode ser empregada caso haja a cláusula GROUP BY no comando SQL' (geralmente verdadeiro na prática padrão SQL ANSI).",
            "quadrix": "A Quadrix foca na distinção categórica entre comandos DDL (como TRUNCATE e ALTER) e DML (como DELETE e UPDATE).",
            "ibfc": "O IBFC foca em queries clássicas de junção de duas tabelas (Aluno e Curso) com cláusula WHERE simples.",
        },
        "pontos_criticos": [
            "Diferença entre `DELETE` (DML, gera log, suporta WHERE, ativa triggers) e `TRUNCATE` (DDL, mais rápido, não aceita WHERE, reseta auto-incremento na maioria dos SGBDs).",
            "O `COUNT(*)` conta linhas nulas, enquanto `COUNT(coluna)` ignora valores `NULL`.",
            "Em operações com `NULL`, comparações como `= NULL` retornam nulo/falso: deve-se usar `IS NULL` ou `IS NOT NULL`.",
        ],
        "questoes_ids": ["q-fgv-sql-01", "q-ceb-sql-01", "q-ibfc-sql-01"],
    },
    {
        "id": "es-01",
        "disciplina": "Engenharia de Software",
        "titulo": "Aula 01: Metodologias Ágeis (Scrum, Kanban, XP) e Práticas de DevOps",
        "objetivos": [
            "Compreender os valores e 12 princípios do Manifesto Ágil de 2001.",
            "Dominar os papéis (Product Owner, Scrum Master, Developers), cerimônias e artefatos do Scrum Guide.",
            "Compreender fluxo puxado, limitação de WIP no Kanban e pipeline de Integração/Entrega Contínua (CI/CD).",
        ],
        "teoria_resumida": """
O Manifesto Ágil prioriza: indivíduos e interações sobre processos e ferramentas; software em funcionamento sobre documentação abrangente; colaboração com o cliente sobre negociação de contratos; e responder a mudanças sobre seguir um plano.

- **Framework Scrum:**
  - **Papéis:** Product Owner (maximiza o valor do produto e gerencia o Product Backlog), Scrum Master (líder servidor e facilitador de processos), Desenvolvedores (criam o incremento a cada Sprint).
  - **Cerimônias:** Sprint Planning, Daily Scrum (15 min), Sprint Review (demonstração do incremento), Sprint Retrospective (melhoria contínua da equipe).
  - **Artefatos:** Product Backlog, Sprint Backlog e Incremento (com Definição de Pronto / Definition of Done).

- **Kanban:** Sistema de fluxo puxado, focado em visualização do trabalho, limitação do Trabalho em Progresso (WIP - Work in Progress) e redução do lead time.
- **DevOps e CI/CD:** Integração frequente de código em repositório central com testes automatizados (CI) e deploy automatizado e confiável para produção (CD).
""",
        "radiografia_bancas": {
            "fgv": "A FGV coloca um conflito real entre o cliente que quer mudar o escopo no meio da Sprint e pergunta qual deve ser a postura do Product Owner e do Scrum Master.",
            "cebraspe": "O Cebraspe adora trocar atribuições: afirma que 'compete ao Scrum Master priorizar os itens do Product Backlog' (ERRADO: é responsabilidade exclusiva do Product Owner).",
            "quadrix": "A Quadrix cobra a duração padrão dos eventos do Scrum (ex: Daily de 15 minutos, Sprint de 1 a 4 semanas).",
            "ibfc": "O IBFC faz questões associando características ao XP (Extreme Programming): Programação em Par, TDD, Refatoração e Integração Contínua.",
        },
        "pontos_criticos": [
            "O Scrum Master NÃO é gerente de projetos: ele não cobra tarefas, ele remove impedimentos e ensina agilidade.",
            "A Sprint não deve ser alterada durante sua execução se isso colocar em risco a Meta da Sprint (Sprint Goal).",
            "Kanban não possui papéis fixos nem timeboxes obrigatórios como o Scrum: o foco do Kanban é no fluxo contínuo.",
        ],
        "questoes_ids": ["q-fgv-agil-01", "q-ceb-agil-01", "q-qdx-agil-01"],
    },
    {
        "id": "es-02",
        "disciplina": "Engenharia de Software",
        "titulo": "Aula 02: Padrões de Projeto (GoF), Arquitetura de Software e Princípios SOLID",
        "objetivos": [
            "Diferenciar os 3 grupos de padrões GoF: Criacionais, Estruturais e Comportamentais.",
            "Dominar os princípios SOLID de design orientado a objetos.",
            "Compreender arquitetura de microsserviços vs monólito e comunicação síncrona (REST/gRPC) vs assíncrona (filas/eventos).",
        ],
        "teoria_resumida": """
- **Padrões de Projeto GoF (Gang of Four):**
  - **Criacionais:** Tratam da criação de objetos (Singleton, Factory Method, Abstract Factory, Builder, Prototype).
  - **Estruturais:** Tratam da composição de classes e objetos (Adapter, Decorator, Facade, Composite, Proxy, Bridge).
  - **Comportamentais:** Tratam de algoritmos e atribuição de responsabilidades entre objetos (Observer, Strategy, State, Command, Template Method).

- **Princípios SOLID:**
  - **S (Single Responsibility):** Uma classe deve ter um, e apenas um, motivo para mudar.
  - **O (Open/Closed):** Aberta para extensão, fechada para modificação.
  - **L (Liskov Substitution):** Subclasses devem poder substituir suas classes base sem quebrar o sistema.
  - **I (Interface Segregation):** Muitas interfaces específicas são melhores que uma geral.
  - **D (Dependency Inversion):** Dependa de abstrações, não de implementações concretas.
""",
        "radiografia_bancas": {
            "fgv": "A FGV descreve um problema de código onde um objeto precisa notificar múltiplos outros sem acoplamento direto e pergunta qual padrão GoF soluciona (Observer) ou como aplicar o Princípio de Inversão de Dependência.",
            "cebraspe": "O Cebraspe frequentemente confunde Adapter (converte uma interface em outra) com Facade (simplifica uma interface complexa para um subsistema).",
            "quadrix": "A Quadrix cobra a classificação: pergunta quais dos padrões listados pertencem à categoria Criacional.",
            "ibfc": "O IBFC cobra a definição direta de Singleton (garantir uma única instância e ponto global de acesso).",
        },
        "pontos_criticos": [
            "Decorator adiciona responsabilidades a objetos dinamicamente sem usar herança.",
            "Strategy permite trocar algoritmos em tempo de execução encapsulando cada um em uma classe separada.",
            "Em microsserviços, cada serviço deve ter seu próprio banco de dados para evitar acoplamento oculto.",
        ],
        "questoes_ids": ["q-fgv-gof-01", "q-ceb-gof-01", "q-ibfc-gof-01"],
    },
    {
        "id": "port-01",
        "disciplina": "Língua Portuguesa",
        "titulo": "Aula 01: Compreensão e Interpretação de Texto, Coesão e Relações Semânticas",
        "objetivos": [
            "Diferenciar compreensão (o que está explícito no texto) de interpretação (inferências legítimas).",
            "Identificar elementos de coesão anafórica e catafórica.",
            "Reconhecer relações de causa, consequência, concessão, oposição e condição.",
        ],
        "teoria_resumida": """
A interpretação textual em concursos de alto nível não mede sua opinião pessoal, mas sua capacidade de rastrear a cadeia argumentativa do autor:

- **Compreensão Textual:** Baseia-se no que está textualmente explícito ('De acordo com o texto...', 'O autor afirma que...').
- **Interpretação / Inferência:** Deduz-se a partir de pistas textuais ('Infere-se do texto...', 'Conclui-se que...'). Atenção: extrapolação, redução ou inversão de sentido são os erros clássicos.
- **Conectivos Essenciais:**
  - **Concessão:** 'embora', 'conquanto', 'ainda que', 'apesar de que', 'posto que' (introduzem quebra de expectativa sem anular a oração principal).
  - **Adversidade:** 'mas', 'porém', 'contudo', 'todavia', 'entretanto', 'no entanto'.
  - **Causa vs Consequência:** Causa é o motivo anterior no tempo; consequência é o efeito resultante.
""",
        "radiografia_bancas": {
            "fgv": "A FGV é a banca mais sofisticada em Português: cria questões sobre a intencionalidade discursiva do autor, ambiguidade deliberada, figuras de estilo e paráfrases sutis.",
            "cebraspe": "O Cebraspe adora itens propondo a substituição de conectivos: 'O vocábulo X poderia ser substituído por Y sem prejuízo para a correção gramatical e o sentido original do texto'.",
            "quadrix": "A Quadrix foca em identificar a que termo da oração um pronome relativo ('que', 'cujo', 'onde') ou demonstrativo faz referência anafórica.",
            "ibfc": "O IBFC pergunta diretamente qual conjunção expressa ideia de conformidade ou concessão.",
        },
        "pontos_criticos": [
            "'Conquanto' é conjunção CONCESSIVA (equivale a 'embora'), e não causal ou conclusiva.",
            "O pronome relativo 'onde' SÓ pode ser usado para se referir a lugares físicos concretos. Em situações abstratas, usa-se 'em que', 'no qual', 'na qual'.",
            "Cuidado com a expressão 'prejuízo para a correção gramatical' vs 'prejuízo para o sentido original': muitas substituições mantêm a gramática correta, mas alteram a nuance de significado.",
        ],
        "questoes_ids": ["q-fgv-port-01", "q-ceb-port-01", "q-qdx-port-01"],
    },
    {
        "id": "dir-01",
        "disciplina": "Direito Constitucional",
        "titulo": "Aula 01: Direitos e Garantias Fundamentais (Art. 5º da CF/88) e Remédios Constitucionais",
        "objetivos": [
            "Dominar as principais garantias do Art. 5º da Constituição Federal de 1988.",
            "Diferenciar Mandado de Segurança, Habeas Corpus, Habeas Data, Mandado de Injunção e Ação Popular.",
            "Conhecer as hipóteses de violação de domicílio e sigilo das comunicações telefônicas.",
        ],
        "teoria_resumida": """
O Art. 5º da CF/88 consagra os direitos fundamentais individuais e coletivos para brasileiros e estrangeiros residentes no país (jurisprudência do STF estende para não residentes em trânsito):

- **Inviolabilidade do Domicílio (Art. 5º, XI):**
  - A casa é asilo inviolável. Ninguém nela pode penetrar sem consentimento, SALVO:
    - A qualquer hora do dia ou da noite: flagrante delito, desastre ou para prestar socorro.
    - Durante o dia: apenas por determinação judicial.

- **Remédios Constitucionais:**
  - **Habeas Corpus:** Liberdade de locomoção (gratuito, dispensa advogado).
  - **Habeas Data:** Conhecimento ou retificação de informações relativas à pessoa do impetrante constantes de bancos de dados públicos ou governamentais (gratuito, exige recusa administrativa prévia).
  - **Mandado de Segurança:** Direito líquido e certo não amparado por HC ou HD (prazo decadencial de 120 dias).
  - **Mandado de Injunção:** Falta de norma regulamentadora que torne inviável o exercício de direitos e liberdades constitucionais.
  - **Ação Popular:** Qualquer cidadão pode propor para anular ato lesivo ao patrimônio público, moralidade administrativa, meio ambiente e patrimônio histórico/cultural (gratuita, salvo má-fé).
""",
        "radiografia_bancas": {
            "fgv": "A FGV narra uma busca policial em domicílio ou empresa com hora marcada e pergunta a validade da prova recolhida à luz da jurisprudência do STF.",
            "cebraspe": "O Cebraspe traz itens sobre a gratuidade dos remédios constitucionais e sobre a necessidade de prévio esgotamento administrativo (ex: Súmula Vinculante 2 para Habeas Data).",
            "quadrix": "A Quadrix cobra a literalidade das hipóteses de entrada forçada em domicílio e os legitimados para Mandado de Segurança Coletivo.",
            "ibfc": "O IBFC cobra a correlação direta entre o remédio constitucional e a situação de fato apresentada no enunciado.",
        },
        "pontos_criticos": [
            "Habeas Data exige prévia recusa da administração pública para que haja interesse de agir.",
            "Ação Popular só pode ser proposta por CIDADÃO (pessoa física no pleno gozo dos direitos políticos com título de eleitor). Pessoa jurídica NÃO pode propor Ação Popular (Súmula 365 STF).",
            "A quebra do sigilo das comunicações telefônicas (interceptação) exige ordem judicial, para fins de investigação criminal ou instrução processual penal, na forma da lei (não cabe em processo civil ou administrativo puro).",
        ],
        "questoes_ids": ["q-ceb-dir-01", "q-fgv-dir-01", "q-ibfc-dir-01"],
    },
]


def list_lessons(disciplina: str | None = None) -> list[dict[str, Any]]:
    """Lista as aulas cadastradas, com sumário e objetivos."""
    if not disciplina:
        return [
            {
                "id": l["id"],
                "disciplina": l["disciplina"],
                "titulo": l["titulo"],
                "objetivos": l["objetivos"],
                "total_questoes": len(l.get("questoes_ids", [])),
            }
            for l in _LESSONS
        ]
    disc_norm = disciplina.strip().lower()
    return [
        {
            "id": l["id"],
            "disciplina": l["disciplina"],
            "titulo": l["titulo"],
            "objetivos": l["objetivos"],
            "total_questoes": len(l.get("questoes_ids", [])),
        }
        for l in _LESSONS
        if l["disciplina"].strip().lower() == disc_norm
    ]


def get_lesson(lesson_id: str) -> dict[str, Any] | None:
    """Retorna os detalhes completos de uma aula."""
    for l in _LESSONS:
        if l["id"] == lesson_id:
            return l
    return None
