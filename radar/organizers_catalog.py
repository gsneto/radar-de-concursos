"""Catálogo canônico de Organizadoras (Bancas Examinadoras, IFs, Universidades e Fundações).

Unifica a lista alfabética completa de ~350 organizadoras públicas brasileiras, reconciliando
variações de nomes/siglas (ex.: CESPE -> Cebraspe, FGV Conhecimento -> FGV) e cruzando contagens
reais de concursos monitorados, provas anteriores catalogadas e questões ativas no banco.
"""

from __future__ import annotations

import json
import re
import unicodedata
from contextlib import closing

from radar.document_store import connect_documents

# Lista canônica (slug PCI, Nome de Exibição) — cobertura integral A–Z.
_RAW_ORGANIZERS: tuple[tuple[str, str], ...] = (
    ("a-s-instituto", "A.S. Instituto"),
    ("abcp", "ABCP"),
    ("acep", "ACEP"),
    ("acesse-concursos", "Acesse Concursos"),
    ("actio-assessoria", "ACTIO ASSESSORIA"),
    ("activa-assessoria", "Activa Assessoria"),
    ("adm-tec", "ADM&TEC"),
    ("aeronautica-do-brasil", "Aeronáutica do Brasil"),
    ("agata", "Ágata"),
    ("agirh", "Agirh"),
    ("agrobase", "Agrobase"),
    ("ajuri", "AJURI"),
    ("amauc", "Amauc"),
    ("ambasp", "Ambasp"),
    ("ameosc", "AMEOSC"),
    ("amiga-publica", "Amiga Pública"),
    ("amma", "AMMA"),
    ("amplasc", "AMPLASC"),
    ("aocp", "AOCP"),
    ("apice", "Ápice"),
    ("aplicativa", "Aplicativa"),
    ("aplicativa-assessoria", "Aplicativa Assessoria"),
    ("apta", "Apta"),
    ("assconpp", "ASSCONPP"),
    ("assepublica", "AssePublica"),
    ("assertcon", "Assertcon"),
    ("astral", "Astral"),
    ("atena-assessoria-educacional", "Atena Assessoria Educacional"),
    ("auctor-consultoria", "Auctor Consultoria"),
    ("avanca-sp", "Avança SP"),
    ("cabral-oliveira", "Cabral & Oliveira"),
    ("caip-imes", "CAIP/IMES"),
    ("cebraspe", "Cebraspe"),
    ("cefet-mg", "CEFET/MG"),
    ("cefet-rj", "CEFET/RJ"),
    ("cemat", "CEMAT"),
    ("centro-paula-souza", "Centro Paula Souza"),
    ("ceperj", "CEPERJ"),
    ("ceps-ufpa", "Ceps/UFPA"),
    ("cepuerj", "Cepuerj"),
    ("cesgranrio", "Cesgranrio"),
    ("cespe", "CESPE"),
    ("cetam", "CETAM"),
    ("cetap", "CETAP"),
    ("cetrede", "CETREDE"),
    ("cetro", "Cetro"),
    ("ciee", "CIEE"),
    ("cmm-concursos", "CMM Concursos"),
    ("colegio-pedro-ii", "Colégio Pedro II"),
    ("comperve-ufrn", "Comperve/UFRN"),
    ("concepcao", "Concepção"),
    ("coned", "Coned"),
    ("conscam", "CONSCAM"),
    ("consep", "Consep"),
    ("consesp", "Consesp"),
    ("consis-consultoria", "CONSIS Consultoria"),
    ("consulpam", "Consulpam"),
    ("consulplan", "Consulplan"),
    ("consultar", "Consultar"),
    ("consultec", "Consultec"),
    ("coperve-ufpb", "Coperve/UFPB"),
    ("copese-ufpi", "Copese/UFPI"),
    ("copese-uft", "Copese/UFT"),
    ("copeve-ufal", "Copeve/UFAL"),
    ("cops-uel", "Cops/UEL"),
    ("coseac-uff", "Coseac/UFF"),
    ("cs-ufg", "CS/UFG"),
    ("csc-consultoria", "CSC Consultoria"),
    ("dedalus-concursos", "Dédalus Concursos"),
    ("directa", "Directa"),
    ("drh-uem", "DRH/UEM"),
    ("drh-ufrr", "DRH/UFRR"),
    ("ecap-consultoria", "Ecap Consultoria"),
    ("educa", "Educa"),
    ("elo-assessoria", "Elo Assessoria"),
    ("epl-concursos", "EPL Concursos"),
    ("epts", "EPTS"),
    ("escola-de-formacao-de-lideres-ltda-me-escolideres", "Escola de Formação de Líderes Ltda - ME (Escolíderes)"),
    ("etica-concursos", "Ética Concursos"),
    ("eupa", "EUPA"),
    ("exame", "Exame"),
    ("exatus", "Exatus"),
    ("exitus-concursos", "Exitus Concursos"),
    ("facape", "Facape"),
    ("facepe", "Facepe"),
    ("faculdade-alfa-umuarama", "Faculdade Alfa Umuarama"),
    ("fadesp", "Fadesp"),
    ("fadurpe", "Fadurpe"),
    ("faepesul", "Faepesul"),
    ("fafipa", "FAFIPA"),
    ("fama-consultoria", "Fama Consultoria"),
    ("famema", "FAMEMA"),
    ("fapec", "FAPEC"),
    ("fapetec", "Fapetec"),
    ("fau-fundacao-de-apoio-ao-desenvolvimento-unicentro", "FAU - Fundação de Apoio ao Desenvolvimento Unicentro"),
    ("fauel", "FAUEL"),
    ("faurgs", "FAURGS"),
    ("fcc", "FCC"),
    ("fcja", "FCJA"),
    ("febave-unibave-federacao-educacional-barriga-verde", "Febave/ Unibave Federação Educacional Barriga Verde"),
    ("fecilcam", "FECILCAM"),
    ("fenix-concursos", "Fenix Concursos"),
    ("fepese", "Fepese"),
    ("fesg-concursos", "FESG Concursos"),
    ("fgpa", "FGPA"),
    ("fgr", "FGR"),
    ("fgv", "FGV"),
    ("fr-gestao-publica", "FR Gestão Pública"),
    ("fronte-concursos-e-projetos", "Fronte Concursos e Projetos"),
    ("fucap", "FUCAP"),
    ("fumarc", "FUMARC"),
    ("funcefet", "FUNCEFET"),
    ("funcern", "FUNCERN"),
    ("fundacao-adm", "Fundação ADM"),
    ("fundacao-aroeira", "Fundação Aroeira"),
    ("fundacao-cajuina", "Fundação Cajuína"),
    ("fundacao-cefetbahia", "Fundação CEFETBAHIA"),
    ("fundacao-cefetminas", "Fundação CefetMinas"),
    ("fundacao-dom-cintra", "Fundação Dom Cintra"),
    ("fundacao-fat", "Fundação FAT"),
    ("fundacao-la-salle", "Fundação La Salle"),
    ("fundacao-sousandrade", "Fundação Sousândrade"),
    ("fundacao-universidade-do-oeste-de-santa-catarina", "Fundação Universidade do Oeste de Santa Catarina"),
    ("fundacao-universidade-do-tocantins", "Fundação Universidade do Tocantins"),
    ("fundape", "Fundape"),
    ("fundatec", "Fundatec"),
    ("funepu", "FUNEPU"),
    ("funrio", "FUNRIO"),
    ("funtef-cp", "FUNTEF-CP"),
    ("funvapi", "FUNVAPI"),
    ("furb", "FURB"),
    ("furg", "FURG"),
    ("gabriel-excelencia", "Gabriel Excelência"),
    ("gama-consultoria", "Gama Consultoria"),
    ("ganzaroli", "Ganzaroli"),
    ("gazzinelli", "Gazzinelli"),
    ("gestao-concurso", "Gestão Concurso"),
    ("gestao-de-concursos", "Gestão de Concursos"),
    ("gl-consultoria", "GL Consultoria"),
    ("gsa", "GSA"),
    ("gualimp", "Gualimp"),
    ("hc-assessoria", "HC Assessoria"),
    ("hospital-das-clinicas", "Hospital das Clínicas"),
    ("iade", "IADE"),
    ("iades", "Iades"),
    ("ian-instituto-de-avaliacao-nacional", "IAN - Instituto de Avaliação Nacional"),
    ("ibade", "IBADE"),
    ("ibam", "IBAM"),
    ("ibam-sp", "IBAM-SP"),
    ("ibap-rj", "IBAP-RJ"),
    ("ibdo", "IBDO"),
    ("ibfc", "IBFC"),
    ("ibgp-instituto-brasileiro-de-gestao-e-pesquisa", "IBGP - Instituto Brasileiro de Gestão e Pesquisa"),
    ("icap", "ICAP"),
    ("idecan", "Idecan"),
    ("idesc", "IDESC"),
    ("idhtec", "IDHTec"),
    ("idib", "IDIB"),
    ("idrh-concursos", "IDRH Concursos"),
    ("iep", "IEP"),
    ("ieses", "IESES"),
    ("if-sudeste-de-mg", "IF Sudeste de MG"),
    ("ifac", "IFAC"),
    ("ifam", "IFAM"),
    ("ifbaiano", "IFBaiano"),
    ("ifc", "IFC"),
    ("ifce", "IFCE"),
    ("ifes", "IFES"),
    ("iff", "IFF"),
    ("iffarroupilha", "IFFarroupilha"),
    ("ifg", "IFG"),
    ("ifgoiano", "IFGoiano"),
    ("ifmg", "IFMG"),
    ("ifms", "IFMS"),
    ("ifmt", "IFMT"),
    ("ifnmg", "IFNMG"),
    ("ifpa", "IFPA"),
    ("ifpb", "IFPB"),
    ("ifpe", "IFPE"),
    ("ifpr", "IFPR"),
    ("ifrj", "IFRJ"),
    ("ifrn", "IFRN"),
    ("ifro", "IFRO"),
    ("ifrr", "IFRR"),
    ("ifrs", "IFRS"),
    ("ifs", "IFS"),
    ("ifsc", "IFSC"),
    ("ifsertao", "IFSERTÃO"),
    ("ifsp", "IFSP"),
    ("ifsul", "IFSul"),
    ("ifsuldeminas", "IFSULDEMINAS"),
    ("iftm", "IFTM"),
    ("ifto", "IFTO"),
    ("igdrh", "IGDRH"),
    ("imais", "IMais"),
    ("imam", "IMAM"),
    ("imparh", "IMPARH"),
    ("imperio-concursos", "Império Concursos"),
    ("inaz-do-para", "Inaz do Pará"),
    ("indepac", "INDEPAC"),
    ("informacon3", "Informacon3"),
    ("informatica-e-concursos-ltda-infocol", "Informática e Concursos LTDA - Infocol"),
    ("inqc-instituto-nacional-de-qualificacao-e-capacitacao", "INQC - Instituto Nacional de Qualificação e Capacitação"),
    ("instituto-abare-ete", "Instituto Abaré-eté"),
    ("instituto-access", "Instituto Access"),
    ("instituto-acesso", "Instituto Acesso"),
    ("instituto-aocp", "Instituto AOCP"),
    ("instituto-atame", "Instituto Atame"),
    ("instituto-brasil", "Instituto Brasil"),
    ("instituto-brio", "Instituto Brio"),
    ("instituto-consulplan", "Instituto Consulplan"),
    ("instituto-dom", "Instituto DOM"),
    ("instituto-ideap", "Instituto IDEAP"),
    ("instituto-indec", "Instituto INDEC"),
    ("instituto-jk", "Instituto JK"),
    ("instituto-legatus", "Instituto Legatus"),
    ("instituto-nosso-rumo", "Instituto Nosso Rumo"),
    ("instituto-quadrix", "Instituto Quadrix"),
    ("instituto-sustente", "Instituto Sustente"),
    ("integri-brasil", "Integri Brasil"),
    ("ipefae", "IPEFAE"),
    ("ippec-instituto-de-pesquisas-pos-graduacao-e-ensino-de-cascavel", "IPPEC - Instituto de Pesquisas, Pós-Graduação e Ensino de Cascavel"),
    ("ismam", "ISMAM"),
    ("itame", "Itame"),
    ("itec", "ITEC"),
    ("ivin", "IVIN"),
    ("jcm-concursos", "JCM Concursos"),
    ("jms", "JMS"),
    ("klc-concursos", "KLC Concursos"),
    ("l-j-assessoria-e-planejamento-administrativo-ltda-epp", "L.J. Assessoria e Planejamento Administrativo Ltda - EPP"),
    ("legalle-concursos", "Legalle Concursos"),
    ("lider-consultoria-e-assessoria", "Lider Consultoria e Assessoria"),
    ("lj-concursos", "LJ Concursos"),
    ("marinha-do-brasil", "Marinha do Brasil"),
    ("maxima", "Máxima"),
    ("metrocapital", "Metrocapital"),
    ("ms-concursos-ltda", "MS Concursos LTDA"),
    ("msconcursos", "MSConcursos"),
    ("msm-consultoria", "MSM Consultoria"),
    ("nc-ufpr", "NC/UFPR"),
    ("nce-ufrj", "NCE/UFRJ"),
    ("ncp", "NCP"),
    ("neteduc", "NetEduc"),
    ("nnai", "NNAI"),
    ("norte-tecnologia", "Norte Tecnologia"),
    ("nubes", "Nubes"),
    ("nucepe-uespi", "Nucepe/UESPI"),
    ("objetiva-concurso", "Objetiva Concurso"),
    ("objetiva-concursos", "Objetiva Concursos"),
    ("om-consultoria", "OM Consultoria"),
    ("omni-concursos", "Omni Concursos"),
    ("oppus", "Oppus"),
    ("organizacao-paulista", "Organização Paulista"),
    ("paqtcpb", "PaqTcPB"),
    ("para-concursos", "Pará Concursos"),
    ("planejar", "Planejar"),
    ("planexcon", "Planexcon"),
    ("premier", "Premier"),
    ("prime-concursos", "Prime Concursos"),
    ("proconsult", "Proconsult"),
    ("promun", "Promun"),
    ("ps-concursos", "PS Concursos"),
    ("publica-concursos", "Pública Concursos"),
    ("publiconsult", "Publiconsult"),
    ("puc-pr", "PUC-PR"),
    ("qualicon", "Qualicon"),
    ("rbo-concursos", "RBO Concursos"),
    ("recrutamento-brasil", "Recrutamento Brasil"),
    ("reis-reis-auditores", "Reis & Reis Auditores"),
    ("sead-ap", "SEAD-AP"),
    ("seap", "SEAP"),
    ("selecon", "SELECON"),
    ("ses-pe", "SES/PE"),
    ("shdias", "SHDias"),
    ("sigma", "Sigma"),
    ("sigma-assessoria", "Sigma Assessoria"),
    ("sigma-consultoria", "Sigma Consultoria"),
    ("sigma-rh", "Sigma RH"),
    ("sismeta", "Sismeta"),
    ("sistema-acafe", "Sistema Acafe"),
    ("sr-concursos", "SR Concursos"),
    ("sr-digitalizacoes", "SR Digitalizações"),
    ("status-consultoria", "Status Consultoria"),
    ("super-estagios", "Super Estágios"),
    ("tribunal-de-justica-go", "Tribunal de Justiça - GO"),
    ("tsr-concursos", "TSR Concursos"),
    ("udesc", "UDESC"),
    ("uea", "UEA"),
    ("uece", "UECE"),
    ("ueg", "UEG"),
    ("uel", "UEL"),
    ("uema", "UEMA"),
    ("uems", "UEMS"),
    ("uenp", "UENP"),
    ("uepb", "UEPB"),
    ("uepg", "UEPG"),
    ("uergs", "UERGS"),
    ("uerj", "UERJ"),
    ("uerr", "UERR"),
    ("uesb", "UESB"),
    ("uesc", "UESC"),
    ("uespi", "UESPI"),
    ("ufabc", "UFABC"),
    ("ufac", "UFAC"),
    ("ufal", "UFAL"),
    ("ufba", "UFBA"),
    ("ufc", "UFC"),
    ("ufca", "UFCA"),
    ("ufcg", "UFCG"),
    ("ufcspa", "UFCSPA"),
    ("ufes", "UFES"),
    ("uff", "UFF"),
    ("uffs", "UFFS"),
    ("ufg", "UFG"),
    ("ufgd", "UFGD"),
    ("ufjf", "UFJF"),
    ("ufla", "UFLA"),
    ("ufma", "UFMA"),
    ("ufmg", "UFMG"),
    ("ufms", "UFMS"),
    ("ufmt", "UFMT"),
    ("ufop", "UFOP"),
    ("ufopa", "UFOPA"),
    ("ufpb", "UFPB"),
    ("ufpe", "UFPE"),
    ("ufpel", "UFPEL"),
    ("ufpr", "UFPR"),
    ("ufra", "UFRA"),
    ("ufrb", "UFRB"),
    ("ufrgs", "UFRGS"),
    ("ufrn", "UFRN"),
    ("ufrpe", "UFRPE"),
    ("ufrrj", "UFRRJ"),
    ("ufs", "UFS"),
    ("ufsc", "UFSC"),
    ("ufscar", "UFSCar"),
    ("ufsj", "UFSJ"),
    ("uftm", "UFTM"),
    ("ufu", "UFU"),
    ("ufv", "UFV"),
    ("ufvjm", "UFVJM"),
    ("unc", "UnC"),
    ("uneb", "UNEB"),
    ("unemat", "UNEMAT"),
    ("unesc", "UNESC"),
    ("unesp", "UNESP"),
    ("unespar", "UNESPAR"),
    ("unicamp", "UNICAMP"),
    ("unicentro", "UNICENTRO"),
    ("unifal", "UNIFAL"),
    ("unifap", "UNIFAP"),
    ("unifei", "UNIFEI"),
    ("unifesp", "UNIFESP"),
    ("unifesspa", "UNIFESSPA"),
    ("unifimes", "Unifimes"),
    ("unila", "UNILA"),
    ("unilab", "UNILAB"),
    ("unimontes", "UNIMONTES"),
    ("unioeste", "Unioeste"),
    ("unipampa", "UNIPAMPA"),
    ("unir", "UNIR"),
    ("unirg", "UNIRG"),
    ("unirio", "UNIRIO"),
    ("unisc", "UNISC"),
    ("unitau", "Unitau"),
    ("univali", "UNIVALI"),
    ("univasf", "UNIVASF"),
    ("universidade-estadual-vale-do-acarau", "Universidade Estadual Vale do Acaraú"),
    ("univesp", "UNIVESP"),
    ("upa", "UPA"),
    ("upe", "UPE"),
    ("upenet", "UPENET"),
    ("urca", "URCA"),
    ("uri-concursos", "URI Concursos"),
    ("uri-servicos", "URI Serviços"),
    ("usp", "USP"),
    ("utfpr", "UTFPR"),
    ("uva", "UVA"),
    ("vunesp", "Vunesp"),
    ("w2-auditoria-e-consultoria", "W2 Auditoria e Consultoria"),
    ("we-do-concursos", "WE DO Concursos"),
    ("zambini", "Zambini"),
)

# Vínculo entre slugs da lista e os 16 perfis estratégicos profundos de `lesson_plan.py`.
_RAIO_X_MAP: dict[str, str] = {
    "fgv": "fgv",
    "cebraspe": "cebraspe",
    "cespe": "cebraspe",
    "fcc": "fcc",
    "cesgranrio": "cesgranrio",
    "vunesp": "vunesp",
    "instituto-quadrix": "quadrix",
    "ibfc": "ibfc",
    "fepese": "fepese",
    "fundatec": "fundatec",
    "ibam": "ibam",
    "ibam-sp": "ibam",
    "idib": "idib",
    "consesp": "consesp",
    "legalle-concursos": "legalle",
    "consulpam": "consulpam",
}

_NATIONAL_SLUGS = {
    "fgv", "cebraspe", "cespe", "fcc", "cesgranrio", "vunesp", "instituto-quadrix",
    "ibfc", "aocp", "instituto-aocp", "idecan", "consulplan", "instituto-consulplan",
    "ibade", "iades", "idib", "ibam", "fundatec", "fepese", "fumarc", "selecon",
    "consulpam", "instituto-access", "instituto-acesso", "instituto-nosso-rumo",
    "ibgp-instituto-brasileiro-de-gestao-e-pesquisa", "avanca-sp", "rbo-concursos",
    "marinha-do-brasil", "aeronautica-do-brasil", "ciee",
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    "cespe": "cebraspe",
    "cespe unb": "cebraspe",
    "centro brasileiro de pesquisa em avaliacao e selecao": "cebraspe",
    "fgv conhecimento": "fgv",
    "fundacao getulio vargas": "fgv",
    "fundacao getulio vargas fgv": "fgv",
    "fundacao carlos chagas": "fcc",
    "fundacao carlos chagas fcc": "fcc",
    "fundacao cesgranrio": "cesgranrio",
    "fundacao vunesp": "vunesp",
    "quadrix": "instituto-quadrix",
    "instituto quadrix": "instituto-quadrix",
    "instituto brasileiro de formacao e capacitacao": "ibfc",
    "legalle": "legalle-concursos",
    "instituto consulpam": "consulpam",
}


def _norm(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).split())


def _classify_group(slug: str, nome: str) -> str:
    if slug in _NATIONAL_SLUGS:
        return "nacional"
    upper = nome.upper()
    if (
        slug.startswith(("if", "uf", "ue", "uni", "cefet", "utfpr", "usp", "furg", "furb"))
        or any(
            token in upper
            for token in (
                "UNIVERSIDADE", "FACULDADE", "COLÉGIO PEDRO II", "COMPERVE",
                "COPERVE", "COPESE", "COPEVE", "NC/UFPR", "NCE/UFRJ", "CS/UFG",
                "CEPS/UFPA", "CEPUERJ", "COSEAC/UFF", "NUCEPE", "FADESP", "FAURGS",
                "FAUEL", "FACEPE", "FACAPE",
            )
        )
    ):
        return "federal_if_uf"
    return "regional_municipal"


_NORM_INDEX: dict[str, str] = {}
for _slug, _name in _RAW_ORGANIZERS:
    _NORM_INDEX[_norm(_slug)] = _slug
    _NORM_INDEX[_norm(_name)] = _slug
for _alias, _target in _ALIAS_TO_CANONICAL.items():
    _NORM_INDEX[_norm(_alias)] = _target


def resolve_organizer_slug(raw_name: str | None) -> str | None:
    """Converte nome/sigla livre de banca para o `slug` canônico sem duplicar aliases."""
    key = _norm(raw_name)
    if not key:
        return None
    if key in _NORM_INDEX:
        resolved = _NORM_INDEX[key]
        return "cebraspe" if resolved == "cespe" else resolved
    for token in (
        ("cebraspe", "cebraspe"),
        ("cespe", "cebraspe"),
        ("fgv", "fgv"),
        ("getulio vargas", "fgv"),
        ("carlos chagas", "fcc"),
        ("fcc", "fcc"),
        ("cesgranrio", "cesgranrio"),
        ("vunesp", "vunesp"),
        ("quadrix", "instituto-quadrix"),
        ("ibfc", "ibfc"),
        ("aocp", "instituto-aocp"),
        ("idecan", "idecan"),
        ("consulplan", "instituto-consulplan"),
        ("fundatec", "fundatec"),
        ("fepese", "fepese"),
        ("ibam", "ibam"),
        ("idib", "idib"),
        ("consulpam", "consulpam"),
        ("selecon", "selecon"),
        ("ibade", "ibade"),
        ("iades", "iades"),
        ("fumarc", "fumarc"),
        ("univasf", "univasf"),
        ("ufba", "ufba"),
        ("ifbaiano", "ifbaiano"),
    ):
        if re.search(rf"\b{re.escape(token[0])}\b", key):
            return token[1]
    return None


def _collect_db_counts(db_path: str | None) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    concursos_by_slug: dict[str, int] = {}
    provas_by_slug: dict[str, int] = {}
    questoes_by_slug: dict[str, int] = {}
    if not db_path:
        return concursos_by_slug, provas_by_slug, questoes_by_slug

    try:
        from radar import exam_papers
        exam_papers.ensure_exam_papers_seeded(db_path)
    except Exception:
        pass

    try:
        with closing(connect_documents(db_path)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "documentos" in tables:
                seen_pairs: set[tuple[str, str]] = set()
                for issuer, title, obs_id in conn.execute(
                    "SELECT issuer, title, COALESCE(observation_id, id) FROM documentos"
                ).fetchall():
                    slug = resolve_organizer_slug(issuer) or resolve_organizer_slug(title)
                    if slug and (slug, str(obs_id)) not in seen_pairs:
                        seen_pairs.add((slug, str(obs_id)))
                        concursos_by_slug[slug] = concursos_by_slug.get(slug, 0) + 1

            if "acervo_provas" in tables:
                for b_slug, count in conn.execute(
                    "SELECT banca_slug, COUNT(*) FROM acervo_provas GROUP BY banca_slug"
                ).fetchall():
                    canonical = "cebraspe" if b_slug == "cespe" else str(b_slug or "")
                    if canonical:
                        provas_by_slug[canonical] = provas_by_slug.get(canonical, 0) + int(count)

            if "pratica_questoes" in tables:
                for fonte, tags_raw in conn.execute(
                    "SELECT fonte, tags FROM pratica_questoes WHERE estado='ativo'"
                ).fetchall():
                    slug = None
                    try:
                        tags = json.loads(tags_raw or "[]")
                    except (TypeError, ValueError):
                        tags = []
                    for tag in tags:
                        if isinstance(tag, str) and tag.startswith("banca:"):
                            slug = resolve_organizer_slug(tag.split(":", 1)[1])
                            if slug:
                                break
                    if not slug:
                        slug = resolve_organizer_slug(fonte)
                    if slug:
                        questoes_by_slug[slug] = questoes_by_slug.get(slug, 0) + 1
    except Exception:
        pass

    return concursos_by_slug, provas_by_slug, questoes_by_slug


def list_organizers(
    db_path: str | None = None,
    *,
    q: str | None = None,
    grupo: str | None = None,
    letra: str | None = None,
    com_raio_x: bool | None = None,
    limit: int | None = None,
) -> dict:
    """Lista o diretório completo A–Z de organizadoras com contagens reais do banco."""
    concursos_map, provas_map, questoes_map = _collect_db_counts(db_path)
    q_norm = _norm(q)
    letra_norm = (letra or "").strip().upper()[:1]
    grupo_norm = (grupo or "").strip().lower()

    items = []
    grupos_count = {"nacional": 0, "federal_if_uf": 0, "regional_municipal": 0}

    for slug, nome in _RAW_ORGANIZERS:
        grp = _classify_group(slug, nome)
        grupos_count[grp] = grupos_count.get(grp, 0) + 1

        canonical_lookup = "cebraspe" if slug == "cespe" else slug
        raio_x_id = _RAIO_X_MAP.get(slug)
        tem_raio_x = bool(raio_x_id)

        if grupo_norm and grp != grupo_norm:
            continue
        if com_raio_x is True and not tem_raio_x:
            continue
        if letra_norm:
            first_char = _norm(nome)[:1].upper()
            if first_char != letra_norm:
                continue
        if q_norm and q_norm not in _norm(nome) and q_norm not in _norm(slug):
            continue

        # Evita duplicar a contagem de Cebraspe na linha legada "CESPE"
        is_legacy_alias = slug == "cespe"
        items.append(
            {
                "slug": slug,
                "nome": nome,
                "grupo": grp,
                "pci_url": f"https://www.pciconcursos.com.br/organizadoras/{slug}",
                "tem_raio_x_ti": tem_raio_x,
                "raio_x_id": raio_x_id,
                "alias_de": "cebraspe" if is_legacy_alias else None,
                "concursos_count": 0 if is_legacy_alias else concursos_map.get(canonical_lookup, 0),
                "provas_count": 0 if is_legacy_alias else provas_map.get(canonical_lookup, 0),
                "questoes_count": 0 if is_legacy_alias else questoes_map.get(canonical_lookup, 0),
            }
        )

    total_filtered = len(items)
    if limit is not None and limit > 0:
        items = items[: int(limit)]

    return {
        "total": total_filtered,
        "total_catalogo": len(_RAW_ORGANIZERS),
        "grupos": grupos_count,
        "itens": items,
    }
