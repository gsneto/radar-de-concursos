"""Catálogo central de fontes do Radar (código versionado, sem segredos).

Cada fonte declara **o que** oferece, **como** é acessada, **quanto custa** e — o mais
importante — **qual conteúdo pode ser persistido**. A permissão é por tipo de conteúdo:
metadado, URL, documento, questão, gabarito e notícia não recebem a mesma resposta.

Regras:
- permissão só é ``persistencia_permitida`` com evidência registrada (URL + data);
- termos ambíguos ou inacessíveis ⇒ ``persistencia_nao_verificada`` (persistência desabilitada);
- código MIT de um scraper **não** autoriza armazenar o conteúdo de terceiros;
- nenhum segredo é armazenado: apenas o nome da variável de ambiente.

Este módulo não faz rede. Quem consulta é o conector (`radar/connectors.py`).
"""

from __future__ import annotations

import copy
from datetime import date

CATALOG_VERSION = "sources_v1"

# Categorias de permissão (ordem de restrição crescente).
PERSISTENCIA_PERMITIDA = "persistencia_permitida"
SOMENTE_USO_TRANSITORIO = "uso_transitorio"
PERSISTENCIA_NAO_VERIFICADA = "persistencia_nao_verificada"
ACESSO_BLOQUEADO = "acesso_bloqueado"
IMPORTACAO_MANUAL_CONTROLADA = "importacao_manual_controlada"

PERMISSIONS = (PERSISTENCIA_PERMITIDA, SOMENTE_USO_TRANSITORIO,
               PERSISTENCIA_NAO_VERIFICADA, ACESSO_BLOQUEADO,
               IMPORTACAO_MANUAL_CONTROLADA)

PERMISSION_LABELS = {
    PERSISTENCIA_PERMITIDA: "Persistência permitida",
    SOMENTE_USO_TRANSITORIO: "Somente uso transitório",
    PERSISTENCIA_NAO_VERIFICADA: "Persistência não verificada",
    ACESSO_BLOQUEADO: "Acesso bloqueado",
    IMPORTACAO_MANUAL_CONTROLADA: "Importação manual controlada",
}

# Tipos de conteúdo distinguidos pela política.
CONTENT_TYPES = ("metadados", "url", "documento", "questao", "gabarito", "noticia",
                 "dado_aberto")

CATEGORIES = ("concursos", "educacional", "auxiliar")
NATURES = ("oficial", "institucional", "agregador", "comunitaria", "comercial")
ACCESS = ("api", "html", "rss", "arquivo_aberto", "portal", "importacao_manual")
STATUSES = ("habilitada", "aguardando_credencial", "aguardando_validacao_de_uso",
            "bloqueada", "nao_implementada", "desativada")


def _content(permission, *, note, license=None, evidence_url=None, verified_at=None,
             confidence="media", redistribution="nao_verificada", decision_note=None):
    return {
        "permission": permission,
        "note": note,
        "license": license,
        "evidence_url": evidence_url,
        "verified_at": verified_at,
        "confidence": confidence,
        "redistribution": redistribution,
        "decision_note": decision_note,
    }


_SOURCES = [
    # --- Fontes oficiais já integradas ------------------------------------------------
    {
        "id": "guajara",
        "name": "Prefeitura de Guajará-Mirim/RO — notícia oficial do concurso",
        "vendor": "Prefeitura de Guajará-Mirim",
        "category": "concursos",
        "nature": "oficial",
        "domains": ["guajaramirim.ro.gov.br"],
        "entry_url": "https://guajaramirim.ro.gov.br/prefeitura-de-guajara-mirim-abre-"
                     "inscricoes-para-concurso-publico-da-educacao-com-107-vagas-e-"
                     "cadastro-de-reserva/",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "Guajará-Mirim/RO", "institutional": "SEMED"},
        "content": {
            "metadados": _content(PERSISTENCIA_PERMITIDA, note="ato público municipal",
                                  license="domínio público (ato oficial)",
                                  evidence_url="https://guajaramirim.ro.gov.br/",
                                  verified_at="2026-10-17", confidence="alta"),
            "documento": _content(PERSISTENCIA_PERMITIDA, note="ato oficial publicado pelo órgão",
                                  license="domínio público (ato oficial)",
                                  evidence_url="https://guajaramirim.ro.gov.br/",
                                  verified_at="2026-10-17", confidence="alta"),
            "noticia": _content(PERSISTENCIA_NAO_VERIFICADA,
                                note="notícia institucional; não é ato normativo e a licença "
                                     "não está declarada",
                                license="não declarada",
                                evidence_url="https://guajaramirim.ro.gov.br/",
                                verified_at="2026-10-17", confidence="media"),
        },
        "display_allowed": True,
        "redistribution_allowed": False,
        "cache_policy": "revalidar a cada ciclo (6 h)",
        "min_interval_hours": 6,
        "rate_limit": {"requests_per_minute": 6},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": True},
        "credential_env": None,
        "retention": "documentos e versões preservados com hash",
        "dedup": "URL canônica + sha256 da versão",
        "terms_url": None,
        "terms_verified_at": "2026-10-17",
        "status": "habilitada",
        "connector": "guajara",
        "confidence": "alta",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Fonte base do contrato v1.",
    },
    {
        "id": "dou-secao-3",
        "name": "Diário Oficial da União — Seção 3 (Imprensa Nacional)",
        "vendor": "Imprensa Nacional",
        "category": "concursos",
        "nature": "oficial",
        "domains": ["www.in.gov.br"],
        "entry_url": "https://www.in.gov.br/leiturajornal?secao=do3",
        "docs_url": "https://www.in.gov.br/",
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "federal e demais poderes"},
        "content": {
            "metadados": _content(PERSISTENCIA_PERMITIDA, note="ato oficial federal",
                                  license="domínio público (ato oficial)",
                                  evidence_url="https://www.in.gov.br/",
                                  verified_at="2026-10-17", confidence="alta"),
            "documento": _content(PERSISTENCIA_PERMITIDA, note="ato oficial federal",
                                  license="domínio público (ato oficial)",
                                  evidence_url="https://www.in.gov.br/",
                                  verified_at="2026-10-17", confidence="alta"),
        },
        "display_allowed": True,
        "redistribution_allowed": False,
        "cache_policy": "revalidar a cada ciclo (6 h)",
        "min_interval_hours": 6,
        "rate_limit": {"requests_per_minute": 6},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": True},
        "credential_env": None,
        "retention": "documentos e versões preservados com hash",
        "dedup": "URL canônica + sha256 da versão",
        "terms_url": None,
        "terms_verified_at": "2026-10-17",
        "status": "habilitada",
        "connector": "dou",
        "confidence": "alta",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Identidade é a SEÇÃO do diário: tratada como container_fonte, não como certame.",
    },
    {
        "id": "fgv-conhecimento",
        "name": "FGV Conhecimento — catálogo de concursos",
        "vendor": "Fundação Getulio Vargas",
        "category": "concursos",
        "nature": "oficial",
        "domains": ["conhecimento.fgv.br"],
        "entry_url": "https://conhecimento.fgv.br/concursos",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "concursos organizados pela FGV"},
        "content": {
            "metadados": _content(PERSISTENCIA_PERMITIDA, note="página pública da banca",
                                  license="não declarada no site",
                                  evidence_url="https://conhecimento.fgv.br/concursos",
                                  verified_at="2026-10-17", confidence="media",
                                  decision_note="Ato oficial publicado pela própria banca; "
                                                "persistido como evidência documental, sem "
                                                "redistribuição e sem uso comercial do conteúdo."),
            "documento": _content(PERSISTENCIA_PERMITIDA,
                                  note="editais e retificações publicados pela banca",
                                  license="não declarada no site",
                                  evidence_url="https://conhecimento.fgv.br/concursos",
                                  verified_at="2026-10-17", confidence="media",
                                  decision_note="Metadado factual (título, URL, data) usado como pista de descoberta; sem redistribuição de conteúdo editorial."),
        },
        "display_allowed": True,
        "redistribution_allowed": False,
        "cache_policy": "revalidar a cada ciclo (6 h)",
        "min_interval_hours": 6,
        "rate_limit": {"requests_per_minute": 4},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": True},
        "credential_env": None,
        "retention": "documentos e versões preservados com hash",
        "dedup": "slug do concurso + URL do documento + sha256",
        "terms_url": None,
        "terms_verified_at": "2026-10-17",
        "status": "habilitada",
        "connector": "fgv",
        "confidence": "media",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Licença de conteúdo não declarada: persistência de documento é decisão de "
                 "produto registrada, não autorização expressa.",
    },
    {
        "id": "quadrix",
        "name": "Quadrix — Instituto de Desenvolvimento Educacional",
        "vendor": "Quadrix",
        "category": "concursos",
        "nature": "oficial",
        "domains": ["www.quadrix.org.br", "anexos-r2.selecao.net.br"],
        "entry_url": "https://www.quadrix.org.br/",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "concursos organizados pelo Quadrix"},
        "content": {
            "metadados": _content(PERSISTENCIA_PERMITIDA, note="página pública da banca",
                                  license="não declarada no site",
                                  evidence_url="https://www.quadrix.org.br/",
                                  verified_at="2026-10-17", confidence="media",
                                  decision_note="Ato oficial publicado pela própria banca; "
                                                "persistido como evidência documental, sem "
                                                "redistribuição."),
            "documento": _content(PERSISTENCIA_PERMITIDA, note="anexos públicos em CDN autorizado",
                                  license="não declarada no site",
                                  evidence_url="https://www.quadrix.org.br/",
                                  verified_at="2026-10-17", confidence="media",
                                  decision_note="Metadado factual (título, URL, data) usado como pista de descoberta; sem redistribuição de conteúdo editorial."),
        },
        "display_allowed": True,
        "redistribution_allowed": False,
        "cache_policy": "revalidar a cada ciclo (6 h)",
        "min_interval_hours": 6,
        "rate_limit": {"requests_per_minute": 4},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": True},
        "credential_env": None,
        "retention": "documentos e versões preservados com hash",
        "dedup": "URL do documento + sha256",
        "terms_url": None,
        "terms_verified_at": "2026-10-17",
        "status": "habilitada",
        "connector": "quadrix",
        "confidence": "media",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "www.quadrix.org.br/uploads é proibido por robots; apenas o CDN de anexos.",
    },
    {
        "id": "ibfc",
        "name": "IBFC — Instituto Brasileiro de Formação e Capacitação",
        "vendor": "IBFC",
        "category": "concursos",
        "nature": "oficial",
        "domains": ["concursos.ibfc.org.br", "anexos-r2.selecao.net.br",
                    "anexos.cdn.selecao.net.br"],
        "entry_url": "https://concursos.ibfc.org.br/index/1",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "concursos organizados pelo IBFC"},
        "content": {
            "metadados": _content(PERSISTENCIA_PERMITIDA, note="catálogo público por certame",
                                  license="não declarada no site",
                                  evidence_url="https://concursos.ibfc.org.br/",
                                  verified_at="2026-10-17", confidence="media",
                                  decision_note="Metadado factual (título, URL, data) usado como pista de descoberta; sem redistribuição de conteúdo editorial."),
            "documento": _content(PERSISTENCIA_PERMITIDA,
                                  note="anexos públicos; CDN com robots restritivo exige "
                                       "autorização explícita e tentativa normal, sem evasão",
                                  license="não declarada no site",
                                  evidence_url="https://concursos.ibfc.org.br/robots.txt",
                                  verified_at="2026-10-17", confidence="media",
                                  decision_note="Ato oficial publicado pela própria banca; "
                                                "persistido como evidência documental, sem "
                                                "redistribuição."),
        },
        "display_allowed": True,
        "redistribution_allowed": False,
        "cache_policy": "revalidar a cada ciclo (6 h)",
        "min_interval_hours": 6,
        "rate_limit": {"requests_per_minute": 4},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": True},
        "credential_env": None,
        "retention": "documentos e versões preservados com hash",
        "dedup": "ibfc-<id> + URL do documento + sha256",
        "terms_url": None,
        "terms_verified_at": "2026-10-17",
        "status": "habilitada",
        "connector": "ibfc",
        "confidence": "media",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Download de anexos do CDN é opt-in por configuração do conector.",
    },
    {
        "id": "pci",
        "name": "PCI Concursos (MCP) — agregador de descoberta",
        "vendor": "PCI Concursos",
        "category": "concursos",
        "nature": "agregador",
        "domains": ["mcp.pciconcursos.com.br", "www.pciconcursos.com.br"],
        "entry_url": "https://mcp.pciconcursos.com.br/mcp",
        "docs_url": None,
        "access": "api",
        "coverage": {"geographic": "nacional", "institutional": "agregador independente"},
        "content": {
            "metadados": _content(PERSISTENCIA_PERMITIDA,
                                  note="fatos de descoberta (título, URL, data) usados como pista",
                                  license="não declarada",
                                  evidence_url="https://www.pciconcursos.com.br/robots.txt",
                                  verified_at="2026-10-17", confidence="baixa",
                                  decision_note="Metadado factual (título, URL, data) usado como pista de descoberta; sem redistribuição de conteúdo editorial."),
            "url": _content(PERSISTENCIA_PERMITIDA, note="URL de origem como proveniência",
                            license="não declarada",
                            evidence_url="https://www.pciconcursos.com.br/robots.txt",
                            verified_at="2026-10-17", confidence="baixa",
                                  decision_note="Metadado factual (título, URL, data) usado como pista de descoberta; sem redistribuição de conteúdo editorial."),
            "noticia": _content(PERSISTENCIA_NAO_VERIFICADA,
                                note="conteúdo editorial de terceiro; termos não verificados — "
                                     "não persistir novos corpos de página",
                                license="não declarada",
                                evidence_url="https://www.pciconcursos.com.br/robots.txt",
                                verified_at="2026-10-17", confidence="baixa"),
        },
        "display_allowed": True,
        "redistribution_allowed": False,
        "cache_policy": "não cachear conteúdo editorial; metadados revalidados por ciclo",
        "min_interval_hours": 6,
        "rate_limit": {"requests_per_minute": 4},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": True},
        "credential_env": None,
        "retention": "metadados de descoberta; conteúdo editorial transitório",
        "dedup": "URL do anúncio + competition_id",
        "terms_url": None,
        "terms_verified_at": "2026-10-17",
        "status": "habilitada",
        "connector": "pci",
        "confidence": "baixa",
        "review_due": "2026-11-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Agregador nunca comprova concurso nem vaga; resultados exigem verificação "
                 "documental. Histórico anterior à política é preservado.",
    },
    # --- Agregadores catalogados, não integrados --------------------------------------
    {
        "id": "concursosnobrasil",
        "name": "Concursos no Brasil",
        "vendor": "ConcursosNoBrasil.com",
        "category": "concursos",
        "nature": "agregador",
        "domains": ["concursosnobrasil.com", "www.concursosnobrasil.com"],
        "entry_url": "https://concursosnobrasil.com/",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "agregador"},
        "content": {
            "metadados": _content(PERSISTENCIA_NAO_VERIFICADA,
                                  note="robots.txt permite; termos de uso não verificados",
                                  evidence_url="https://www.concursosnobrasil.com/robots.txt",
                                  verified_at="2026-10-17", confidence="baixa"),
            "noticia": _content(PERSISTENCIA_NAO_VERIFICADA,
                                note="conteúdo editorial de terceiro sem licença declarada",
                                evidence_url="https://www.concursosnobrasil.com/robots.txt",
                                verified_at="2026-10-17", confidence="baixa"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache persistente",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 2},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": False},
        "credential_env": None,
        "retention": "nada persistido até revisão de termos",
        "dedup": "n/a",
        "terms_url": "https://concursosnobrasil.com/",
        "terms_verified_at": None,
        "status": "aguardando_validacao_de_uso",
        "connector": None,
        "confidence": "baixa",
        "review_due": "2026-11-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Candidato de descoberta secundária. Não implementado nesta fase.",
    },
    {
        "id": "acheconcursos",
        "name": "Ache Concursos",
        "vendor": "Ache Concursos",
        "category": "concursos",
        "nature": "agregador",
        "domains": ["www.acheconcursos.com.br"],
        "entry_url": "https://www.acheconcursos.com.br/",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "agregador"},
        "content": {
            "metadados": _content(PERSISTENCIA_NAO_VERIFICADA,
                                  note="robots permite com restrições; termos não verificados",
                                  evidence_url="https://www.acheconcursos.com.br/robots.txt",
                                  verified_at="2026-10-17", confidence="baixa"),
            "noticia": _content(PERSISTENCIA_NAO_VERIFICADA,
                                note="conteúdo editorial de terceiro",
                                evidence_url="https://www.acheconcursos.com.br/robots.txt",
                                verified_at="2026-10-17", confidence="baixa"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache persistente",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 2},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": False},
        "credential_env": None,
        "retention": "nada persistido até revisão de termos",
        "dedup": "n/a",
        "terms_url": "https://www.acheconcursos.com.br/",
        "terms_verified_at": None,
        "status": "aguardando_validacao_de_uso",
        "connector": None,
        "confidence": "baixa",
        "review_due": "2026-11-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Não implementado nesta fase.",
    },
    {
        "id": "jcconcursos",
        "name": "JC Concursos (UOL)",
        "vendor": "JC Concursos / UOL",
        "category": "concursos",
        "nature": "agregador",
        "domains": ["www.jcconcursos.com.br", "jcconcursos.uol.com.br"],
        "entry_url": "https://www.jcconcursos.com.br/",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "agregador de notícias"},
        "content": {
            "metadados": _content(PERSISTENCIA_NAO_VERIFICADA,
                                  note="robots permite; termos editoriais não verificados",
                                  evidence_url="https://www.jcconcursos.com.br/robots.txt",
                                  verified_at="2026-10-17", confidence="baixa"),
            "noticia": _content(SOMENTE_USO_TRANSITORIO,
                                note="robots permite leitura; conteúdo jornalístico protegido, "
                                     "sem licença para armazenar — consulta transitória apenas",
                                license="jornalístico (não licenciado)",
                                evidence_url="https://www.jcconcursos.com.br/robots.txt",
                                verified_at="2026-10-17", confidence="media"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache persistente",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 2},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": False},
        "credential_env": None,
        "retention": "nada persistido",
        "dedup": "n/a",
        "terms_url": "https://www.jcconcursos.com.br/",
        "terms_verified_at": None,
        "status": "aguardando_validacao_de_uso",
        "connector": None,
        "confidence": "baixa",
        "review_due": "2026-11-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Notícia não comprova concurso. Não implementado nesta fase.",
    },
    # --- APIs de terceiros (código aberto, conteúdo de terceiro) ----------------------
    {
        "id": "api-concursos-vinimartinsc",
        "name": "concursosPublicosAPI (Vinimartinsc)",
        "vendor": "comunidade (GitHub)",
        "category": "concursos",
        "nature": "comunitaria",
        "domains": [],
        "entry_url": "https://github.com/Vinimartinsc/concursosPublicosAPI",
        "docs_url": "https://github.com/Vinimartinsc/concursosPublicosAPI",
        "access": "api",
        "coverage": {"geographic": "nacional", "institutional": "scraper de ConcursosNoBrasil"},
        "content": {
            "metadados": _content(PERSISTENCIA_NAO_VERIFICADA,
                                  note="MIT no código; conteúdo pertence ao agregador de origem",
                                  license="MIT (software); conteúdo: não concedido",
                                  evidence_url="https://github.com/Vinimartinsc/concursosPublicosAPI",
                                  verified_at="2026-10-17", confidence="baixa"),
            "noticia": _content(PERSISTENCIA_NAO_VERIFICADA,
                                note="o próprio autor recomenda NÃO USAR EM PRODUÇÃO",
                                license="MIT (software); conteúdo: não concedido",
                                evidence_url="https://github.com/Vinimartinsc/concursosPublicosAPI",
                                verified_at="2026-10-17", confidence="baixa"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 1},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": False},
        "credential_env": None,
        "retention": "nada persistido",
        "dedup": "n/a",
        "terms_url": "https://concursosnobrasil.com/",
        "terms_verified_at": None,
        "status": "nao_implementada",
        "connector": None,
        "confidence": "baixa",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Licença do software não autoriza armazenar conteúdo de terceiro.",
    },
    {
        "id": "concursos-api-deno",
        "name": "concursos-api-deno (Jeiel0rbit)",
        "vendor": "comunidade (GitHub)",
        "category": "concursos",
        "nature": "comunitaria",
        "domains": ["concursos-api.deno.dev"],
        "entry_url": "https://github.com/Jeiel0rbit/concursos-api-deno",
        "docs_url": "https://github.com/Jeiel0rbit/concursos-api-deno",
        "access": "api",
        "coverage": {"geographic": "nacional", "institutional": "scraper de ConcursosNoBrasil"},
        "content": {
            "metadados": _content(PERSISTENCIA_NAO_VERIFICADA,
                                  note="MIT no código; dados extraídos do ConcursosNoBrasil",
                                  license="MIT (software); conteúdo: não concedido",
                                  evidence_url="https://github.com/Jeiel0rbit/concursos-api-deno",
                                  verified_at="2026-10-17", confidence="baixa"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 1},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": False},
        "credential_env": None,
        "retention": "nada persistido",
        "dedup": "n/a",
        "terms_url": "https://concursosnobrasil.com/",
        "terms_verified_at": None,
        "status": "nao_implementada",
        "connector": None,
        "confidence": "baixa",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Endpoint público testado nesta fase respondeu 404; não usar.",
    },
    {
        "id": "api-concursos-kaua",
        "name": "api-concursos-publicos (kauafernandomelo)",
        "vendor": "comunidade (GitHub)",
        "category": "concursos",
        "nature": "comunitaria",
        "domains": [],
        "entry_url": "https://github.com/kauafernandomelo/api-concursos-publicos",
        "docs_url": "https://github.com/kauafernandomelo/api-concursos-publicos",
        "access": "api",
        "coverage": {"geographic": "nacional", "institutional": "scraper do PCI Concursos"},
        "content": {
            "metadados": _content(ACESSO_BLOQUEADO,
                                  note="repositório sem licença declarada",
                                  license="ausente",
                                  evidence_url="https://github.com/kauafernandomelo/api-concursos-publicos",
                                  verified_at="2026-10-17", confidence="alta"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 1},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": False},
        "credential_env": None,
        "retention": "nada persistido",
        "dedup": "n/a",
        "terms_url": None,
        "terms_verified_at": None,
        "status": "bloqueada",
        "connector": None,
        "confidence": "alta",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Sem licença: não reutilizar código nem dados.",
    },
    # --- Dados abertos / auxiliares ---------------------------------------------------
    {
        "id": "dados-gov-br",
        "name": "Portal Brasileiro de Dados Abertos",
        "vendor": "Governo Federal",
        "category": "auxiliar",
        "nature": "oficial",
        "domains": ["dados.gov.br"],
        "entry_url": "https://dados.gov.br/",
        "docs_url": "https://dados.gov.br/dados/api/publico/conjuntos-dados",
        "access": "api",
        "coverage": {"geographic": "nacional", "institutional": "catálogo federal de dados"},
        "content": {
            "metadados": _content(ACESSO_BLOQUEADO,
                                  note="API respondeu 401 sem credencial em 2026-10-17",
                                  license="dados abertos (a confirmar por conjunto)",
                                  evidence_url="https://dados.gov.br/dados/api/publico/conjuntos-dados",
                                  verified_at="2026-10-17", confidence="alta"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache até credencial",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 2},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": False},
        "credential_env": "RADAR_DADOS_GOV_BR_TOKEN",
        "retention": "nada persistido até credencial e licença por conjunto",
        "dedup": "id do conjunto de dados",
        "terms_url": "https://dados.gov.br/",
        "terms_verified_at": None,
        "status": "aguardando_credencial",
        "connector": None,
        "confidence": "alta",
        "review_due": "2026-11-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Credencial necessária; nenhuma conta foi criada nesta fase.",
    },
    {
        "id": "conecta-gov-br",
        "name": "Conecta gov.br — catálogo de APIs",
        "vendor": "Governo Federal",
        "category": "auxiliar",
        "nature": "oficial",
        "domains": ["www.gov.br"],
        "entry_url": "https://www.gov.br/conecta/catalogo/apis",
        "docs_url": "https://www.gov.br/conecta/catalogo/apis",
        "access": "portal",
        "coverage": {"geographic": "nacional", "institutional": "catálogo de APIs públicas"},
        "content": {
            "metadados": _content(PERSISTENCIA_NAO_VERIFICADA,
                                  note="catálogo HTML; APIs exigem cadastro por serviço",
                                  license="não declarada por serviço",
                                  evidence_url="https://www.gov.br/conecta/catalogo/apis",
                                  verified_at="2026-10-17", confidence="media"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache",
        "min_interval_hours": 168,
        "rate_limit": {"requests_per_minute": 1},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": False},
        "credential_env": None,
        "retention": "nada persistido",
        "dedup": "n/a",
        "terms_url": "https://www.gov.br/conecta/",
        "terms_verified_at": None,
        "status": "aguardando_validacao_de_uso",
        "connector": None,
        "confidence": "media",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Cada API do catálogo tem termos próprios; integração é por serviço.",
    },
    {
        "id": "ibge-localidades",
        "name": "IBGE — Localidades (municípios e UFs)",
        "vendor": "IBGE",
        "category": "auxiliar",
        "nature": "oficial",
        "domains": ["servicodados.ibge.gov.br"],
        "entry_url": "https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
        "docs_url": "https://servicodados.ibge.gov.br/api/docs/localidades",
        "access": "api",
        "coverage": {"geographic": "nacional (5571 municípios)", "institutional": "IBGE"},
        "content": {
            "metadados": _content(PERSISTENCIA_PERMITIDA,
                                  note="dados abertos oficiais do IBGE; API sem credencial",
                                  license="dados abertos governamentais",
                                  evidence_url="https://servicodados.ibge.gov.br/api/docs/localidades",
                                  verified_at="2026-10-17", confidence="alta"),
            "dado_aberto": _content(PERSISTENCIA_PERMITIDA,
                                    note="lista oficial de municípios/UFs para validar local",
                                    license="dados abertos governamentais",
                                    evidence_url="https://servicodados.ibge.gov.br/api/docs/localidades",
                                    verified_at="2026-10-17", confidence="alta"),
        },
        "display_allowed": True,
        "redistribution_allowed": False,
        "cache_policy": "snapshot local com validade de 30 dias",
        "min_interval_hours": 720,
        "rate_limit": {"requests_per_minute": 2},
        "monthly_limit": None,
        "cost": {"amount": 0, "currency": "BRL", "unit": "requisicao", "verified": True},
        "credential_env": None,
        "retention": "snapshot de municípios/UFs; sem dados pessoais",
        "dedup": "código IBGE do município",
        "terms_url": "https://servicodados.ibge.gov.br/api/docs",
        "terms_verified_at": "2026-10-17",
        "status": "habilitada",
        "connector": "ibge-localidades",
        "confidence": "alta",
        "review_due": "2027-04-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Fonte auxiliar: valida local de prova; nunca confirma campo sozinha.",
    },
    # --- Educacional ----------------------------------------------------------------
    {
        "id": "quest-api",
        "name": "Quest API — banco de questões (comercial)",
        "vendor": "Quest API",
        "category": "educacional",
        "nature": "comercial",
        "domains": ["github.com"],
        "entry_url": "https://github.com/gontijogabriel/Quest-API",
        "docs_url": "https://github.com/gontijogabriel/Quest-API",
        "access": "api",
        "coverage": {"geographic": "nacional", "institutional": "provas, questões e gabaritos"},
        "content": {
            "questao": _content(ACESSO_BLOQUEADO,
                                note="API B2B com assinatura e API key; sem licença de conteúdo",
                                license="comercial (não declarada)",
                                evidence_url="https://github.com/gontijogabriel/Quest-API",
                                verified_at="2026-10-17", confidence="alta"),
            "gabarito": _content(ACESSO_BLOQUEADO,
                                 note="idem: requer contrato e credencial",
                                 license="comercial (não declarada)",
                                 evidence_url="https://github.com/gontijogabriel/Quest-API",
                                 verified_at="2026-10-17", confidence="alta"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 1},
        "monthly_limit": None,
        "cost": {"amount": None, "currency": "BRL", "unit": "assinatura", "verified": False},
        "credential_env": "RADAR_QUEST_API_KEY",
        "retention": "nada persistido",
        "dedup": "n/a",
        "terms_url": "https://github.com/gontijogabriel/Quest-API",
        "terms_verified_at": None,
        "status": "bloqueada",
        "connector": None,
        "confidence": "alta",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Código privado, sem licença; nenhuma assinatura foi contratada.",
    },
    {
        "id": "qconcursos",
        "name": "Qconcursos",
        "vendor": "Qconcursos",
        "category": "educacional",
        "nature": "comercial",
        "domains": ["www.qconcursos.com"],
        "entry_url": "https://www.qconcursos.com/",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "banco de questões"},
        "content": {
            "questao": _content(ACESSO_BLOQUEADO,
                                note="robots.txt respondeu 403 em 2026-10-17; conteúdo pago",
                                license="comercial",
                                evidence_url="https://www.qconcursos.com/robots.txt",
                                verified_at="2026-10-17", confidence="alta"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 1},
        "monthly_limit": None,
        "cost": {"amount": None, "currency": "BRL", "unit": "assinatura", "verified": False},
        "credential_env": None,
        "retention": "nada persistido",
        "dedup": "n/a",
        "terms_url": "https://www.qconcursos.com/",
        "terms_verified_at": None,
        "status": "bloqueada",
        "connector": None,
        "confidence": "alta",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Não implementado; sem autorização de acesso nem de conteúdo.",
    },
    {
        "id": "questoesdeconcursos",
        "name": "Questões de Concursos",
        "vendor": "Questões de Concursos",
        "category": "educacional",
        "nature": "comercial",
        "domains": ["www.questoesdeconcursos.com.br"],
        "entry_url": "https://www.questoesdeconcursos.com.br/",
        "docs_url": None,
        "access": "html",
        "coverage": {"geographic": "nacional", "institutional": "banco de questões"},
        "content": {
            "questao": _content(ACESSO_BLOQUEADO,
                                note="robots.txt respondeu 403 em 2026-10-17",
                                license="comercial",
                                evidence_url="https://www.questoesdeconcursos.com.br/robots.txt",
                                verified_at="2026-10-17", confidence="alta"),
        },
        "display_allowed": False,
        "redistribution_allowed": False,
        "cache_policy": "sem cache",
        "min_interval_hours": 24,
        "rate_limit": {"requests_per_minute": 1},
        "monthly_limit": None,
        "cost": {"amount": None, "currency": "BRL", "unit": "assinatura", "verified": False},
        "credential_env": None,
        "retention": "nada persistido",
        "dedup": "n/a",
        "terms_url": "https://www.questoesdeconcursos.com.br/",
        "terms_verified_at": None,
        "status": "bloqueada",
        "connector": None,
        "confidence": "alta",
        "review_due": "2027-01-17",
        "review_owner": "operador local (CLI fontes-revisar)",
        "notes": "Não implementado; sem autorização de acesso nem de conteúdo.",
    },
]

REQUIRED_FIELDS = ("id", "name", "vendor", "category", "nature", "domains", "entry_url",
                   "access", "coverage", "content", "display_allowed", "cache_policy",
                   "min_interval_hours", "rate_limit", "cost", "credential_env", "retention",
                   "dedup", "terms_url", "terms_verified_at", "status", "connector",
                   "confidence", "review_due", "review_owner")


def catalog() -> list[dict]:
    """Cópia profunda do catálogo (mutação do chamador não altera a política global)."""
    return [copy.deepcopy(source) for source in _SOURCES]


def source_ids() -> list[str]:
    return [source["id"] for source in _SOURCES]


def get_source(source_id: str) -> dict:
    for source in _SOURCES:
        if source["id"] == source_id:
            return copy.deepcopy(source)
    raise KeyError(source_id)


def permission_for(source_id: str, content_type: str) -> str:
    source = get_source(source_id)
    content = source["content"].get(content_type)
    if content is None:
        return ACESSO_BLOQUEADO
    return content["permission"]


def can_persist(source_id: str, content_type: str) -> bool:
    """Compatibilidade: delega à política (que considera o estado da fonte)."""
    from radar import source_policy
    return source_policy.can_persist(source_id, content_type)


def validate_catalog() -> list[str]:
    """Valida o catálogo: campos obrigatórios e honestidade das permissões."""
    errors = []
    seen = set()
    for source in _SOURCES:
        sid = source.get("id")
        if not sid:
            errors.append("fonte sem id")
            continue
        if sid in seen:
            errors.append(f"id duplicado: {sid}")
        seen.add(sid)
        for field in REQUIRED_FIELDS:
            if field not in source:
                errors.append(f"{sid}: campo obrigatório ausente: {field}")
        if source.get("category") not in CATEGORIES:
            errors.append(f"{sid}: categoria inválida")
        if source.get("nature") not in NATURES:
            errors.append(f"{sid}: natureza inválida")
        if source.get("access") not in ACCESS:
            errors.append(f"{sid}: tipo de acesso inválido")
        if source.get("status") not in STATUSES:
            errors.append(f"{sid}: estado inválido")
        content = source.get("content") or {}
        if not content:
            errors.append(f"{sid}: sem tipos de conteúdo")
        for ctype, entry in content.items():
            if ctype not in CONTENT_TYPES:
                errors.append(f"{sid}: tipo de conteúdo desconhecido: {ctype}")
            if entry.get("permission") not in PERMISSIONS:
                errors.append(f"{sid}/{ctype}: permissão inválida")
            if entry["permission"] == PERSISTENCIA_PERMITIDA:
                if not entry.get("evidence_url") or not entry.get("verified_at"):
                    errors.append(f"{sid}/{ctype}: persistência sem evidência verificada")
                license_text = (entry.get("license") or "").lower()
                if "não declarada" in license_text and not entry.get("decision_note"):
                    errors.append(f"{sid}/{ctype}: licença não declarada exige "
                                  f"decision_note explícita")
                if entry.get("confidence") not in ("alta", "media", "baixa"):
                    errors.append(f"{sid}/{ctype}: confiança inválida")
        if source.get("status") == "habilitada" and not source.get("connector"):
            errors.append(f"{sid}: habilitada sem conector")
        if source.get("credential_env") and "=" in str(source["credential_env"]):
            errors.append(f"{sid}: credential_env não pode conter valor")
        due = source.get("review_due")
        if due:
            try:
                date.fromisoformat(due)
            except (TypeError, ValueError):
                errors.append(f"{sid}: review_due inválida")
    return errors


def review_due_sources(today: str | None = None) -> list[str]:
    """Fontes cuja revisão de política venceu (ou vence hoje)."""
    reference = date.fromisoformat(today) if today else date.today()
    due = []
    for source in _SOURCES:
        try:
            if date.fromisoformat(source["review_due"]) <= reference:
                due.append(source["id"])
        except (TypeError, ValueError):
            due.append(source["id"])
    return sorted(due)


def summary() -> dict:
    by_status = {}
    by_category = {}
    for source in _SOURCES:
        by_status[source["status"]] = by_status.get(source["status"], 0) + 1
        by_category[source["category"]] = by_category.get(source["category"], 0) + 1
    return {"version": CATALOG_VERSION, "total": len(_SOURCES),
            "por_estado": by_status, "por_categoria": by_category,
            "revisao_vencida": review_due_sources()}
