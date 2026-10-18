"""Continuidade de tabelas entre páginas, com proveniência por segmento (Fase 32).

Problema real (IBFC 004/2026): o cabeçalho do quadro de vagas está na página 21, as linhas
ocupam 21–29 e o `TOTAL` aparece na página 29 — **sem** cabeçalho na mesma página. Tratar
cada página como tabela independente perde o total ou o atribui à tabela errada.

Este módulo reconhece a estrutura e classifica a continuidade por **evidências combinadas**,
nunca por proximidade de páginas:

| Sinal | Peso | Por quê |
|---|---|---|
| cabeçalho repetido na continuação | +3 | o próprio documento declara a mesma tabela |
| numeração de NTE contínua (01→27) | +3 | sequência sem lacuna nem reinício |
| retoma o NTE em curso (sub-cabeçalho repetido) | +2 | é a mesma tabela continuando |
| página abre no meio da lista de municípios | +2 | corte de página, não de estrutura |
| página fecha com TOTAL | +2 | o quadro em curso termina ali |
| linhas de município sem NTE na página | +1 | continuação de lista |
| TOTAL encerra / nota de rodapé presente | +1 cada | marcadores de fim de quadro |
| abre novo ANEXO/QUADRO | −3 | início de outra estrutura |
| NTE volta/reinicia numeração | −2 | outro quadro |
| apenas página seguinte | 0 | **proximidade não comprova nada** |

Limiares: `forte` ≥ 5, `provavel` ≥ 2, `independente` ≤ −2, senão `ambigua`.

Resultado: `forte`, `provavel`, `independente`, `ambigua` ou `irreconstruivel`. Nada é gravado
aqui: a estrutura é insumo de extração e de revisão.
"""

from __future__ import annotations

import re
import unicodedata

CONTINUITY_VERSION = "table_continuity_v1"

# Cabeçalho do quadro com total agregado (mesma família da Fase 31).
_AGG_HEADER = re.compile(r"TOTAL\s+DE\s+VAGAS\s*(?:\(([^)]{3,160})\))?", re.I)
# Linha de NTE: "NTE 05 - SEDE: ITABUNA 140" (case-insensitive; aceita "SEDE:").
# "NTE 05 - SEDE: ITABUNA 140" e a variante "NÚCLEO 06 - VALENÇA 34" (mesma estrutura,
# rótulo diferente no 004/2026). "SEDE:" é opcional.
_NTE_ROW = re.compile(
    r"\b(?:NTE|N[ÚU]CLEO)\s*(\d{1,2})\s*[-–—]?\s*(?:SEDE\s*:\s*)?"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' .\-]{1,50}?)\s+"
    r"(\d{1,3}(?:\.\d{3})+|\d{1,5})\b", re.I)
# Linha município/quantidade dentro do NTE: "IRECÊ 30".
_MUN_ROW = re.compile(r"\b([A-ZÀ-Þ][A-ZÀ-Þ' \-]{2,45}?)\s+(\d{1,4})\b")
_TOTAL = re.compile(r"\bTOTAL\s+(\d{1,3}(?:\.\d{3})+|\d{1,6})\b", re.I)
# Nomes que não são município (evitam inflar o sinal de "linha de município").
_MUN_NOISE = {"TOTAL", "LEI", "DECRETO", "ANEXO", "PAGINA", "ART", "INCISO", "PARAGRAFO"}
_NEW_SECTION = re.compile(
    r"\bANEXO\s+[IVXLCDM]+\b|\bQUADRO\s+DE\s+VAGAS\b|\bTABELA\s+\d|\bDEMONSTRATIVO\b", re.I)
_FOOTNOTE = re.compile(r"\(\s*\*\s*\)\s*Total\s+de\s+vagas\s+incluindo", re.I)


def _norm(text: str) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.upper().split())


def _qty(value: str) -> int:
    return int(value.replace(".", ""))


def _rows(text: str) -> dict:
    """Linhas reconhecidas no texto de uma página."""
    ntes = [{"nte": int(match.group(1)), "sede": " ".join(match.group(2).split()),
             "total": _qty(match.group(3)), "quote": match.group(0),
             "start": match.start(), "end": match.end(), "page": None}
            for match in _NTE_ROW.finditer(text)]
    total = _TOTAL.search(text)
    return {
        "ntes": ntes,
        "municipios": sum(1 for match in _MUN_ROW.finditer(text)
                          if _norm(match.group(1)) not in _MUN_NOISE),
        "total": _qty(total.group(1)) if total else None,
        "total_quote": total.group(0) if total else None,
        "total_start": total.start() if total else None,
        "total_end": total.end() if total else None,
        # A nota de rodapé "( * ) Total de vagas incluindo..." não é cabeçalho de quadro: ela é
        # mascarada antes da busca, sem anular um cabeçalho real na mesma página.
        "header": bool(_AGG_HEADER.search(_FOOTNOTE.sub(" ", text))),
        "novo_anexo": bool(_NEW_SECTION.search(text)),
        "nota": bool(_FOOTNOTE.search(text)),
    }


def page_signatures(blocks: list[dict]) -> list[dict]:
    """Assinatura por página (ordem de página), só para páginas com cara de quadro."""
    by_page = {}
    for block in blocks:
        page = block.get("page_number")
        if page is None:
            continue
        by_page.setdefault(page, []).append(block.get("text") or "")
    pages = []
    for page in sorted(by_page):
        text = " ".join(by_page[page])
        signature = _rows(text)
        signature["page"] = page
        for row in signature["ntes"]:
            row["page"] = page
        signature["text"] = text
        # Página candidata a quadro: cabeçalho agregado, linha de NTE ou TOTAL.
        signature["tabela"] = bool(signature["header"] or signature["ntes"]
                                   or signature["total"] is not None)
        pages.append(signature)
    return pages


def _transition(previous: dict, current: dict) -> dict:
    """Avalia se `current` continua a tabela de `previous` (sinais combinados)."""
    sinais = []
    score = 0
    if current["header"]:
        sinais.append({"sinal": "cabecalho_repetido", "peso": 3})
        score += 3
    # Página que fecha com TOTAL pertence ao quadro em curso, mesmo que cite "anexo".
    if current["novo_anexo"] and not current["header"] and current["total"] is None:
        sinais.append({"sinal": "abre_novo_anexo", "peso": -3})
        score -= 3
    if previous["ntes"] and current["ntes"]:
        last = max(row["nte"] for row in previous["ntes"])
        first = min(row["nte"] for row in current["ntes"])
        if first > last:
            sinais.append({"sinal": "ntes_continuam", "peso": 3,
                           "detalhe": f"{last} → {first}"})
            score += 3
        elif first == last:
            # A continuação retoma o NTE em curso (sub-cabeçalho repetido): é o mesmo quadro.
            sinais.append({"sinal": "retoma_nte_em_curso", "peso": 2,
                           "detalhe": f"NTE {first}"})
            score += 2
        elif first < last:
            sinais.append({"sinal": "ntes_repetem_ou_voltam", "peso": -2,
                           "detalhe": f"{last} → {first}"})
            score -= 2
    # A página começa no meio da lista de municípios (antes do primeiro NTE da página):
    # evidência estrutural forte de que a tabela continua da página anterior.
    first_nte = _NTE_ROW.search(current["text"])
    prefixo = current["text"][:first_nte.start()] if first_nte else current["text"]
    if _MUN_ROW.search(prefixo):
        sinais.append({"sinal": "inicia_no_meio_da_lista", "peso": 2})
        score += 2
    if current["total"] is not None and previous["ntes"]:
        sinais.append({"sinal": "fecha_com_total", "peso": 2})
        score += 2
    if previous["ntes"] and current["municipios"] and not current["ntes"]:
        sinais.append({"sinal": "linhas_de_municipio_sem_cabecalho", "peso": 1})
        score += 1
    if current["total"] is not None and previous["total"] is None:
        sinais.append({"sinal": "total_encerra", "peso": 1})
        score += 1
    if current["nota"]:
        sinais.append({"sinal": "nota_de_rodape", "peso": 1})
        score += 1
    sinais.append({"sinal": "pagina_adjacente", "peso": 0,
                   "detalhe": f"p{previous['page']} → p{current['page']} "
                              f"(proximidade isolada não comprova)"})
    if score >= 5:
        certeza = "forte"
    elif score >= 2:
        certeza = "provavel"
    elif score <= -2:
        certeza = "independente"
    else:
        certeza = "ambigua"
    return {"from_page": previous["page"], "to_page": current["page"],
            "score": score, "certeza": certeza, "sinais": sinais}


def analyze_tables(blocks: list[dict]) -> list[dict]:
    """Reconstrói quadros multipágina e classifica cada continuidade."""
    pages = page_signatures(blocks)
    tables = []
    current = None
    for page in pages:
        if not page["tabela"]:
            if current is not None and current.get("aberta"):
                # Página sem quadro encerra a estrutura corrente.
                current["aberta"] = False
            continue
        if current is None or not current["aberta"]:
            current = {"tipo": "quadro_vagas", "aberta": True,
                       "header_page": page["page"] if page["header"] else None,
                       "pages": [page["page"]], "row_pages": [], "total_page": None,
                       "transitions": [], "rows": list(page["ntes"]),
                       "total": page["total"], "nota": page["nota"],
                       "header_quote": None}
            tables.append(current)
        else:
            transition = _transition(pages[[p["page"] for p in pages].index(
                current["pages"][-1])], page)
            current["transitions"].append(transition)
            if transition["certeza"] == "independente":
                current["aberta"] = False
                current = {"tipo": "quadro_vagas", "aberta": True,
                           "header_page": page["page"] if page["header"] else None,
                           "pages": [page["page"]], "row_pages": [], "total_page": None,
                           "transitions": [], "rows": list(page["ntes"]),
                           "total": page["total"], "nota": page["nota"],
                           "header_quote": None}
                tables.append(current)
                continue
            current["pages"].append(page["page"])
            current["rows"].extend(page["ntes"])
        if page["ntes"] or page["municipios"]:
            current["row_pages"].append(page["page"])
        if page["header"] and current["header_quote"] is None:
            match = _AGG_HEADER.search(page["text"])
            current["header_quote"] = page["text"][match.start():match.end()]
        if page["total"] is not None:
            current["total"] = page["total"]
            current["total_page"] = page["page"]
            current["total_quote"] = page["total_quote"]
            current["aberta"] = False
    return [_summarize(table, pages) for table in tables]


def _dedupe_ntes(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Uma linha por NTE: a **primeira** ocorrência carrega o total.

    O documento repete o cabeçalho do NTE antes da lista de municípios
    ("NTE 01 - SEDE: IRECÊ 84 NTE 01 - SEDE: IRECÊ AMERICA DOURADA 3"): a segunda ocorrência é
    sub-cabeçalho, e o número seguinte pertence ao município — não ao NTE.
    """
    primeira, repetidas = {}, []
    for row in rows:
        if row["nte"] in primeira:
            repetidas.append(row)
            continue
        primeira[row["nte"]] = row
    return [primeira[key] for key in sorted(primeira)], repetidas


def _summarize(table: dict, pages: list[dict]) -> dict:
    page_map = {page["page"]: page for page in pages}
    transitions = table.get("transitions", [])
    if not transitions:
        certeza = "forte" if table["header_page"] and table["total_page"] else "ambigua"
    else:
        ordem = {"forte": 3, "provavel": 2, "ambigua": 1, "independente": 0}
        certeza = min((t["certeza"] for t in transitions), key=lambda c: ordem[c])
        if table["header_page"] is None:
            certeza = "irreconstruivel"  # linhas sem cabeçalho em nenhuma página
    ambiguidades = []
    if table["header_page"] is None:
        ambiguidades.append("cabeçalho do quadro não localizado no documento")
    if table["total_page"] is None:
        ambiguidades.append("TOTAL não localizado: soma das linhas não pode ser conferida")
    if any(t["certeza"] == "ambigua" for t in transitions):
        ambiguidades.append("transição de página ambígua entre segmentos")
    unicos, repetidas = _dedupe_ntes(table["rows"])
    ntes = [row["nte"] for row in unicos]
    if ntes:
        esperado = list(range(min(ntes), max(ntes) + 1))
        faltando = [n for n in esperado if n not in ntes]
        if faltando:
            ambiguidades.append(
                f"numeração publicada não inclui NTE {faltando[:5]} (ausente no documento)")
    conflitos = [row for row in repetidas
                 if row["total"] != next((u["total"] for u in unicos
                                          if u["nte"] == row["nte"]), None)
                 and (row.get("page") or 0) > next(
                     (u.get("page") or 0 for u in unicos if u["nte"] == row["nte"]), 0)]
    if conflitos:
        ambiguidades.append(f"{len(conflitos)} ocorrência(s) repetida(s) de NTE com total "
                            f"diferente do primeiro")
    soma = sum(row["total"] for row in unicos)
    if table["total"] is not None and table["total"] != soma:
        ambiguidades.append(f"TOTAL {table['total']} difere da soma das linhas {soma}")
    segments = []
    for page_number in table["pages"]:
        page = page_map.get(page_number, {})
        segments.append({
            "page": page_number,
            "papel": ("cabecalho" if page_number == table["header_page"] else
                      ("total" if page_number == table["total_page"] else "linhas")),
            "linhas": len(page.get("ntes") or []),
            "municipios": page.get("municipios", 0),
            "total": page.get("total"),
            "quote": (page.get("total_quote") if page_number == table["total_page"]
                      else None),
        })
    return {
        "version": CONTINUITY_VERSION,
        "table_id": f"quadro-vagas-p{table['pages'][0]}",
        "tipo": table["tipo"],
        "header_page": table["header_page"],
        "row_pages": sorted(set(table["row_pages"])),
        "total_page": table["total_page"],
        "pages": table["pages"],
        "certeza": certeza,
        "transitions": transitions,
        "header_quote": table.get("header_quote"),
        "total": table["total"],
        "total_quote": table.get("total_quote"),
        "soma_linhas": soma,
        "ntes": unicos,
        "ntes_repetidos": len(repetidas),
        "segments": segments,
        "ambiguidades": ambiguidades,
        "limitacao": ("Estrutura reconstruída por sinais combinados; não é fato confirmado. "
                      "Cada segmento mantém a página de origem."),
    }


def continuity_report(blocks: list[dict], *, only_multi_page: bool = False) -> dict:
    tables = analyze_tables(blocks)
    if only_multi_page:
        tables = [table for table in tables if len(table["pages"]) > 1]
    return {"version": CONTINUITY_VERSION, "total": len(tables),
            "multipagina": sum(1 for table in tables if len(table["pages"]) > 1),
            "tabelas": tables}


def continuity_report_all(db_path, *, limit: int = 2000) -> dict:
    """Quadros contínuos em todas as versões analisadas (somente leitura).

    Só devolve tabelas com mais de uma página: uma tabela de página única não precisa de
    reconstrução e polui a leitura operacional.
    """
    from contextlib import closing

    from radar.document_store import connect_documents, is_readable_schema

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        versions = conn.execute(
            """SELECT v.id,d.title FROM versoes_documento v
               JOIN documentos d ON d.id=v.document_id
               WHERE EXISTS (SELECT 1 FROM blocos_documento b WHERE b.version_id=v.id)
               ORDER BY d.title LIMIT ?""", (int(limit),)).fetchall()
        report = {"version": CONTINUITY_VERSION, "total": 0, "multipagina": 0,
                  "tabelas": []}
        for version_id, title in versions:
            blocks = [{"page_number": page, "text": text} for page, text in conn.execute(
                "SELECT page_number,text FROM blocos_documento WHERE version_id=? "
                "ORDER BY page_number,start_offset", (version_id,))]
            for table in analyze_tables(blocks):
                if len(table["pages"]) <= 1:
                    continue
                # Sem NTE nem total não é quadro de vagas: é falso positivo de página.
                if not table["ntes"] and table["total"] is None:
                    continue
                report["tabelas"].append(dict(table, version_id=version_id, title=title))
    report["total"] = len(report["tabelas"])
    report["multipagina"] = report["total"]
    return report
