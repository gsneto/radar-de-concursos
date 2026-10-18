"""Escopo documental: cargo do edital, NTE e distribuição regional (Fase 32).

O quadro do IBFC 004/2026 **não tem coluna de cargo**: ele distribui vagas por NTE e
município. Atribuir esses números ao "cargo mais próximo" seria associação por proximidade —
proibida. Este módulo:

1. identifica o cargo **no escopo do edital** (texto do próprio edital, com citação);
2. usa o cargo do escopo somente quando ele é **único**; com mais de um, a relação é ambígua;
3. reconstrói a distribuição por NTE/município a partir do quadro contínuo (Fase 32);
4. separa rigorosamente NTE (regional administrativa) de município e de local de prova.

Nada aqui confirma campo: a relação cargo↔NTE é **candidata estrutural**, com a evidência que
a sustenta e o estado de certeza. Só o `TOTAL` do quadro vira proposta por padrão; os totais de
NTE são relatório estrutural.
"""

from __future__ import annotations

import json
import re
import unicodedata

from radar import table_continuity

SCOPE_VERSION = "regional_scope_v2"
METHOD_TOTAL = "quadro-vagas-regional"

# Cargo declarado no edital. Padrões fortes (escopo do certame) e fracos (menções soltas,
# como "função de jurado" em critério de pontuação) são separados de propósito.
_STRONG_CARGO = re.compile(
    r"\b(?:fun[çc][ãa]o\s+tempor[áa]ria\s+de|provimento\s+do\s+cargo\s+de|cargo\s+de)\s+"
    r"([^,.;:()]{4,110})", re.I)
_WEAK_CARGO = re.compile(r"\bfun[çc][ãa]o\s+de\s+([^,.;:()]{4,110})", re.I)
# Corta o nome do cargo antes de conectivo de continuação da frase.
_CARGO_CUT = re.compile(
    r"\s+(?:para|da|do|das|dos|na|no|nas|nos|em)\s+|\s*[-–—]\s*(?=[a-zà-ÿ])", re.I)
# Rótulo do NTE; "SEDE:" é opcional porque o NÚCLEO 06 aparece como "NÚCLEO 06 - VALENÇA 34".
# O total de cada NTE é sempre a PRIMEIRA ocorrência; sub-cabeçalhos repetidos são ignorados.
_NTE = re.compile(r"\b(?:NTE|N[ÚU]CLEO)\s*(\d{1,2})\s*[-–—]?\s*(?:SEDE\s*:\s*)?"
                  r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' .\-]{1,50}?)\s+"
                  r"(\d{1,3}(?:\.\d{3})+|\d{1,5})\b", re.I)
# Rótulo do NTE sem total (sub-cabeçalho repetido), com ou sem "SEDE:".
_NTE_LABEL = re.compile(r"\b(?:NTE|N[ÚU]CLEO)\s*(\d{1,2})\s*[-–—]?\s*(?:SEDE\s*:\s*)?",
                        re.I)

# Ruído que não é nome de cargo quando aparece isolado.
_CARGO_STOP = {"NIVEL MEDIO", "NIVEL SUPERIOR", "JURADO", "MESARIO", "ELEITOR"}

# Certezas em que o quadro é considerado reconstruído o bastante para gerar proposta.
PROPOSABLE_CERTAINTY = {"forte", "provavel"}


def _norm(text: str) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.upper().split())


def _qty(value: str) -> int:
    return int(value.replace(".", ""))


def _clean_cargo(raw: str) -> str | None:
    value = " ".join(raw.split())
    cut = _CARGO_CUT.search(value)
    if cut:
        value = value[:cut.start()]
    value = value.strip(" -–—,.;:()")
    if len(value) < 4 or len(value) > 90:
        return None
    if _norm(value) in _CARGO_STOP:
        return None
    if not re.search(r"[A-Za-zÀ-ÿ]{4}", value):
        return None
    return value


def cargo_candidates(blocks: list[dict], *, limit: int = 200) -> list[dict]:
    """Cargos declarados no texto do edital, com página e trecho literal.

    Padrões fortes ("função temporária de", "cargo de") têm precedência: só se nenhum for
    encontrado é que as menções fracas ("função de") são consideradas.
    """
    for pattern, strength in ((_STRONG_CARGO, "forte"), (_WEAK_CARGO, "fraca")):
        found = {}
        for index, block in enumerate(blocks):
            text = block.get("text") or ""
            if not isinstance(text, str):
                continue
            for match in pattern.finditer(text):
                value = _clean_cargo(match.group(1))
                if value is None:
                    continue
                key = _norm(value)
                if key in found:
                    continue
                # Offsets recalculados depois do corte, para casar com o trecho citado.
                start = match.start()
                quote = " ".join(text[start:match.end()].split())
                found[key] = {
                    "cargo": value, "page": block.get("page_number"),
                    "quote": quote, "block_index": index, "forca": strength,
                    "start_offset": start, "end_offset": start + len(quote),
                }
                if len(found) >= limit:
                    break
        if found:
            return list(found.values())
    return []


def scope_certainty(candidates: list[dict]) -> tuple[str, list[str]]:
    """Certeza da relação tabela→cargo a partir do escopo do edital."""
    ambiguidades = []
    if not candidates:
        return "sem_cargo", ["cargo não identificado no texto do edital"]
    if len(candidates) == 1:
        return "escopo_edital_unico", ambiguidades
    # Mais de um cargo: a tabela regional pode se referir a qualquer um deles.
    ambiguidades.append(
        "mais de um cargo no edital: a tabela regional não permite decidir qual")
    return "ambiguo", ambiguidades


def _locate(blocks: list[dict], page, quote: str) -> tuple[int | None, int | None]:
    """Índice do bloco e offset onde o trecho aparece, na página informada.

    Nunca devolve aproximação: se o trecho não estiver no bloco, devolve ``(None, None)`` e a
    proposta correspondente não é emitida.
    """
    if not quote:
        return None, None
    for index, block in enumerate(blocks):
        if block.get("page_number") != page:
            continue
        text = block.get("text") or ""
        position = text.find(quote)
        if position >= 0:
            return index, position
    return None, None


def _blank_subheaders(segment: str, sede: str) -> str:
    """Remove os sub-cabeçalhos repetidos do NTE, preservando os municípios.

    O sub-cabeçalho repete "NTE NN - SEDE: <sede>" sem total. A sede pode aparecer
    abreviada no cabeçalho ("F. DE SANTANA" × "FEIRA DE SANTANA"), então o consumo dos
    tokens da sede é por prefixo de palavra, nunca por quantidade fixa.
    """
    sede_words = _norm(sede).split()
    out = []
    position = 0
    for match in _NTE_LABEL.finditer(segment):
        if match.start() < position:
            continue
        out.append(segment[position:match.start()])
        cursor = match.end()
        consumed = 0
        for word in sede_words:
            token = re.match(r"\s*([A-Za-zÀ-ÿ\.]{1,20})\b", segment[cursor:])
            if not token:
                break
            if not _norm(token.group(1)).startswith(_norm(word).rstrip(".")[:2]):
                break
            cursor += token.end()
            consumed += 1
        if consumed == 0:
            cursor = match.end()
        out.append(" " * (cursor - match.start()))
        position = cursor
    out.append(segment[position:])
    return "".join(out)


def _municipios(segment: str, base: int, page_at, sede: str) -> list[dict]:
    """Pares nome/quantidade dentro do NTE, com página, trecho e offsets absolutos.

    Remove os sub-cabeçalhos repetidos e divide o restante nos números: cada quantidade
    fecha o nome que a antecede. A camada é **diagnóstica**: só é publicável quando a soma
    fecha e o chamador valida cada linha.
    """
    cleaned = _blank_subheaders(segment, sede)
    cleaned = re.sub(r"\bSEDE\b\s*:?", lambda m: " " * len(m.group(0)), cleaned, flags=re.I)
    rows = []
    cursor = 0
    parts = re.split(r"(\d{1,4})\b", cleaned)
    for index in range(1, len(parts), 2):
        prefix = parts[index - 1]
        nome = " ".join(prefix.split()).strip(" -–—,.;:")
        name_start = cursor + len(prefix) - len(prefix.lstrip())
        cursor += len(prefix)
        if nome and re.search(r"[A-Za-zÀ-ÿ]{3}", nome):
            words = nome.split()
            if len(words) <= 6 and not _norm(nome).startswith(("NTE", "NUCLEO")):
                quote = f"{nome} {parts[index]}"
                rows.append({"municipio": nome, "quantidade": _qty(parts[index]),
                             "page": page_at(base + name_start),
                             "quote": quote,
                             "start": base + name_start,
                             "end": base + cursor + len(parts[index])})
        cursor += len(parts[index])
    return rows


def _tables_with_ntes(report: dict) -> list[dict]:
    return [table for table in report["tabelas"] if table.get("ntes")]


def regional_breakdown(blocks: list[dict]) -> dict:
    """Distribuição por NTE e município, com página e trecho de cada linha.

    O quadro é contínuo entre páginas: o texto das páginas da tabela é concatenado e cada
    NTE é segmentado até a próxima linha de NTE (de número diferente). O sub-cabeçalho
    repetido do NTE fica dentro do segmento e é removido antes de ler os municípios.

    Com mais de um quadro contendo NTE, nada é escolhido automaticamente: a seleção fica
    ambígua e nenhum total é publicado.
    """
    report = table_continuity.continuity_report(blocks)
    tables = _tables_with_ntes(report)
    if not tables:
        return {"version": SCOPE_VERSION, "tabela": None, "ntes": [],
                "limitacao": "nenhum quadro com NTE identificado"}
    if len(tables) > 1:
        return {"version": SCOPE_VERSION, "tabela": None, "ntes": [],
                "total_ntes": 0, "soma_ntes": None,
                "ambiguidade": f"{len(tables)} quadros com NTE no documento; "
                               "seleção não automática",
                "limitacao": "mais de um quadro regional: nenhum total publicado"}
    table = tables[0]

    by_page = {}
    for block in blocks:
        page = block.get("page_number")
        if page is None:
            continue
        by_page.setdefault(page, []).append(block.get("text") or "")

    pieces, page_of_offset = [], []
    offset = 0
    for page in table["pages"]:
        text = " ".join(by_page.get(page, []))
        # Rodapé "Página N de M" não faz parte do quadro e contamina a leitura de números.
        text = re.sub(r"\bP[áa]gina\s*\d+\s*de\s*\d+\b", " ", text, flags=re.I)
        pieces.append(text)
        page_of_offset.append((offset, offset + len(text), page))
        offset += len(text) + 1
    joined = " ".join(pieces)
    # Só o TOTAL com número encerra o quadro; "TOTAL DE VAGAS" é o título do cabeçalho.
    total_marker = re.search(r"\bTOTAL\s+\d", joined)
    if total_marker:
        joined = joined[:total_marker.start()]

    def page_at(position: int):
        for start, end, page in page_of_offset:
            if start <= position < end:
                return page
        return table["pages"][-1] if table["pages"] else None

    occurrences = []
    for match in _NTE.finditer(joined):
        occurrences.append({"start": match.start(), "end": match.end(),
                            "nte": int(match.group(1)),
                            "sede": " ".join(match.group(2).split()),
                            "total": _qty(match.group(3)),
                            "quote": match.group(0), "page": page_at(match.start())})
    if not occurrences:
        return {"version": SCOPE_VERSION, "tabela": table, "ntes": [],
                "limitacao": "quadro sem linha de NTE legível"}

    # Totais: a primeira ocorrência de cada NTE (o sub-cabeçalho repete a linha sem total).
    primeira = {}
    for item in occurrences:
        primeira.setdefault(item["nte"], item)

    # Segmento: da primeira ocorrência do NTE até o próximo NTE de número diferente.
    segments = {}
    for item in primeira.values():
        nxt = next((other for other in occurrences
                    if other["start"] > item["start"] and other["nte"] != item["nte"]), None)
        limit = nxt["start"] if nxt else len(joined)
        segments[item["nte"]] = _municipios(joined[item["end"]:limit], item["end"],
                                            page_at, item["sede"])

    ntes = []
    for numero in sorted(primeira):
        item = primeira[numero]
        municipios = segments.get(numero, [])
        soma = sum(row["quantidade"] for row in municipios)
        block_index, start_offset = _locate(blocks, item["page"], item["quote"])
        ntes.append({
            "nte": numero, "sede": item["sede"], "total": item["total"],
            "page": item["page"], "block_index": block_index,
            "start_offset": start_offset, "quote": item["quote"],
            "municipios": municipios, "municipios_total": len(municipios),
            "soma_municipios": soma,
            "conflito": (soma != item["total"]) if municipios else None,
        })
    reconciliados = [item["nte"] for item in ntes if item["conflito"] is False]
    total_page = table.get("total_page")
    total_quote = table.get("total_quote")
    total_block_index, total_start = (_locate(blocks, total_page, total_quote)
                                      if total_quote else (None, None))
    return {"version": SCOPE_VERSION, "tabela": table, "ntes": ntes,
            "total_block_index": total_block_index,
            "total_start_offset": total_start,
            "total_quote": total_quote,
            "total_ntes": len(ntes),
            "soma_ntes": sum(item["total"] for item in ntes),
            "municipios_reconciliados": reconciliados,
            # Nome deliberadamente estreito: confere a SOMA, não cada linha.
            "soma_municipios_confere": bool(ntes) and len(reconciliados) == len(ntes),
            "limitacao_municipios": (
                None if ntes and len(reconciliados) == len(ntes) else
                "a soma dos municípios não fecha com o total de todos os NTEs; a camada de "
                "município é diagnóstica e não deve ser publicada como fato")}


def scope_report(db_path, version_id: str) -> dict:
    """Relatório completo: tabela contínua + cargo do escopo + distribuição regional."""
    from contextlib import closing

    from radar.document_store import connect_documents, is_readable_schema

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute(
            "SELECT d.id, d.title, d.contest_id, d.role_id FROM versoes_documento v "
            "JOIN documentos d ON d.id=v.document_id WHERE v.id=?", (version_id,)).fetchone()
        if not row:
            raise ValueError("versão inexistente")
        blocks = [{"page_number": page, "text": text} for page, text in conn.execute(
            "SELECT page_number,text FROM blocos_documento WHERE version_id=? "
            "ORDER BY page_number,start_offset", (version_id,))]
    document_id, title, contest_id, role_id = row
    report = regional_breakdown(blocks)
    candidates = cargo_candidates(blocks)
    certeza, ambiguidades = scope_certainty(candidates)
    if report.get("ambiguidade"):
        ambiguidades.append(report["ambiguidade"])
    table = report["tabela"] or {}
    if table.get("header_page") and not candidates:
        ambiguidades.append("quadro sem cargo e edital sem cargo identificável")
    total = table.get("total")
    soma = report.get("soma_ntes")
    if total is not None and soma is not None and total != soma:
        ambiguidades.append(f"TOTAL {total} difere da soma dos NTEs {soma}")
    if table.get("ambiguidades"):
        ambiguidades.extend(table["ambiguidades"])
    return {
        "version": SCOPE_VERSION, "document_id": document_id, "version_id": version_id,
        "title": title, "contest_id": contest_id, "document_role_id": role_id,
        "tabela": table,
        "certeza_tabela": table.get("certeza"),
        "total_block_index": report.get("total_block_index"),
        "total_start_offset": report.get("total_start_offset"),
        "total_quote": report.get("total_quote"),
        "cargo_candidatos": candidates,
        "certeza_escopo": certeza,
        "cargo_do_escopo": candidates[0] if certeza == "escopo_edital_unico" else None,
        "ntes": report["ntes"],
        "total_ntes": report.get("total_ntes", 0),
        "municipios_reconciliados": report.get("municipios_reconciliados", []),
        "soma_municipios_confere": report.get("soma_municipios_confere", False),
        "soma_ntes": soma,
        "total_publicado": total,
        "ambiguidades": ambiguidades,
        "limitacao": ("Relação cargo↔NTE é candidata estrutural, não fato confirmado. NTE é "
                      "regional administrativa; não é município, local de prova nem lotação. "
                      "Nenhuma modalidade é derivada do total."),
        "limitacao_municipios": report.get("limitacao_municipios"),
    }


def proposals_from_scope(report: dict, *, label_prefix: str = "",
                         include_ntes: bool = False) -> list[dict]:
    """Propostas de `vagas_total_publicado` a partir do quadro regional.

    Por padrão emite **apenas o TOTAL do quadro**: um total de NTE é recorte regional e não
    pode ser confundido com o total do concurso. ``include_ntes=True`` emite os totais de NTE
    como recortes, sempre marcados como tal. Nada é emitido quando a certeza do quadro não é
    `forte`/`provavel` ou quando o trecho não é localizável no bloco.
    """
    table = report.get("tabela") or {}
    certeza = table.get("certeza")
    if certeza not in PROPOSABLE_CERTAINTY:
        return []
    cargo = report.get("cargo_do_escopo")
    escopo = (f"{label_prefix}{cargo['cargo']}" if cargo
              else "cargo do escopo não identificado")
    pages = f"p{table.get('header_page')}–p{table.get('total_page')}"
    base = (f"total agregado publicado (ampla + negros + pcd); não distribuir por modalidade; "
            f"quadro {pages} ({certeza}); {escopo}")
    proposals = []
    if include_ntes:
        for item in report.get("ntes", []):
            if item.get("block_index") is None or item.get("start_offset") is None:
                continue
            proposals.append({
                "contest_id": report["contest_id"], "role_id": None,
                "field_name": "vagas_total_publicado",
                "value_json": json.dumps(item["total"]), "value_type": "integer",
                "extraction_method": METHOD_TOTAL,
                "ambiguity_reason": (f"recorte do NTE {item['nte']:02d} - {item['sede']} "
                                     f"(não é o total do concurso); {base}"),
                "evidence": {"block_index": item["block_index"], "quote": item["quote"],
                             "start_offset": item["start_offset"],
                             "end_offset": item["start_offset"] + len(item["quote"])},
            })
    total = report.get("total_publicado")
    if total is not None and report.get("total_block_index") is not None:
        quote = table.get("total_quote") or f"TOTAL {total}"
        position = report.get("total_start_offset")
        if position is not None:
            proposals.append({
                "contest_id": report["contest_id"], "role_id": None,
                "field_name": "vagas_total_publicado",
                "value_json": json.dumps(total), "value_type": "integer",
                "extraction_method": METHOD_TOTAL,
                "ambiguity_reason": (f"TOTAL do quadro ({report.get('total_ntes')} NTEs) — "
                                     f"{base}"),
                "evidence": {"block_index": report["total_block_index"], "quote": quote,
                             "start_offset": position,
                             "end_offset": position + len(quote)},
            })
    return proposals
