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

_BANCA_METRICS: dict[str, dict[str, Any]] = {
    "fgv": {
        "dificuldade": 9.5,
        "indice_pegadinhas": 92,
        "perfil_cobranca": {"interpretacao": 70, "doutrina_jurisprudencia": 20, "lei_seca": 10},
        "tempo_medio_questao": "3 min (Textos Longos)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "federal",
        "categoria_label": "Federal & Nacional",
        "top_disciplinas_ti": ["Microsserviços", "SQL Analítico & ACID", "Padrões GoF", "Engenharia de Software"],
    },
    "cebraspe": {
        "dificuldade": 9.6,
        "indice_pegadinhas": 96,
        "perfil_cobranca": {"interpretacao": 45, "doutrina_jurisprudencia": 40, "lei_seca": 15},
        "tempo_medio_questao": "1m30s (Itens C/E)",
        "fator_chute": "Crítico: 1 Erro Anula 1 Acerto",
        "categoria": "federal",
        "categoria_label": "Federal & Nacional",
        "top_disciplinas_ti": ["Segurança (ISO 27001)", "Redes (BGP/OSPF/TCP)", "Governança (ITIL/COBIT)", "DevOps & Cloud"],
    },
    "fcc": {
        "dificuldade": 9.0,
        "indice_pegadinhas": 65,
        "perfil_cobranca": {"interpretacao": 30, "doutrina_jurisprudencia": 45, "lei_seca": 25},
        "tempo_medio_questao": "2m15s (Equilibrado)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "tribunais",
        "categoria_label": "Tribunais & Carreiras",
        "top_disciplinas_ti": ["Java & Spring", "Modelagem Relacional", "Governança (ITIL/PMBOK)", "Estruturas de Dados"],
    },
    "cesgranrio": {
        "dificuldade": 8.5,
        "indice_pegadinhas": 55,
        "perfil_cobranca": {"interpretacao": 50, "doutrina_jurisprudencia": 25, "lei_seca": 25},
        "tempo_medio_questao": "2 min (Direto)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "federal",
        "categoria_label": "Federal & Estatais",
        "top_disciplinas_ti": ["Ciência de Dados (Python)", "DevOps & Docker", "SQL & NoSQL", "Engenharia de Requisitos"],
    },
    "esaf": {
        "dificuldade": 9.4,
        "indice_pegadinhas": 85,
        "perfil_cobranca": {"interpretacao": 40, "doutrina_jurisprudencia": 40, "lei_seca": 20},
        "tempo_medio_questao": "3 min (Denso)",
        "fator_chute": "Mínimo Eliminatório por Matéria",
        "categoria": "federal",
        "categoria_label": "Federal & Fiscais",
        "top_disciplinas_ti": ["Governança Setor Público", "Auditoria de TI", "Contratações Públicas (TCU)", "Gestão de Riscos"],
    },
    "vunesp": {
        "dificuldade": 7.8,
        "indice_pegadinhas": 45,
        "perfil_cobranca": {"interpretacao": 20, "doutrina_jurisprudencia": 10, "lei_seca": 70},
        "tempo_medio_questao": "1m45s (Objetivo)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "tribunais",
        "categoria_label": "Estadual & Tribunais",
        "top_disciplinas_ti": ["Comandos SO (Linux/Win)", "Redes & Sub-redes", "Hardware & Periféricos", "SQL Básico/Médio"],
    },
    "fundatec": {
        "dificuldade": 7.2,
        "indice_pegadinhas": 40,
        "perfil_cobranca": {"interpretacao": 25, "doutrina_jurisprudencia": 15, "lei_seca": 60},
        "tempo_medio_questao": "1m45s (Direto)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "regional",
        "categoria_label": "Regional & Sul",
        "top_disciplinas_ti": ["Cabeamento & Redes", "Segurança & Malwares", "Suporte & Hardware", "SQL Básico"],
    },
    "comissao_propria": {
        "dificuldade": 8.0,
        "indice_pegadinhas": 50,
        "perfil_cobranca": {"interpretacao": 30, "doutrina_jurisprudencia": 30, "lei_seca": 40},
        "tempo_medio_questao": "2m30s (Específico)",
        "fator_chute": "Conforme Edital",
        "categoria": "tribunais",
        "categoria_label": "Órgão Próprio",
        "top_disciplinas_ti": ["Stack Tecnológica do Órgão", "Regimento Interno", "PDTI Local", "Sistemas Legados"],
    },
    "ibam": {
        "dificuldade": 6.5,
        "indice_pegadinhas": 35,
        "perfil_cobranca": {"interpretacao": 25, "doutrina_jurisprudencia": 10, "lei_seca": 65},
        "tempo_medio_questao": "1m30s (4 Alternativas)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "regional",
        "categoria_label": "Municipal & Regional",
        "top_disciplinas_ti": ["Office & LibreOffice", "Microinformática", "Redes Locais", "Leis Municipais"],
    },
    "quadrix": {
        "dificuldade": 8.2,
        "indice_pegadinhas": 78,
        "perfil_cobranca": {"interpretacao": 35, "doutrina_jurisprudencia": 25, "lei_seca": 40},
        "tempo_medio_questao": "1m40s (Itens C/E)",
        "fator_chute": "Penalidade Parcial ou Total",
        "categoria": "conselhos",
        "categoria_label": "Conselhos & Autarquias",
        "top_disciplinas_ti": ["Comandos Linux (bash)", "SQL & Joins", "Redes Locais", "Regimento dos Conselhos"],
    },
    "consesp": {
        "dificuldade": 6.2,
        "indice_pegadinhas": 30,
        "perfil_cobranca": {"interpretacao": 15, "doutrina_jurisprudencia": 5, "lei_seca": 80},
        "tempo_medio_questao": "1m20s (Rápido)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "regional",
        "categoria_label": "Municipal & Interior",
        "top_disciplinas_ti": ["Hardware & Memórias", "Atalhos do Windows", "Prompt de Comando", "Pacote Office"],
    },
    "idib": {
        "dificuldade": 7.5,
        "indice_pegadinhas": 55,
        "perfil_cobranca": {"interpretacao": 40, "doutrina_jurisprudencia": 20, "lei_seca": 40},
        "tempo_medio_questao": "1m50s (Intermediário)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "conselhos",
        "categoria_label": "Conselhos & Médias",
        "top_disciplinas_ti": ["Diagramas UML 2.5", "Banco Relacional (DDL/DML)", "Noções de Nuvem (SaaS)", "Segurança Básica"],
    },
    "fepese": {
        "dificuldade": 8.8,
        "indice_pegadinhas": 60,
        "perfil_cobranca": {"interpretacao": 40, "doutrina_jurisprudencia": 30, "lei_seca": 30},
        "tempo_medio_questao": "2m30s (Acadêmico)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "tribunais",
        "categoria_label": "Estadual de Elite (SC)",
        "top_disciplinas_ti": ["Estruturas de Dados (BST/Grafos)", "Otimização de Consultas SQL", "Protocolo TCP a Fundo", "Álgebra Relacional"],
    },
    "legalle": {
        "dificuldade": 6.8,
        "indice_pegadinhas": 35,
        "perfil_cobranca": {"interpretacao": 20, "doutrina_jurisprudencia": 10, "lei_seca": 70},
        "tempo_medio_questao": "1m30s (Direto)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "regional",
        "categoria_label": "Municipal & Sul",
        "top_disciplinas_ti": ["Manutenção & Suporte", "Active Directory & Windows", "Políticas de Backup", "Normas de Segurança"],
    },
    "consulpam": {
        "dificuldade": 6.4,
        "indice_pegadinhas": 32,
        "perfil_cobranca": {"interpretacao": 20, "doutrina_jurisprudencia": 10, "lei_seca": 70},
        "tempo_medio_questao": "1m25s (Direto)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "regional",
        "categoria_label": "Municipal & Nordeste",
        "top_disciplinas_ti": ["Microinformática", "Protocolos TCP/IP", "Memórias & Periféricos", "Antivírus & Firewall"],
    },
    "ibfc": {
        "dificuldade": 7.4,
        "indice_pegadinhas": 45,
        "perfil_cobranca": {"interpretacao": 25, "doutrina_jurisprudencia": 15, "lei_seca": 60},
        "tempo_medio_questao": "1m40s (Objetivo)",
        "fator_chute": "Livre (Sem penalidade)",
        "categoria": "conselhos",
        "categoria_label": "Autarquias & Estados",
        "top_disciplinas_ti": ["Portas & Protocolos Padrão", "Modelos de Ciclo de Vida", "Scrum & RUP", "Consultas SQL Simples"],
    },
}


def get_banca_profiles() -> dict[str, dict[str, Any]]:
    """Retorna os perfis analíticos comparativos de estilo de exame de cada banca enriquecidos com métricas."""
    result: dict[str, dict[str, Any]] = {}
    for bid, bdata in _BANCAS.items():
        copy_data = dict(bdata)
        metrics = _BANCA_METRICS.get(bid, {})
        copy_data.update(metrics)
        result[bid] = copy_data
    return result


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
                "tabela_resumo": {
            "titulo": "Resumo Comparativo das Formas Normais",
            "colunas": ["Forma Normal", "Requisito Fundamental", "O que Elimina", "Pegadinha Frequente"],
            "linhas": [
                ["1FN", "Atributos atômicos e indivisíveis", "Grupos repetitivos e campos multivalorados", "Telefones separados por vírgula violam a 1FN"],
                ["2FN", "Estar na 1FN + dependência total da PK", "Dependência parcial de chaves compostas", "Se a PK for simples (1 coluna), estando na 1FN já está na 2FN"],
                ["3FN", "Estar na 2FN + sem dependência transitiva", "Dependência entre colunas não-chave", "Atributo não-chave determinando outro não-chave"],
                ["BCNF", "Todo determinante de DF deve ser chave candidata", "Anomalias de dependência funcional composta", "Mais restritiva que a 3FN tradicional"],
            ]
        },
        "videoaulas": [
            {
                "titulo": "Modelagem de Dados e Formas Normais (1FN, 2FN e 3FN) para Concursos",
                "canal": "Curso em Vídeo",
                "duracao": "26 min",
                "youtube_id": "Ofktsne-utM",
                "descricao": "Aula didática passo a passo explicando como transformar tabelas não normalizadas em 1FN, 2FN e 3FN sem perda de dados."
            },
            {
                "titulo": "Banco de Dados para FGV e Cebraspe - Questões Comentadas de Normalização",
                "canal": "Gran Concursos TI",
                "duracao": "34 min",
                "youtube_id": "K_Qkxv_C34k",
                "descricao": "Resolução de questões de alto nível focando nas armadilhas de dependência parcial e transitiva."
            }
        ],
        "flashcards": [
            {
                "id": "fc-bd-01",
                "frente": "Qual a exigência mandatória da Primeira Forma Normal (1FN)?",
                "verso": "Todos os atributos devem ser ATÔMICOS (indivisíveis) e monovalorados. Proíbe listas, arrays ou campos separados por vírgula.",
                "mnemonico": "1FN = Átomo único (sem vírgulas nem coleções)",
                "tag": "Banco de Dados"
            },
            {
                "id": "fc-bd-02",
                "frente": "Uma tabela na 1FN com chave primária SIMPLES (1 atributo) já está na 2FN?",
                "verso": "SIM! A 2FN proíbe dependência PARCIAL. Se a chave primária só tem um atributo, não existe como depender de apenas uma fração dela.",
                "mnemonico": "PK Simples na 1FN ➔ Automaticamente 2FN",
                "tag": "Banco de Dados"
            },
            {
                "id": "fc-bd-03",
                "frente": "Como identificar uma violação da Terceira Forma Normal (3FN)?",
                "verso": "Quando existe dependência TRANSITIVA entre atributos não-chave: um campo comum determina outro campo comum (A ➔ B e B ➔ C).",
                "mnemonico": "3FN = Proibida ponte entre atributos não-chaves",
                "tag": "Banco de Dados"
            },
            {
                "id": "fc-bd-04",
                "frente": "Em qual situação a normalização pode ser desfavorável na prática?",
                "verso": "Em sistemas analíticos (Data Warehouses / OLAP): o excesso de JOINs degrada a performance de leitura, justificando a desnormalização controlada.",
                "mnemonico": "OLTP = Normalizado (3FN) | OLAP = Desnormalizado (Star Schema)",
                "tag": "Banco de Dados"
            }
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
                "tabela_resumo": {
            "titulo": "Guia de Sobrevivência em SQL para Provas",
            "colunas": ["Comando / Cláusula", "Classificação", "Comportamento Chave", "Cai na Banca Como..."],
            "linhas": [
                ["DELETE vs TRUNCATE", "DML vs DDL", "DELETE aceita WHERE e gera log; TRUNCATE zera a tabela inteira e reseta sequence", "Afirmar que TRUNCATE aceita WHERE (Falso!)"],
                ["WHERE vs HAVING", "Filtro", "WHERE filtra antes do agrupamento; HAVING filtra grupos após GROUP BY", "Usar função de agregação como COUNT() no WHERE (Erro!)"],
                ["LEFT JOIN", "Junção Externa", "Retorna tudo da esquerda + correspondentes da direita (NULL onde faltar)", "Identificar registros órfãos usando WHERE direita.id IS NULL"],
                ["COUNT(*) vs COUNT(col)", "Agregação", "COUNT(*) conta todas as linhas; COUNT(col) ignora nulos", "Pegadinha de total de linhas com valores NULL"],
            ]
        },
        "videoaulas": [
            {
                "titulo": "SQL do Zero ao Avançado para Concursos de TI",
                "canal": "Prof. Concursos TI",
                "duracao": "38 min",
                "youtube_id": "8H6Qk8gU0L0",
                "descricao": "Ordem lógica de execução das cláusulas SQL (FROM, WHERE, GROUP BY, HAVING, SELECT, ORDER BY) e tipos de JOIN."
            },
            {
                "titulo": "Subconsultas e Funções de Janela (Window Functions) na FGV",
                "canal": "Estratégia Concursos",
                "duracao": "29 min",
                "youtube_id": "3pvdc_GkH88",
                "descricao": "Dominando ROW_NUMBER(), RANK(), DENSE_RANK() e subqueries correlacionadas que mais caem em TI."
            }
        ],
        "flashcards": [
            {
                "id": "fc-sql-01",
                "frente": "Qual a ordem lógica real de processamento de uma query SQL?",
                "verso": "1. FROM ➔ 2. WHERE ➔ 3. GROUP BY ➔ 4. HAVING ➔ 5. SELECT ➔ 6. DISTINCT ➔ 7. ORDER BY ➔ 8. LIMIT.",
                "mnemonico": "FW-GHSL: From, Where, Group, Having, Select, Limit",
                "tag": "SQL"
            },
            {
                "id": "fc-sql-02",
                "frente": "Por que 'SELECT * FROM tabela WHERE COUNT(id) > 5' é inválido?",
                "verso": "Porque funções de agregação como COUNT, SUM, AVG só podem ser filtradas na cláusula HAVING, nunca no WHERE.",
                "mnemonico": "WHERE = Linha a linha | HAVING = Grupos agregados",
                "tag": "SQL"
            },
            {
                "id": "fc-sql-03",
                "frente": "Qual a diferença essencial entre INNER JOIN e LEFT JOIN?",
                "verso": "INNER JOIN retorna apenas a interseção (match dos dois lados). LEFT JOIN preserva 100% da tabela esquerda mesmo sem par na direita.",
                "mnemonico": "INNER = Apenas pares completos | LEFT = Esquerda garantida",
                "tag": "SQL"
            }
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
                "tabela_resumo": {
            "titulo": "Scrum vs Kanban vs XP: Diferenças Essenciais",
            "colunas": ["Framework", "Papéis Definidos", "Ritmo de Entrega", "Métrica / Foco Principal"],
            "linhas": [
                ["Scrum", "Product Owner, Scrum Master, Developers", "Sprints fixas (timebox de 1 a 4 semanas)", "Sprint Goal e Velocity da equipe"],
                ["Kanban", "Sem papéis pré-definidos", "Fluxo contínuo (puxado)", "Limitação de WIP e redução do Lead Time"],
                ["XP (Extreme)", "Equipe com foco em engenharia", "Iterações curtas (1 a 2 semanas)", "Qualidade técnica (TDD, Pair Programming, CI)"],
            ]
        },
        "videoaulas": [
            {
                "titulo": "Scrum Guide Completo para Concursos Públicos",
                "canal": "Gabaritando TI",
                "duracao": "31 min",
                "youtube_id": "2gA9WqFv_0s",
                "descricao": "Papéis, eventos e artefatos atualizados do Scrum Guide oficial com dicas de como as bancas tentam confundir."
            },
            {
                "titulo": "Kanban e Práticas de DevOps (CI/CD) Explicados",
                "canal": "Prof. Fernando Pedrosa",
                "duracao": "24 min",
                "youtube_id": "W1vL6v1MsqA",
                "descricao": "Fluxo puxado, limites de WIP, Lead Time vs Cycle Time e automação de pipelines com Docker e Git."
            }
        ],
        "flashcards": [
            {
                "id": "fc-es-01",
                "frente": "No Scrum, quem é o único responsável pela gestão e priorização do Product Backlog?",
                "verso": "O Product Owner (PO). Nem o Scrum Master nem os Desenvolvedores decidem a prioridade dos itens de negócio.",
                "mnemonico": "PO = Dono do 'O Quê' | Time = Dono do 'Como'",
                "tag": "Engenharia de Software"
            },
            {
                "id": "fc-es-02",
                "frente": "O Scrum Master pode atribuir tarefas aos desenvolvedores?",
                "verso": "NÃO! O time é auto-gerenciável e auto-organizado. O Scrum Master é um líder servidor que remove impedimentos.",
                "mnemonico": "Scrum Master facilita, orienta e remove barreiras; NUNCA manda",
                "tag": "Engenharia de Software"
            },
            {
                "id": "fc-es-03",
                "frente": "Qual o objetivo central de limitar o WIP (Work In Progress) no Kanban?",
                "verso": "Evitar gargalos, expor impedimentos e reduzir o tempo total de ciclo (Lead Time), garantindo que tarefas sejam concluídas antes de novas começarem.",
                "mnemonico": "'Pare de começar e comece a terminar'",
                "tag": "Engenharia de Software"
            }
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
                "tabela_resumo": {
            "titulo": "Classificação dos Padrões GoF Mais Cobrados",
            "colunas": ["Categoria", "Padrões Clássicos", "Intenção / Propósito", "Exemplo Típico em Concursos"],
            "linhas": [
                ["Criacionais", "Singleton, Factory Method, Abstract Factory, Builder", "Isolar a criação de objetos da sua representação", "Garantir única conexão de banco (Singleton)"],
                ["Estruturais", "Adapter, Decorator, Facade, Composite, Proxy", "Composição flexível de classes e interfaces", "Adicionar funcionalidade sem herança (Decorator)"],
                ["Comportamentais", "Observer, Strategy, State, Command, Template Method", "Distribuição de algoritmos e fluxo de mensagens", "Trocar algoritmo de cálculo em runtime (Strategy)"],
            ]
        },
        "videoaulas": [
            {
                "titulo": "Padrões de Projeto GoF Descomplicados para Concursos",
                "canal": "Fábio Araújo - Concursos TI",
                "duracao": "36 min",
                "youtube_id": "3pvdc_GkH88",
                "descricao": "Diferença prática entre Strategy vs State, Adapter vs Facade e Decorator vs Proxy com diagramas UML."
            },
            {
                "titulo": "Princípios SOLID com Exemplos Práticos de Código",
                "canal": "Código Fonte TV",
                "duracao": "27 min",
                "youtube_id": "6SfrO3mMvKU",
                "descricao": "Cada uma das 5 letras do SOLID explicada com código claro e violações comuns que caem em provas."
            }
        ],
        "flashcards": [
            {
                "id": "fc-gof-01",
                "frente": "Qual a diferença entre os padrões Adapter e Facade?",
                "verso": "Adapter CONVERTE uma interface incompatível para que classes colaborem. Facade SIMPLIFICA uma interface complexa de um subsistema.",
                "mnemonico": "Adapter = Adaptador de tomada | Facade = Fachada limpa do prédio",
                "tag": "Padrões de Projeto"
            },
            {
                "id": "fc-gof-02",
                "frente": "Qual padrão GoF implementa o padrão de publicação/assinatura (Pub/Sub)?",
                "verso": "Observer. Permite que um sujeito notifique múltiplos observadores automaticamente quando seu estado muda.",
                "mnemonico": "Observer = Notificador de eventos / YouTube notify",
                "tag": "Padrões de Projeto"
            },
            {
                "id": "fc-gof-03",
                "frente": "O que preconiza o Princípio Aberto/Fechado (Open/Closed - O do SOLID)?",
                "verso": "Entidades de software devem estar ABERTAS para extensão, mas FECHADAS para modificação. Adicione novas classes sem alterar código testado.",
                "mnemonico": "Open p/ novidades | Closed p/ cirurgias no código existente",
                "tag": "SOLID"
            }
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
                "tabela_resumo": {
            "titulo": "Tabela de Ouro dos Conectivos em Provas",
            "colunas": ["Valor Semântico", "Conjunções Principais", "Atenção Especial", "Pegadinha Clássica"],
            "linhas": [
                ["Concessão", "embora, conquanto, ainda que, mesmo que, posto que", "Quebra expectativa sem anular o fato", "'Conquanto' é concessivo, nunca causal"],
                ["Adversidade", "mas, porém, contudo, todavia, entretanto, no entanto", "Contrapõe ideias (o segundo fato prevalece)", "'Mas' não pode vir após vírgula deslocado"],
                ["Causa", "porque, já que, visto que, como (no início), porquanto", "Fato anterior que gera o efeito", "'Porquanto' é causal/explicativo; 'Conquanto' é concessivo"],
                ["Condição", "se, caso, desde que (+ subjuntivo), contanto que", "Hipótese necessária", "Exige verbo no subjuntivo"],
            ]
        },
        "videoaulas": [
            {
                "titulo": "Interpretação e Semântica de Texto para FGV e Cebraspe",
                "canal": "Português com Letícia",
                "duracao": "32 min",
                "youtube_id": "W1vL6v1MsqA",
                "descricao": "Como não cair nas pegadinhas de extrapolação e contradição em enunciados longos e densos."
            },
            {
                "titulo": "Conjunções e Relações Semânticas que Mais Caem",
                "canal": "Prof. Noslen",
                "duracao": "25 min",
                "youtube_id": "Y07Z2Y9s_iI",
                "descricao": "Diferença definitiva entre conjunções concessivas, adversativas, causais e consecutivas."
            }
        ],
        "flashcards": [
            {
                "id": "fc-port-01",
                "frente": "Qual a diferença de sentido entre 'conquanto' e 'porquanto'?",
                "verso": "'Conquanto' = CONCESSÃO (equivale a 'embora'). 'Porquanto' = CAUSA / EXPLICAÇÃO (equivale a 'porque').",
                "mnemonico": "CONquanto = CONcessão | PORquanto = PORque",
                "tag": "Português"
            },
            {
                "id": "fc-port-02",
                "frente": "Em quais casos o pronome relativo 'onde' pode ser empregado segundo a norma culta?",
                "verso": "EXCLUSIVAMENTE para indicar espaço físico delimitado concreto (ex: 'A cidade onde nasci'). Em termos abstratos, usa-se 'em que' ou 'no qual'.",
                "mnemonico": "Onde = Lugar físico que você toca/pisa",
                "tag": "Português"
            },
            {
                "id": "fc-port-03",
                "frente": "A substituição de conectivos mantém a correção gramatical e o sentido original?",
                "verso": "Muitas vezes mantém a gramática, mas ALTERA a relação de sentido (ex: trocar 'porque' por 'portanto' inverte causa e consequência). Cuidado com o comando da questão!",
                "mnemonico": "Gramática pode continuar válida mesmo invertendo o sentido!",
                "tag": "Português"
            }
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
                "tabela_resumo": {
            "titulo": "Quadro Comparativo dos 5 Remédios Constitucionais",
            "colunas": ["Remédio", "Direito Protegido", "Legitimidade Ativa", "Custas Judiciais", "Prazo / Requisito"],
            "linhas": [
                ["Habeas Corpus", "Liberdade de locomoção (ir e vir)", "Qualquer pessoa (física ou jurídica)", "Gratuito (dispensa advogado)", "Não tem prazo decadencial"],
                ["Habeas Data", "Acesso ou retificação de dados pessoais", "Apenas a própria pessoa (personalíssimo)", "Gratuito", "Exige recusa administrativa prévia"],
                ["Mandado de Segurança", "Direito líquido e certo não amparado por HC/HD", "Pessoa física ou jurídica prejudicada", "Pago (salvo gratuidade da justiça)", "Prazo decadencial de 120 dias"],
                ["Mandado de Injunção", "Falta de norma regulamentadora de direito", "Titular do direito inviabilizado", "Pago (processo civil)", "Necessita de omissão legislativa"],
                ["Ação Popular", "Patrimônio público, moralidade e meio ambiente", "Apenas CIDADÃO (com título eleitoral)", "Gratuita (salvo comprovada má-fé)", "Pessoa jurídica NÃO tem legitimidade"],
            ]
        },
        "videoaulas": [
            {
                "titulo": "Remédios Constitucionais Esquematizados (Art. 5º da CF)",
                "canal": "Estratégia Concursos",
                "duracao": "33 min",
                "youtube_id": "Y07Z2Y9s_iI",
                "descricao": "Quadro mnemônico dos remédios constitucionais com jurisprudência atualizada do STF e STJ."
            },
            {
                "titulo": "Inviolabilidade de Domicílio e Sigilos no STF",
                "canal": "Gran Cursos Online",
                "duracao": "28 min",
                "youtube_id": "Ofktsne-utM",
                "descricao": "As 4 exceções da entrada forçada em domicílio (Art. 5º, XI) e a tese de repercussão geral do STF."
            }
        ],
        "flashcards": [
            {
                "id": "fc-dir-01",
                "frente": "Pessoa Jurídica (empresa ou associação) pode ajuizar Ação Popular?",
                "verso": "NÃO! Ação Popular é remédio privativo do CIDADÃO (pessoa física no pleno exercício dos direitos políticos). Súmula 365 do STF.",
                "mnemonico": "Ação Popular = Exclusivo de quem vota (tem título)",
                "tag": "Direito Constitucional"
            },
            {
                "id": "fc-dir-02",
                "frente": "Quando é permitida a entrada na casa do indivíduo sem seu consentimento?",
                "verso": "A qualquer hora: flagrante delito, desastre ou socorro. Durante o dia (apenas): por determinação JUDICIAL.",
                "mnemonico": "Noite = FDS (Flagrante, Desastre, Socorro). Juiz = Só de dia!",
                "tag": "Direito Constitucional"
            },
            {
                "id": "fc-dir-03",
                "frente": "Qual o requisito indispensável para impetrar Habeas Data?",
                "verso": "A prova da RECUSA ou omissão da autoridade administrativa em fornecer ou retificar a informação (Súmula Vinculante 2 do STF).",
                "mnemonico": "Sem pedido negado na administração = Sem Habeas Data",
                "tag": "Direito Constitucional"
            }
        ],
        "questoes_ids": ["q-ceb-dir-01", "q-fgv-dir-01", "q-ibfc-dir-01"],
    },
    {
        "id": "red-01",
        "disciplina": "Redes de Computadores",
        "titulo": "Aula 01: Arquitetura em Camadas (Modelo OSI vs TCP/IP), Protocolos e Roteamento",
        "objetivos": [
            "Dominar as 7 camadas do Modelo OSI e as 4 camadas da arquitetura TCP/IP.",
            "Diferenciar perfeitamente TCP (orientado a conexão) de UDP (não orientado, baixa latência).",
            "Conhecer protocolos essenciais e suas portas padrão: DNS (53), DHCP (67/68), HTTP (80), HTTPS (443), SSH (22)."
        ],
        "teoria_resumida": """
O Modelo OSI (Open Systems Interconnection) da ISO padronizou a comunicação em 7 camadas lógicas:
1. Física (bits e meios de transmissão)
2. Enlace (quadros/frames, endereços MAC, switches L2)
3. Rede (pacotes, endereçamento IP, roteamento L3)
4. Transporte (segmentos, TCP/UDP, confiabilidade fim a fim)
5. Sessão (estabelecimento e controle de sessões)
6. Apresentação (criptografia, compressão e formatação de dados)
7. Aplicação (interface com o usuário: HTTP, DNS, SMTP, FTP)

A arquitetura prática TCP/IP simplifica para 4 camadas: Acesso à Rede (Física + Enlace), Internet (Rede), Transporte e Aplicação (Sessão + Apresentação + Aplicação).

- **TCP vs UDP:**
  - **TCP (Transmission Control Protocol):** Confiável, orientado a conexão, realiza three-way handshake (SYN, SYN-ACK, ACK), controle de fluxo (Janela Deslizante) e controle de congestionamento.
  - **UDP (User Datagram Protocol):** Não confiável, sem conexão, sem controle de fluxo, com cabeçalho reduzido (8 bytes contra 20 bytes do TCP). Ideal para streaming de voz/vídeo (VoIP) e DNS rápido.
""",
        "tabela_resumo": {
            "titulo": "Comparativo Modelo OSI vs TCP/IP e Unidades de Dados (PDU)",
            "colunas": ["Camada OSI", "Camada TCP/IP", "Unidade de Dados (PDU)", "Protocolos / Equipamentos"],
            "linhas": [
                ["Aplicação / Apresentação / Sessão", "Aplicação", "Dados / Mensagem", "HTTP, HTTPS (443), DNS (53), SSH (22), SMTP (587)"],
                ["Transporte", "Transporte", "Segmento", "TCP (Conexão e Controle) e UDP (Velocidade e Datagrama)"],
                ["Rede", "Internet", "Pacote", "IP (IPv4/IPv6), ICMP (Ping), Roteadores L3"],
                ["Enlace", "Acesso à Rede", "Quadro (Frame)", "Ethernet, Endereço MAC (48 bits), Switches L2"],
                ["Física", "Acesso à Rede", "Bits", "Cabos, Fibra óptica, Hubs, Modulação"],
            ]
        },
        "videoaulas": [
            {
                "titulo": "Modelo OSI e TCP/IP na Prática para Concursos de TI",
                "canal": "Prof. Concursos TI",
                "duracao": "35 min",
                "youtube_id": "Vcb5F4P7eFw",
                "descricao": "Mnemônico infalível das 7 camadas do modelo OSI e fluxo de encapsulamento e desencapsulamento."
            },
            {
                "titulo": "TCP vs UDP e Three-Way Handshake Explicados",
                "canal": "Gabaritando TI",
                "duracao": "22 min",
                "youtube_id": "K_Qkxv_C34k",
                "descricao": "Como o handshake SYN / SYN-ACK / ACK funciona e como o Cebraspe tenta enganar o candidato."
            }
        ],
        "flashcards": [
            {
                "id": "fc-red-01",
                "frente": "Qual a ordem das 7 camadas do Modelo OSI da mais baixa à mais alta?",
                "verso": "1. Física ➔ 2. Enlace ➔ 3. Rede ➔ 4. Transporte ➔ 5. Sessão ➔ 6. Apresentação ➔ 7. Aplicação.",
                "mnemonico": "'FERTS-AA' (Física, Enlace, Rede, Transporte, Sessão, Apresentação, Aplicação)",
                "tag": "Redes"
            },
            {
                "id": "fc-red-02",
                "frente": "Como é chamada a Unidade de Dados (PDU) nas camadas 4, 3 e 2 do modelo OSI?",
                "verso": "Camada 4 (Transporte) = SEGMENTO | Camada 3 (Rede) = PACOTE | Camada 2 (Enlace) = QUADRO (FRAME).",
                "mnemonico": "Transporte Segmenta, Rede Pacota, Enlace Enquadra",
                "tag": "Redes"
            },
            {
                "id": "fc-red-03",
                "frente": "Qual a sequência de flags do aperto de mão de três vias (Three-Way Handshake) do TCP?",
                "verso": "1. Cliente envia SYN ➔ 2. Servidor responde SYN-ACK ➔ 3. Cliente confirma com ACK.",
                "mnemonico": "SYN ➔ SYN-ACK ➔ ACK (Olá? ➔ Olá, ouvi! ➔ Confirmado!)",
                "tag": "Redes"
            }
        ],
        "radiografia_bancas": {
            "fgv": "A FGV descreve uma topologia de rede corporativa e pergunta em qual camada do modelo OSI atua determinado filtro de firewall stateful ou balanceador de carga.",
            "cebraspe": "O Cebraspe adora trocar as funções de TCP e UDP, ou afirmar que o UDP realiza controle de congestionamento (FALSO!).",
            "quadrix": "A Quadrix cobra as portas padrão dos protocolos de rede mais utilizados.",
            "ibfc": "O IBFC foca em qual camada do OSI pertence determinado protocolo (ex: ICMP pertence à camada de Rede)."
        },
        "pontos_criticos": [
            "O protocolo ICMP (usado pelo comando ping) opera na Camada de Rede (Camada 3), encapsulado diretamente em pacotes IP.",
            "O endereço MAC opera na Camada de Enlace (Camada 2) e possui 48 bits (6 bytes hexadecimais).",
            "DNS opera primariamente sobre UDP na porta 53 para consultas rápidas, mas utiliza TCP para transferência de zona entre servidores."
        ],
        "questoes_ids": ["q-ceb-red-01", "q-fgv-red-01"]
    },
    {
        "id": "seg-01",
        "disciplina": "Segurança da Informação",
        "titulo": "Aula 01: Princípios (CID), Criptografia Simétrica vs Assimétrica, Hash e OWASP",
        "objetivos": [
            "Dominar os 5 pilares da Segurança: Confidencialidade, Integridade, Disponibilidade, Autenticidade e Não-Repúdio.",
            "Diferenciar criptografia de chave simétrica (AES, DES) de assimétrica (RSA, ECC, chaves pública e privada).",
            "Compreender a assinatura digital (criptografa o hash com a chave PRIVADA do remetente) e vulnerabilidades OWASP Top 10."
        ],
        "teoria_resumida": """
A Segurança da Informação apoia-se nos pilares CIDAN:
- **Confidencialidade:** Sigilo contra acesso não autorizado (garantido por criptografia).
- **Integridade:** Certeza de que o dado não foi alterado indevidamente (garantido por funções hash).
- **Disponibilidade:** Acesso garantido aos usuários legítimos quando necessário (garantido por redundância e backups).
- **Autenticidade:** Certeza da identidade do autor da mensagem/ação.
- **Não-Repúdio (Irretratabilidade):** O autor não pode negar a autoria de uma ação (garantido por assinatura digital com certificado).

- **Criptografia Simétrica vs Assimétrica:**
  - **Simétrica (Chave Secreta):** Uma única chave para cifrar e decifrar (ex: AES, DES, 3DES, RC4). Muito rápida, ideal para grandes volumes de dados. Problema: distribuição segura da chave.
  - **Assimétrica (Chave Pública):** Par de chaves matematicamente correlacionadas (ex: RSA, ECC, Diffie-Hellman). A chave pública cifra; a chave privada decifra (ou vice-versa). Mais lenta, resolve o problema de troca de chaves.

- **Assinatura Digital (O que cai em 90% das provas!):**
  1. O remetente gera um hash do documento.
  2. O remetente cifra o hash com sua **CHAVE PRIVADA**. O resultado é a assinatura digital.
  3. O destinatário decifra o hash usando a **CHAVE PÚBLICA** do remetente e confere se bate com o hash recalculado.
  - Garante: Autenticidade, Integridade e Não-Repúdio (mas NÃO garante confidencialidade por si só!).
""",
        "tabela_resumo": {
            "titulo": "Criptografia Simétrica vs Assimétrica vs Assinatura Digital",
            "colunas": ["Mecanismo", "Chave Utilizada", "Garante Principalmente", "Exemplos Frequentes"],
            "linhas": [
                ["Criptografia Simétrica", "Mesma chave secreta para cifrar e decifrar", "Confidencialidade rápida de dados", "AES (padrão de mercado), DES, 3DES, ChaCha20"],
                ["Criptografia Assimétrica", "Par de chaves: Pública (aberta) e Privada (secreta)", "Troca segura de chaves e confidencialidade", "RSA, ECC (Curvas Elípticas), Diffie-Hellman"],
                ["Função Hash", "Sem chave (algoritmo unidirecional / one-way)", "Integridade do arquivo (detecta qualquer alteração)", "SHA-256, SHA-3, MD5 (inseguro/obsoleto)"],
                ["Assinatura Digital", "Hash cifrado com a chave PRIVADA do autor", "Autenticidade, Integridade e Não-Repúdio", "Certificados Digitais padrão ICP-Brasil"],
            ]
        },
        "videoaulas": [
            {
                "titulo": "Criptografia Simétrica e Assimétrica para Concursos Públicos",
                "canal": "Gran Concursos TI",
                "duracao": "32 min",
                "youtube_id": "8Z8m_2W5qF8",
                "descricao": "Como funciona o par de chaves pública/privada e o segredo da assinatura digital explicado sem mistérios."
            },
            {
                "titulo": "OWASP Top 10 e Ataques Web (SQL Injection, XSS, CSRF)",
                "canal": "Prof. Fernando Pedrosa",
                "duracao": "26 min",
                "youtube_id": "Ofktsne-utM",
                "descricao": "Principais vulnerabilidades web cobradas pela FGV e Cebraspe em cargos de Analista de TI."
            }
        ],
        "flashcards": [
            {
                "id": "fc-seg-01",
                "frente": "Com qual chave é gerada uma Assinatura Digital autêntica?",
                "verso": "Com a CHAVE PRIVADA do remetente (aplicada sobre o resumo criptográfico / hash do documento).",
                "mnemonico": "Assina com a PRIVADA (só você tem) | Confere com a PÚBLICA (todos têm)",
                "tag": "Segurança"
            },
            {
                "id": "fc-seg-02",
                "frente": "A Assinatura Digital garante a Confidencialidade (sigilo) do documento?",
                "verso": "NÃO! A assinatura digital garante Autenticidade, Integridade e Não-Repúdio. O documento pode estar legível a qualquer um se não for também criptografado.",
                "mnemonico": "Assinatura = Quem assinou (AIN: Autenticidade, Integridade, Não-repúdio)",
                "tag": "Segurança"
            },
            {
                "id": "fc-seg-03",
                "frente": "Qual a principal vantagem da criptografia simétrica sobre a assimétrica?",
                "verso": "A velocidade de processamento e baixo consumo computacional: a criptografia simétrica é até 1.000x mais rápida para grandes volumes de dados.",
                "mnemonico": "Simétrica = Rápida e Leve | Assimétrica = Segura para trocar chaves",
                "tag": "Segurança"
            }
        ],
        "radiografia_bancas": {
            "fgv": "A FGV adora descrever um ataque de SQL Injection ou Cross-Site Scripting (XSS) e perguntar qual controle do OWASP previne (ex: validação e sanitização de inputs com prepared statements).",
            "cebraspe": "O Cebraspe afirma que a assinatura digital é feita cifrando-se o texto com a chave pública do destinatário (FALSO! É com a chave privada do remetente).",
            "quadrix": "A Quadrix cobra a associação direta entre os pilares CIDAN e suas definições conceituais.",
            "ibfc": "O IBFC costuma listar algoritmos e pedir para assinalar qual deles é um algoritmo de chave simétrica (ex: AES)."
        },
        "pontos_criticos": [
            "MD5 e SHA-1 são algoritmos de hash criptograficamente rompidos (colisões encontradas); hoje o padrão mínimo recomendado é o SHA-256.",
            "Para garantir CONFIDENCIALIDADE usando criptografia assimétrica, você cifra com a chave PÚBLICA do destinatário (só a privada dele poderá abrir).",
            "Para garantir AUTENTICIDADE/ASSINATURA, você cifra o hash com a sua chave PRIVADA (qualquer um com sua pública confere que foi você)."
        ],
        "questoes_ids": ["q-ceb-seg-01", "q-fgv-seg-01"]
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
