"""Acervo estruturado de Provas Anteriores Oficiais & Extrator `pymupdf` de Questões.

Foco profundo em TI / Sistemas de Informação + disciplinas básicas nas principais bancas,
mantendo as demais carreiras (`administrativa`, `fiscal`, `tribunais`, `policial`, `educacao`)
catalogadas na superfície com estrutura pronta para expansão.
"""

from __future__ import annotations

import base64
import json
import re
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar import organizers_catalog, practice_store, real_exam_questions
from radar.document_store import connect_documents

CAREERS = ("ti", "administrativa", "fiscal", "tribunais", "policial", "educacao")

CAREER_LABELS = {
    "ti": "TI & Sistemas de Informação",
    "administrativa": "Administrativa & Gestão",
    "fiscal": "Fiscal & Controle",
    "tribunais": "Tribunais & Jurídica",
    "policial": "Policial & Segurança",
    "educacao": "Educação, IFs & Universidades",
}

_SEED_EXAM_PAPERS: tuple[dict, ...] = (
    # --- NÚCLEO PROFUNDO: TI & SISTEMAS DE INFORMAÇÃO -------------------------
    {
        "id": "prova-fgv-mpo-2024-ti",
        "titulo": "Analista de Planejamento e Orçamento - Tecnologia da Informação",
        "cargo": "Analista de Planejamento e Orçamento (TI)",
        "orgao": "Ministério do Planejamento e Orçamento (MPO)",
        "banca_slug": "fgv",
        "banca_nome": "FGV",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://conhecimento.fgv.br/concursos/mpo24",
        "gabarito_url": "https://conhecimento.fgv.br/concursos/mpo24",
        "match_orgao_tag": "orgao:mpo",
    },
    {
        "id": "prova-fgv-rfb-2023-ti",
        "titulo": "Auditor-Fiscal da Receita Federal - Tecnologia da Informação",
        "cargo": "Auditor-Fiscal (Ênfase TI / Bancos de Dados)",
        "orgao": "Receita Federal do Brasil (RFB)",
        "banca_slug": "fgv",
        "banca_nome": "FGV",
        "ano": 2023,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://conhecimento.fgv.br/concursos/rfb22",
        "gabarito_url": "https://conhecimento.fgv.br/concursos/rfb22",
        "match_orgao_tag": "orgao:receita_federal",
    },
    {
        "id": "prova-fgv-tcesp-2023-ti",
        "titulo": "Agente da Fiscalização - Tecnologia da Informação",
        "cargo": "Agente da Fiscalização - TI",
        "orgao": "TCE/SP",
        "banca_slug": "fgv",
        "banca_nome": "FGV",
        "ano": 2023,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://conhecimento.fgv.br/concursos/tcesp23",
        "gabarito_url": "https://conhecimento.fgv.br/concursos/tcesp23",
        "match_banca_fallback": "banca:fgv",
    },
    {
        "id": "prova-fgv-camara-2023-ti",
        "titulo": "Analista Legislativo - Informática Legislativa (Sistemas)",
        "cargo": "Analista Legislativo - Informática Legislativa",
        "orgao": "Câmara dos Deputados",
        "banca_slug": "fgv",
        "banca_nome": "FGV",
        "ano": 2023,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://conhecimento.fgv.br/concursos/camara23",
        "gabarito_url": "https://conhecimento.fgv.br/concursos/camara23",
        "match_banca_fallback": "banca:fgv",
    },
    {
        "id": "prova-cebraspe-dataprev-2024-ti",
        "titulo": "Analista de Tecnologia da Informação - Engenharia de Software",
        "cargo": "Analista de TI - Desenvolvimento / Arquitetura",
        "orgao": "DATAPREV",
        "banca_slug": "cebraspe",
        "banca_nome": "Cebraspe",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.cebraspe.org.br/concursos/dataprev_24",
        "gabarito_url": "https://www.cebraspe.org.br/concursos/dataprev_24",
        "match_orgao_tag": "orgao:dataprev",
    },
    {
        "id": "prova-cebraspe-bacen-2024-ti",
        "titulo": "Analista do Banco Central - Área 1: Tecnologia da Informação",
        "cargo": "Analista - Tecnologia da Informação",
        "orgao": "Banco Central do Brasil (BACEN)",
        "banca_slug": "cebraspe",
        "banca_nome": "Cebraspe",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.cebraspe.org.br/concursos/bcb_24",
        "gabarito_url": "https://www.cebraspe.org.br/concursos/bcb_24",
        "match_banca_fallback": "banca:cebraspe",
    },
    {
        "id": "prova-cebraspe-serpro-2023-ti",
        "titulo": "Analista - Especialização: Tecnologia (Desenvolvimento e Dados)",
        "cargo": "Analista de Sistemas / TI",
        "orgao": "SERPRO",
        "banca_slug": "cebraspe",
        "banca_nome": "Cebraspe",
        "ano": 2023,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.cebraspe.org.br/concursos/serpro_23",
        "gabarito_url": "https://www.cebraspe.org.br/concursos/serpro_23",
        "match_banca_fallback": "banca:cebraspe",
    },
    {
        "id": "prova-fcc-tjpe-2024-si",
        "titulo": "Analista Judiciário - Apoio Especializado: Sistemas de Informação",
        "cargo": "Analista Judiciário - Sistemas de Informação",
        "orgao": "TJ/PE",
        "banca_slug": "fcc",
        "banca_nome": "FCC",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.concursosfcc.com.br/",
        "gabarito_url": "https://www.concursosfcc.com.br/",
        "match_banca_fallback": "banca:fcc",
    },
    {
        "id": "prova-fcc-trt5-2023-ti",
        "titulo": "Analista Judiciário - Tecnologia da Informação",
        "cargo": "Analista Judiciário - TI",
        "orgao": "TRT 5ª Região (BA)",
        "banca_slug": "fcc",
        "banca_nome": "FCC",
        "ano": 2023,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.concursosfcc.com.br/",
        "gabarito_url": "https://www.concursosfcc.com.br/",
        "match_banca_fallback": "banca:fcc",
    },
    {
        "id": "prova-cesgranrio-caixa-2024-ti",
        "titulo": "Técnico Bancário Novo - Tecnologia da Informação",
        "cargo": "Técnico Bancário Novo - Polo TI",
        "orgao": "Caixa Econômica Federal",
        "banca_slug": "cesgranrio",
        "banca_nome": "Cesgranrio",
        "ano": 2024,
        "nivel": "medio",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.cesgranrio.org.br/concursos/principal.aspx",
        "gabarito_url": "https://www.cesgranrio.org.br/concursos/principal.aspx",
        "match_banca_fallback": "banca:cesgranrio",
    },
    {
        "id": "prova-cesgranrio-bb-2023-ti",
        "titulo": "Escriturário - Agente de Tecnologia (TI)",
        "cargo": "Agente de Tecnologia",
        "orgao": "Banco do Brasil",
        "banca_slug": "cesgranrio",
        "banca_nome": "Cesgranrio",
        "ano": 2023,
        "nivel": "medio",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.cesgranrio.org.br/concursos/principal.aspx",
        "gabarito_url": "https://www.cesgranrio.org.br/concursos/principal.aspx",
        "match_banca_fallback": "banca:cesgranrio",
    },
    {
        "id": "prova-vunesp-tjsp-2024-ti",
        "titulo": "Analista de Sistemas Judiciário",
        "cargo": "Analista de Sistemas",
        "orgao": "TJ/SP",
        "banca_slug": "vunesp",
        "banca_nome": "Vunesp",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.vunesp.com.br/",
        "gabarito_url": "https://www.vunesp.com.br/",
        "match_banca_fallback": "banca:vunesp",
    },
    {
        "id": "prova-quadrix-conselhos-2024-ti",
        "titulo": "Analista de Tecnologia da Informação e Suporte de Sistemas",
        "cargo": "Analista de TI",
        "orgao": "Conselhos Federais / Regionais",
        "banca_slug": "instituto-quadrix",
        "banca_nome": "Instituto Quadrix",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://www.quadrix.org.br/",
        "gabarito_url": "https://www.quadrix.org.br/",
        "match_banca_fallback": "banca:quadrix",
    },
    {
        "id": "prova-ibfc-ebserh-2023-ti",
        "titulo": "Analista Administrativo - Tecnologia da Informação (Sistemas)",
        "cargo": "Analista de TI",
        "orgao": "EBSERH Nacional",
        "banca_slug": "ibfc",
        "banca_nome": "IBFC",
        "ano": 2023,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://concursos.ibfc.org.br/",
        "gabarito_url": "https://concursos.ibfc.org.br/",
        "match_banca_fallback": "banca:ibfc",
    },
    {
        "id": "prova-univasf-2024-ti",
        "titulo": "Analista de Tecnologia da Informação (TAE - Sistemas)",
        "cargo": "Analista de Tecnologia da Informação",
        "orgao": "UNIVASF (Vale do São Francisco / Paulo Afonso)",
        "banca_slug": "univasf",
        "banca_nome": "UNIVASF",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "ti",
        "edital_ou_prova_url": "https://portais.univasf.edu.br/",
        "gabarito_url": "https://portais.univasf.edu.br/",
        "match_banca_fallback": None,
    },
    {
        "id": "prova-ifbaiano-2024-ti",
        "titulo": "Técnico de Tecnologia da Informação (TAE)",
        "cargo": "Técnico de Tecnologia da Informação",
        "orgao": "IFBaiano / IFSERTÃO",
        "banca_slug": "ifbaiano",
        "banca_nome": "IFBaiano",
        "ano": 2024,
        "nivel": "medio",
        "carreira": "ti",
        "edital_ou_prova_url": "https://concursos.ifbaiano.edu.br/",
        "gabarito_url": "https://concursos.ifbaiano.edu.br/",
        "match_banca_fallback": None,
    },
    # --- SUPERFÍCIE DE EXPANSÃO: DEMAIS ÁREAS ESTILO PCI ----------------------
    {
        "id": "prova-cebraspe-inss-adm",
        "titulo": "Técnico do Seguro Social (Carreira Administrativa)",
        "cargo": "Técnico do Seguro Social",
        "orgao": "INSS",
        "banca_slug": "cebraspe",
        "banca_nome": "Cebraspe",
        "ano": 2022,
        "nivel": "medio",
        "carreira": "administrativa",
        "edital_ou_prova_url": "https://www.cebraspe.org.br/concursos/inss_22",
        "gabarito_url": "https://www.cebraspe.org.br/concursos/inss_22",
        "match_banca_fallback": None,
    },
    {
        "id": "prova-cesgranrio-ibge-adm",
        "titulo": "Agente de Pesquisas e Mapeamento",
        "cargo": "Agente de Pesquisas e Mapeamento",
        "orgao": "IBGE",
        "banca_slug": "cesgranrio",
        "banca_nome": "Cesgranrio",
        "ano": 2023,
        "nivel": "medio",
        "carreira": "administrativa",
        "edital_ou_prova_url": "https://www.cesgranrio.org.br/concursos/principal.aspx",
        "gabarito_url": "https://www.cesgranrio.org.br/concursos/principal.aspx",
        "match_banca_fallback": None,
    },
    {
        "id": "prova-fgv-sefaz-fiscal",
        "titulo": "Auditor Fiscal da Receita Estadual (Área Geral)",
        "cargo": "Auditor Fiscal",
        "orgao": "SEFAZ/MG",
        "banca_slug": "fgv",
        "banca_nome": "FGV",
        "ano": 2023,
        "nivel": "superior",
        "carreira": "fiscal",
        "edital_ou_prova_url": "https://conhecimento.fgv.br/concursos/",
        "gabarito_url": "https://conhecimento.fgv.br/concursos/",
        "match_banca_fallback": None,
    },
    {
        "id": "prova-fcc-trf3-tribunais",
        "titulo": "Técnico Judiciário - Área Administrativa",
        "cargo": "Técnico Judiciário",
        "orgao": "TRF 3ª Região",
        "banca_slug": "fcc",
        "banca_nome": "FCC",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "tribunais",
        "edital_ou_prova_url": "https://www.concursosfcc.com.br/",
        "gabarito_url": "https://www.concursosfcc.com.br/",
        "match_banca_fallback": None,
    },
    {
        "id": "prova-cebraspe-pf-policial",
        "titulo": "Agente de Polícia Federal",
        "cargo": "Agente de Polícia Federal",
        "orgao": "Polícia Federal (PF)",
        "banca_slug": "cebraspe",
        "banca_nome": "Cebraspe",
        "ano": 2021,
        "nivel": "superior",
        "carreira": "policial",
        "edital_ou_prova_url": "https://www.cebraspe.org.br/concursos/",
        "gabarito_url": "https://www.cebraspe.org.br/concursos/",
        "match_banca_fallback": None,
    },
    {
        "id": "prova-ifpe-ebtt-educacao",
        "titulo": "Professor do Ensino Básico, Técnico e Tecnológico (Computação)",
        "cargo": "Professor EBTT - Informática",
        "orgao": "IFPE",
        "banca_slug": "ifpe",
        "banca_nome": "IFPE",
        "ano": 2024,
        "nivel": "superior",
        "carreira": "educacao",
        "edital_ou_prova_url": "https://portal.ifpe.edu.br/",
        "gabarito_url": "https://portal.ifpe.edu.br/",
        "match_banca_fallback": None,
    },
)


def _ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS acervo_provas (
            id TEXT PRIMARY KEY,
            titulo TEXT NOT NULL,
            cargo TEXT NOT NULL,
            orgao TEXT NOT NULL,
            banca_slug TEXT NOT NULL,
            banca_nome TEXT NOT NULL,
            ano INTEGER NOT NULL,
            nivel TEXT NOT NULL DEFAULT 'superior',
            carreira TEXT NOT NULL DEFAULT 'ti',
            edital_ou_prova_url TEXT,
            gabarito_url TEXT,
            match_tag TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def ensure_exam_papers_seeded(db_path: str) -> None:
    """Garante a criação da tabela `acervo_provas`, semeadura inicial e questões reais."""
    try:
        real_exam_questions.seed_real_questions(db_path)
    except Exception:
        pass

    now = datetime.now(timezone.utc).isoformat()
    with closing(connect_documents(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _ensure_schema(conn)
            existing = {
                row[0] for row in conn.execute("SELECT id FROM acervo_provas").fetchall()
            }
            for item in _SEED_EXAM_PAPERS:
                if item["id"] in existing:
                    continue
                match_tag = item.get("match_orgao_tag") or item.get("match_banca_fallback")
                conn.execute(
                    """
                    INSERT INTO acervo_provas(
                        id, titulo, cargo, orgao, banca_slug, banca_nome,
                        ano, nivel, carreira, edital_ou_prova_url, gabarito_url,
                        match_tag, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"],
                        item["titulo"],
                        item["cargo"],
                        item["orgao"],
                        item["banca_slug"],
                        item["banca_nome"],
                        int(item["ano"]),
                        item["nivel"],
                        item["carreira"],
                        item.get("edital_ou_prova_url"),
                        item.get("gabarito_url"),
                        match_tag,
                        now,
                    ),
                )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


def list_exam_papers(
    db_path: str,
    *,
    q: str | None = None,
    banca: str | None = None,
    carreira: str | None = None,
    ano: int | str | None = None,
    limit: int = 200,
) -> dict:
    """Lista provas anteriores no estilo diretório PCI com contagem real de questões vinculadas."""
    ensure_exam_papers_seeded(db_path)

    with closing(connect_documents(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT id, titulo, cargo, orgao, banca_slug, banca_nome,
                   ano, nivel, carreira, edital_ou_prova_url, gabarito_url, match_tag
            FROM acervo_provas
            ORDER BY CASE WHEN carreira = 'ti' THEN 0 ELSE 1 END, ano DESC, titulo ASC
            """
        ).fetchall()

        question_tags_list: list[set[str]] = []
        has_questions = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pratica_questoes'"
        ).fetchone()
        if has_questions:
            for (tags_raw,) in conn.execute(
                "SELECT tags FROM pratica_questoes WHERE estado='ativo'"
            ).fetchall():
                try:
                    parsed = json.loads(tags_raw or "[]")
                    question_tags_list.append({str(t).strip().lower() for t in parsed})
                except (TypeError, ValueError):
                    pass

    por_carreira: dict[str, int] = {c: 0 for c in CAREERS}
    banca_filter = organizers_catalog.resolve_organizer_slug(banca) if banca else None
    carreira_filter = (carreira or "").strip().lower()
    ano_filter = int(ano) if ano not in (None, "") else None
    q_filter = (q or "").strip().lower()

    items = []
    for row in rows:
        (
            pid,
            titulo,
            cargo,
            orgao,
            banca_slug,
            banca_nome,
            p_ano,
            nivel,
            p_carreira,
            prova_url,
            gab_url,
            match_tag,
        ) = row
        por_carreira[p_carreira] = por_carreira.get(p_carreira, 0) + 1

        if carreira_filter and p_carreira != carreira_filter:
            continue
        if banca_filter and organizers_catalog.resolve_organizer_slug(banca_slug) != banca_filter:
            continue
        if ano_filter is not None and int(p_ano) != ano_filter:
            continue
        if q_filter:
            haystack = f"{titulo} {cargo} {orgao} {banca_nome} {p_ano}".lower()
            if q_filter not in haystack:
                continue

        paper_tag = f"prova:{pid}".lower()
        fallback_tag = (match_tag or "").strip().lower()
        direct_matches = sum(1 for tset in question_tags_list if paper_tag in tset)
        if direct_matches > 0:
            q_count = direct_matches
            simulado_tag = paper_tag
        elif fallback_tag:
            q_count = sum(1 for tset in question_tags_list if fallback_tag in tset)
            simulado_tag = fallback_tag if q_count > 0 else None
        else:
            q_count = 0
            simulado_tag = None

        items.append(
            {
                "id": pid,
                "titulo": titulo,
                "cargo": cargo,
                "orgao": orgao,
                "banca_slug": banca_slug,
                "banca_nome": banca_nome,
                "ano": int(p_ano),
                "nivel": nivel,
                "carreira": p_carreira,
                "carreira_label": CAREER_LABELS.get(p_carreira, p_carreira.title()),
                "edital_ou_prova_url": prova_url,
                "gabarito_url": gab_url,
                "questoes_count": q_count,
                "simulado_tag": simulado_tag,
            }
        )

    total = len(items)
    return {
        "total": total,
        "por_carreira": por_carreira,
        "itens": items[: max(1, int(limit))],
    }


def _parse_gabarito_map(texto_gabarito: str) -> dict[int, str]:
    ans: dict[int, str] = {}
    for match in re.finditer(
        r"(?:^|\s|;|\|)(\d{1,3})\s*[-–:.=\)]\s*([A-ECeVvfF])\b",
        texto_gabarito or "",
    ):
        num = int(match.group(1))
        letter = match.group(2).upper()
        if letter == "C" and "CERTO" in (texto_gabarito or "").upper():
            letter = "V"
        ans[num] = letter
    return ans


def extract_questions_from_exam_text(
    texto_prova: str,
    texto_gabarito: str = "",
) -> list[dict]:
    """Extrai questões numeradas com alternativas A–D/E a partir do texto oficial da prova."""
    gabarito_map = _parse_gabarito_map(texto_gabarito)
    raw = (texto_prova or "").strip()
    if not raw:
        return []

    blocks = re.split(r"(?:^|\n)\s*(\d{1,3})\s*[\.\)\-–]\s+", raw)
    # blocks = [prefix, num1, body1, num2, body2, ...]
    extracted: list[dict] = []
    for idx in range(1, len(blocks) - 1, 2):
        q_num = int(blocks[idx])
        body = blocks[idx + 1].strip()
        opt_parts = re.split(r"(?:^|\n)\s*[\(\[]?([A-E])[\)\]\.\-–]\s+", body)
        if len(opt_parts) < 5:
            continue
        stem = " ".join(opt_parts[0].split()).strip()
        if len(stem) < 12:
            continue
        options: list[dict[str, str]] = []
        for o_idx in range(1, len(opt_parts) - 1, 2):
            letra = opt_parts[o_idx].upper()
            texto = " ".join(opt_parts[o_idx + 1].split()).strip()
            if texto:
                options.append({"id": letra, "texto": texto})
        if len(options) < 2:
            continue
        gab = gabarito_map.get(q_num, options[0]["id"])
        valid_letters = {o["id"] for o in options}
        if gab not in valid_letters:
            gab = options[0]["id"]
        extracted.append(
            {
                "numero": q_num,
                "enunciado": stem,
                "alternativas": options,
                "gabarito": gab,
            }
        )
    return extracted


def _extract_pdf_text_if_provided(pdf_base64: str | None) -> str:
    if not pdf_base64:
        return ""
    import pymupdf

    raw_bytes = base64.b64decode(pdf_base64)
    doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def import_exam_paper(db_path: str, payload: dict) -> dict:
    """Registra uma prova pública oficial em `acervo_provas` e extrai suas questões opcionais."""
    ensure_exam_papers_seeded(db_path)

    titulo = str(payload.get("titulo") or "").strip()
    orgao = str(payload.get("orgao") or "").strip()
    banca_raw = str(payload.get("banca") or "").strip()
    if not titulo or not orgao or not banca_raw:
        raise ValueError("titulo, orgao e banca são obrigatórios")

    cargo = str(payload.get("cargo") or titulo).strip()
    banca_slug = organizers_catalog.resolve_organizer_slug(banca_raw) or re.sub(
        r"[^a-z0-9-]+", "-", banca_raw.lower()
    ).strip("-")
    ano = int(payload.get("ano") or datetime.now(timezone.utc).year)
    nivel = str(payload.get("nivel") or "superior").strip().lower()
    carreira = str(payload.get("carreira") or "ti").strip().lower()
    if carreira not in CAREERS:
        carreira = "ti"

    paper_id = f"prova-{banca_slug}-{ano}-{uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat()
    prova_url = str(payload.get("edital_ou_prova_url") or "").strip() or None
    gabarito_url = str(payload.get("gabarito_url") or "").strip() or None

    with closing(connect_documents(db_path)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            _ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO acervo_provas(
                    id, titulo, cargo, orgao, banca_slug, banca_nome,
                    ano, nivel, carreira, edital_ou_prova_url, gabarito_url,
                    match_tag, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    titulo,
                    cargo,
                    orgao,
                    banca_slug,
                    banca_raw,
                    ano,
                    nivel,
                    carreira,
                    prova_url,
                    gabarito_url,
                    f"prova:{paper_id}",
                    now,
                ),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    texto_prova = str(payload.get("texto_prova") or "").strip()
    if not texto_prova and payload.get("pdf_base64"):
        texto_prova = _extract_pdf_text_if_provided(str(payload.get("pdf_base64")))
    texto_gabarito = str(payload.get("texto_gabarito") or "").strip()
    disciplina_padrao = str(payload.get("disciplina_padrao") or "Conhecimentos Específicos de TI").strip()

    extracted_items = extract_questions_from_exam_text(texto_prova, texto_gabarito)
    created_count = 0
    for item in extracted_items:
        practice_store.create_question(
            db_path,
            tipo="escolha_unica",
            enunciado=item["enunciado"],
            alternativas=item["alternativas"],
            gabarito=item["gabarito"],
            comentario=f"Questão oficial #{item['numero']} extraída da prova {banca_raw} ({ano}) — {orgao}.",
            disciplina=disciplina_padrao,
            topico=cargo,
            dificuldade="media",
            tags=[
                f"prova:{paper_id}",
                f"banca:{banca_slug}",
                f"ano:{ano}",
                f"carreira:{carreira}",
            ],
            fonte=f"{banca_raw} - {ano} - {orgao} - {cargo}",
            licenca="prova_publica",
            procedencia=prova_url or "importacao_oficial_admin",
        )
        created_count += 1

    papers = list_exam_papers(db_path, q=titulo)
    created_row = next((it for it in papers["itens"] if it["id"] == paper_id), None)
    return {
        "ok": True,
        "prova": created_row or {"id": paper_id, "titulo": titulo},
        "questoes_extraidas": created_count,
    }
