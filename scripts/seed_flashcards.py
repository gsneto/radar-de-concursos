"""Seeder de Flashcards de Alta Frequência para Concursos Públicos e Bancas (GSN Concursos)."""

import json
from uuid import uuid4
from datetime import datetime, timezone
import sqlite3

FLASHCARDS = [
    # --- Banco de Dados ---
    {
        "frente": "O que exige a 1ª Forma Normal (1FN) no modelo relacional?",
        "verso": "Exige que todos os atributos sejam atômicos (monovalorados e indivisíveis), eliminando grupos repetitivos, vetores e tabelas aninhadas.",
        "tags": ["banco-de-dados", "normalizacao", "ti"],
        "conceito_key": "1fn_atomicidade",
    },
    {
        "frente": "Qual a diferença essencial entre 2FN e 3FN?",
        "verso": "• 2FN: elimina dependências parciais (atributos não-chave devem depender de toda a chave primária composta).\n• 3FN: elimina dependências transitivas (nenhum atributo não-chave pode depender de outro não-chave).",
        "tags": ["banco-de-dados", "normalizacao", "ti"],
        "conceito_key": "2fn_3fn_diferenca",
    },
    {
        "frente": "Quais são as 4 propriedades ACID de uma transação em SGBDs?",
        "verso": "• Atomicidade: ou todas as operações são executadas ou nenhuma é (rollback).\n• Consistência: preserva a integridade e regras do banco.\n• Isolamento: transações concorrentes não interferem no estado uma da outra.\n• Durabilidade: após o commit, alterações sobrevivem a falhas de energia ou sistema.",
        "tags": ["banco-de-dados", "acid", "ti"],
        "conceito_key": "acid_propriedades",
    },
    {
        "frente": "O que estabelece o Teorema CAP para bancos de dados distribuídos?",
        "verso": "Afirma que um sistema distribuído só pode garantir simultaneamente 2 das 3 propriedades:\n1. Consistência (Consistency)\n2. Disponibilidade (Availability)\n3. Tolerância a Partições (Partition Tolerance). Como P é inevitável em rede, escolhe-se CP ou AP.",
        "tags": ["banco-de-dados", "nosql", "arquitetura", "ti"],
        "conceito_key": "teorema_cap",
    },
    {
        "frente": "Diferença entre comando TRUNCATE e DELETE em SQL.",
        "verso": "• DELETE: comando DML, remove linhas uma a uma, permite cláusula WHERE, gera logs de transação completos e dispara triggers.\n• TRUNCATE: comando DDL, desfaz páginas do disco, não aceita WHERE, é muito mais rápido e não dispara triggers DELETE.",
        "tags": ["banco-de-dados", "sql", "ti"],
        "conceito_key": "sql_delete_truncate",
    },

    # --- Engenharia de Software ---
    {
        "frente": "Quais são os 5 princípios SOLID da Orientação a Objetos?",
        "verso": "• S: Single Responsibility (Responsabilidade Única)\n• O: Open/Closed (Aberto para extensão, fechado para modificação)\n• L: Liskov Substitution (Subclasses substituem classes base sem quebrar o código)\n• I: Interface Segregation (Múltiplas interfaces específicas são melhores que uma geral)\n• D: Dependency Inversion (Dependa de abstrações, não de implementações concretas)",
        "tags": ["engenharia-de-software", "solid", "ti"],
        "conceito_key": "solid_principios",
    },
    {
        "frente": "Qual a diferença entre os padrões de projeto Strategy e State (GoF)?",
        "verso": "• Strategy: o cliente escolhe ou injeta qual algoritmo concreto usar (comportamento intercambiável por configuração externa).\n• State: o contexto troca seu comportamento automaticamente à medida que seu estado interno transita.",
        "tags": ["engenharia-de-software", "gof", "design-patterns", "ti"],
        "conceito_key": "gof_strategy_state",
    },
    {
        "frente": "Qual o timebox e o objetivo da reunião Daily Scrum no framework Scrum?",
        "verso": "Timebox máximo de 15 minutos. Objetivo: inspecionar o progresso da equipe em direção à Meta da Sprint (Sprint Goal) e sincronizar o plano de trabalho para as próximas 24 horas.",
        "tags": ["metodologias-ageis", "scrum", "ti"],
        "conceito_key": "scrum_daily",
    },
    {
        "frente": "Ciclo Red-Green-Refactor no TDD (Test-Driven Development).",
        "verso": "1. Red: Escreva um teste automatizado que falhe.\n2. Green: Escreva o código mínimo estritamente necessário para o teste passar.\n3. Refactor: Melhore o design, legibilidade e duplicações mantendo o teste passando.",
        "tags": ["engenharia-de-software", "tdd", "testes", "ti"],
        "conceito_key": "tdd_ciclo",
    },

    # --- Redes e Segurança da Informação ---
    {
        "frente": "Em qual camada do modelo OSI operam: Switch L2, Roteador e Firewall de Aplicação (WAF)?",
        "verso": "• Switch L2: Camada 2 (Enlace de Dados) - endereços MAC.\n• Roteador: Camada 3 (Rede) - endereços IP e roteamento.\n• WAF: Camada 7 (Aplicação) - inspeção HTTP/HTTPS e payloads.",
        "tags": ["redes", "osi", "ti"],
        "conceito_key": "osi_camadas_equipamentos",
    },
    {
        "frente": "Qual a diferença entre criptografia simétrica e assimétrica?",
        "verso": "• Simétrica (ex: AES): usa a mesma chave para cifrar e decifrar. Muito rápida, ideal para grandes volumes.\n• Assimétrica (ex: RSA, ECC): usa par de chaves (pública para cifrar, privada para decifrar). Resolve o intercâmbio seguro de chaves.",
        "tags": ["seguranca-da-informacao", "criptografia", "ti"],
        "conceito_key": "criptografia_simetrica_assimetrica",
    },
    {
        "frente": "Como funciona o Three-Way Handshake do protocolo TCP?",
        "verso": "1. Cliente envia pacote SYN (solicita conexão e envia seu ISN).\n2. Servidor responde com SYN + ACK (confirma recebimento e envia seu ISN).\n3. Cliente responde com ACK (conexão estabelecida com sucesso).",
        "tags": ["redes", "tcp", "ti"],
        "conceito_key": "tcp_three_way_handshake",
    },
    {
        "frente": "Portas padrão dos protocolos: SSH, DNS, HTTP, HTTPS e PostgreSQL.",
        "verso": "• SSH: TCP 22\n• DNS: UDP/TCP 53\n• HTTP: TCP 80\n• HTTPS: TCP 443\n• PostgreSQL: TCP 5432",
        "tags": ["redes", "portas", "ti"],
        "conceito_key": "portas_padrao_protocolos",
    },

    # --- Bancas Examinadoras & Estratégia ---
    {
        "frente": "Regra de ouro e armadilhas da banca Fundação Getulio Vargas (FGV).",
        "verso": "• Estilo: Múltipla escolha com enunciados longos e estudos de caso práticos.\n• Pegadinha: Ambiguidade sutil em Português e casos hipotéticos de concorrência em TI.\n• Estratégia: Não se apegue a decoreba; treine interpretação de contexto e gestão de tempo.",
        "tags": ["bancas", "fgv", "estrategia"],
        "conceito_key": "perfil_banca_fgv",
    },
    {
        "frente": "Regra de penalidade do Cebraspe (modelo Certo/Errado) e cálculo de risco.",
        "verso": "• Regra: 1 erro anula 1 acerto líquido (-1 ponto).\n• Estratégia: Só assinale o item se sua confiança for superior a 50%. Na dúvida completa, o valor esperado de deixar em branco (0 pontos) é superior ao chute.",
        "tags": ["bancas", "cebraspe", "estrategia"],
        "conceito_key": "perfil_banca_cebraspe",
    },

    # --- Direito Constitucional ---
    {
        "frente": "Quais são os 5 remédios constitucionais do Art. 5º da CF/88?",
        "verso": "1. Habeas Corpus: protege liberdade de locomoção.\n2. Habeas Data: assegura conhecimento/retificação de informações pessoais.\n3. Mandado de Segurança: protege direito líquido e certo contra ilegalidade/abuso de poder.\n4. Mandado de Injunção: supre falta de norma regulamentadora que inviabilize direito constitucional.\n5. Ação Popular: anula ato lesivo ao patrimônio público, moralidade ou meio ambiente.",
        "tags": ["direito-constitucional", "remedios-constitucionais"],
        "conceito_key": "remedios_constitucionais",
    },
    {
        "frente": "Quais são as Cláusulas Pétreas expressas na CF/88 (Art. 60, § 4º)?",
        "verso": "Não será objeto de deliberação proposta de emenda tendente a abolir:\nI - a forma federativa de Estado;\nII - o voto direto, secreto, universal e periódico;\nIII - a separação dos Poderes;\nIV - os direitos e garantias individuais.",
        "tags": ["direito-constitucional", "clausulas-petreas"],
        "conceito_key": "clausulas_petreas_cf88",
    },
]

def seed_flashcards(db_path="data/radar.sqlite3"):
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    try:
        cur = conn.cursor()
        for card in FLASHCARDS:
            # Verifica se já existe pelo conceito_key
            existing = cur.execute(
                "SELECT id FROM pratica_flashcards WHERE conceito_key = ?", (card["conceito_key"],)
            ).fetchone()
            if existing:
                continue
            fid = str(uuid4())
            cur.execute(
                """INSERT INTO pratica_flashcards(
                    id, disciplina_id, topico_id, contest_id, conceito_key,
                    frente, verso, tags, fonte, licenca, estado, ease, intervalo,
                    repeticoes, proxima_revisao, ultima_revisao, revisoes, created_at, updated_at
                ) VALUES (?, NULL, NULL, '', ?, ?, ?, ?, 'GSN Pedagogia', 'CC-BY-4.0', 'ativo', 2.5, 0, 0, NULL, NULL, 0, ?, ?)""",
                (
                    fid,
                    card["conceito_key"],
                    card["frente"],
                    card["verso"],
                    json.dumps(card["tags"], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            inserted += 1
        conn.commit()
        print(f"Sucesso: {inserted} flashcards inseridos com sucesso!")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_flashcards()
