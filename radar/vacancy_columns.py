"""Quadros de vagas com várias modalidades em colunas (PDF posicional).

Dois layouts reais motivaram o módulo:

1. **Quadro largo com siglas** (ex.: SEDUC-PA, Anexo II): cabeçalho com uma sigla por
   coluna (``AC PcD PP PI PQ PPIQ PI/PQ Total``) repetido a cada página, células de texto
   multilinha e linhas de totalização por regional. A leitura usa a **posição** das
   palavras no PDF (cabeçalho ancora as colunas), porque o texto achatado perde a célula.
2. **Quadro com notação de reserva** (ex.: TJAP): cabeçalho escrito por extenso e células
   ``10+CR`` / ``CR*``. A leitura é sequencial, mas a notação é interpretada por
   `modality_legend.cr_notation`.

Regras que o módulo garante:

- categoria **unificada** (PPIQ, PI/PQ) nunca vira vaga exclusiva indígena;
- ``CR`` não vira zero nem vaga imediata;
- total agregado não é distribuído entre modalidades;
- linha cuja soma não fecha mantém os valores publicados e registra o conflito;
- a evidência é o trecho literal do bloco armazenado, com offsets exatos;
- sem PDF local (ou sem a biblioteca), o quadro largo não é lido: fica pendente.
"""

from __future__ import annotations

import json
import re

from radar import modality_legend

VERSION = "quadro_colunas_v1"

# Campos persistidos por linha (o restante das colunas fica no relatório e na evidência).
FIELD_BY_SIGLA = {
    "Total": "immediate_vacancies",
    "PI": "indigenous_vacancies",
    "PPIQ": "unified_ppiq_vacancies",
    "PI/PQ": "unified_pi_pq_vacancies",
}

# Cabeçalho do quadro largo: siglas na ordem publicada.
WIDE_HEADER = ("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ", "Total")

# Faixas horizontais das colunas de identificação (x em pontos do PDF).
DEFAULT_LABEL_BANDS = (
    ("DRE", 0, 80),
    ("MUN", 80, 150),
    ("CARGO", 150, 235),
    ("FORM", 235, 292),
    ("ESC", 292, 345),
)

_HEADER_LABELS = {"DRE", "Municípios/", "Distritos", "Cargo", "Formação", "Escolaridade"}
_TOTAL_PREFIX = "TOTAL"


def _key(text: str) -> str:
    return modality_legend.normalize(text).replace(" ", "")


def page_words(pdf_path, page_number: int) -> list[dict] | None:
    """Palavras com caixa delimitadora na página; ``None`` se o PDF não está disponível.

    Aceita caminho do arquivo ou os bytes do PDF (ingestão recém-baixada).
    """
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - dependência declarada no projeto
        return None
    try:
        if isinstance(pdf_path, (bytes, bytearray)):
            document = pymupdf.open(stream=bytes(pdf_path), filetype="pdf")
        else:
            document = pymupdf.open(str(pdf_path))
    except Exception:
        return None
    try:
        if not 1 <= int(page_number) <= document.page_count:
            return None
        page = document[page_number - 1]
        height = page.rect.height
        words = []
        for x0, y0, x1, y1, text, *_ in page.get_text("words"):
            if y1 >= height - 40:  # rodapé (número da página) não é célula
                continue
            words.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "text": text})
        return words
    finally:
        document.close()


def _header(words) -> dict | None:
    """Âncoras do cabeçalho largo, na ordem publicada, ou ``None``."""
    anchors = {}
    for word in words:
        if word["text"] in WIDE_HEADER and word["text"] not in anchors:
            anchors[word["text"]] = word
    if len(anchors) != len(WIDE_HEADER):
        return None
    # As siglas do cabeçalho ficam na mesma linha. Texto corrido que cita as mesmas
    # palavras em linhas diferentes (ex.: Anexo II-A) não é cabeçalho de quadro.
    tops = [anchor["y0"] for anchor in anchors.values()]
    if max(tops) - min(tops) > 6:
        return None
    top = min(anchor["y0"] for anchor in anchors.values())
    bottom = max(anchor["y1"] for anchor in anchors.values())
    centers = [(anchors[name]["x0"] + anchors[name]["x1"]) / 2 for name in WIDE_HEADER]
    bounds = [(centers[i] + centers[i + 1]) / 2 for i in range(len(centers) - 1)]
    start = centers[0] - (centers[1] - centers[0]) / 2
    return {"top": top, "bottom": bottom, "centers": centers, "bounds": bounds,
            "start": start, "anchors": anchors}


def _column(word, header) -> str | None:
    center = (word["x0"] + word["x1"]) / 2
    if center < header["start"]:
        return "LABEL"
    for index, name in enumerate(WIDE_HEADER):
        low = header["bounds"][index - 1] if index else header["start"]
        high = header["bounds"][index] if index < len(header["bounds"]) else 10_000
        if low <= center < high:
            return name
    return None


def _label_band(x, bands):
    for name, low, high in bands:
        if low <= x < high:
            return name
    return None


def _line_blocks(items, gap=6):
    """Blocos de linhas contíguas da mesma coluna (célula multilinha)."""
    blocks = []
    for item in sorted(items, key=lambda value: (value[0], value[1])):
        if blocks and item[0] - blocks[-1][-1][0] <= gap:
            blocks[-1].append(item)
        else:
            blocks.append([item])
    return blocks


def _row_anchors(words, header) -> list[float]:
    """Centros verticais das linhas de dados, ancorados em qualquer coluna numérica.

    Ancorar só na primeira coluna perderia uma linha cuja célula inicial viesse vazia
    (ou com marcador de zero) e engoliria o rótulo dela na linha anterior.
    """
    numeric = [word for word in words
               if word["y0"] > header["top"] and _column(word, header) in WIDE_HEADER
               and re.fullmatch(r"\d{1,5}", word["text"])]
    ys = sorted({round(word["y0"], 1) for word in numeric})
    clusters: list[list[float]] = []
    for y in ys:
        if clusters and y - clusters[-1][-1] <= 3:
            clusters[-1].append(y)
        else:
            clusters.append([y])
    return [sum(cluster) / len(cluster) for cluster in clusters]


def _is_total_row(words, anchor: float) -> bool:
    for word in words:
        if (word["text"].upper().startswith(_TOTAL_PREFIX)
                and abs(word["y0"] - anchor) <= 6 and word["x0"] < 150):
            return True
    return False


def assemble_rows(words, *, bands=DEFAULT_LABEL_BANDS) -> dict | None:
    """Linhas do quadro largo a partir das palavras posicionadas de uma página.

    Devolve ``{"header": [...], "rows": [...]}``; cada linha traz ``values`` (na ordem do
    cabeçalho), ``cargo``/``formacao``/``escolaridade``/``dre`` e ``total`` (bool).
    ``None`` quando a página não tem o cabeçalho completo.
    """
    header = _header(words)
    if header is None:
        return None
    anchors = _row_anchors(words, header)
    if not anchors:
        return {"header": list(WIDE_HEADER), "rows": [], "leading": {}}
    totals = {anchor for anchor in anchors if _is_total_row(words, anchor)}
    data_anchors = [anchor for anchor in anchors if anchor not in totals]
    rows = []
    for anchor in anchors:
        cells = {name: [] for name in WIDE_HEADER}
        label = {name: [] for name, _, _ in bands}
        for word in words:
            if word["y0"] <= header["top"] or word["text"] in _HEADER_LABELS:
                continue
            column = _column(word, header)
            if column is None:
                continue
            center = (word["y0"] + word["y1"]) / 2
            if column == "LABEL":
                if anchor in totals:
                    # A linha de totalização traz o próprio rótulo na mesma linha.
                    if abs(center - anchor) <= 6:
                        band = _label_band(word["x0"], bands)
                        if band:
                            label[band].append((word["y0"], word["x0"], word["text"]))
                    continue
                if center < anchors[0] - 8:
                    # Célula que continua a última linha da página anterior: pertence a ela.
                    continue
                band = _label_band(word["x0"], bands)
                if band:
                    label[band].append((word["y0"], word["x0"], word["text"]))
            elif abs(center - anchor) <= 16:
                cells[column].append((word["y0"], word["x0"], word["text"]))
        # Célula multilinha: o bloco (linhas contíguas da mesma coluna) pertence à linha
        # cujo número está no centro do bloco. Evita cortar "Assistente de Gestão …".
        assigned = {name: list(label[name]) for name, _, _ in bands}
        for name in ("CARGO", "FORM", "ESC"):
            assigned[name] = []
            for block in _line_blocks(label[name]):
                center = (block[0][0] + block[-1][0]) / 2
                if not data_anchors:
                    continue
                target = min(data_anchors, key=lambda value: abs(value - center))
                if abs(target - center) > 60 or abs(target - anchor) > 0.01:
                    continue
                assigned[name].extend(block)
        label = assigned

        def text_of(items):
            return " ".join(text for _, _, text in sorted(items))

        rows.append({
            "anchor": anchor,
            "total": anchor in totals,
            "values": [text_of(cells[name]) or None for name in WIDE_HEADER],
            "cargo": text_of(label["CARGO"]),
            "formacao": text_of(label["FORM"]),
            "escolaridade": text_of(label["ESC"]),
            "dre": text_of(label["DRE"]),
            "municipios": text_of(label["MUN"]),
        })
    return {"header": list(WIDE_HEADER), "rows": rows,
            "leading": _leading_label(words, header, anchors[0], bands)}


def _leading_label(words, header, first_anchor, bands):
    """Palavras de célula acima da primeira linha: continuação da linha da página anterior."""
    leading = {name: [] for name in ("CARGO", "FORM", "ESC")}
    for word in words:
        if word["y0"] <= header["top"] or word["text"] in _HEADER_LABELS:
            continue
        band = _label_band(word["x0"], bands)
        if band in leading and word["y1"] <= first_anchor - 8:
            leading[band].append((word["y0"], word["x0"], word["text"]))
    return leading


def _integers(values):
    """Valores inteiros na ordem do cabeçalho; ``None`` quando alguma célula não é número.

    O marcador ``-`` é zero explícito da banca (mesma leitura de `cr_notation`).
    """
    numbers = []
    for value in values:
        if value is None:
            return None
        text = value.strip()
        if text in ("-", "–", "—"):
            numbers.append(0)
            continue
        if not re.fullmatch(r"\d{1,5}", text):
            return None
        numbers.append(int(text))
    return numbers


_CONNECTORS = {"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o"}
_LEVELS = re.compile(r"^N[íi]vel\s+(Superior|M[ée]dio|Fundamental|T[ée]cnico)\b", re.I)


def label_incomplete(cargo: str, formacao: str, escolaridade: str) -> bool:
    """Cargo não identificável: vazio ou cortado pela quebra de página.

    A célula que atravessa a página deixa a escolaridade truncada ("Nível" sem o nível) e
    o cargo terminando em conectivo ("Especialista em"). Um cargo que termina em conectivo
    com escolaridade completa apenas transbordou para a coluna de formação (caso legítimo
    de nome longo, ex.: "Analista de Gestão Governamental e Administração").
    """
    combined = " ".join(part for part in (cargo, formacao) if part).strip()
    if not combined:
        return True
    cargo_words = (cargo or "").split()
    ends_connector = bool(cargo_words) and (
        cargo_words[-1].lower().strip(",;") in _CONNECTORS)
    return ends_connector and schooling_incomplete(escolaridade)


def schooling_incomplete(escolaridade: str) -> bool:
    """Escolaridade que não é um nível publicado (célula cortada na quebra de página)."""
    return _LEVELS.match(" ".join((escolaridade or "").split())) is None


def compose_label(cargo: str, formacao: str, dre: str) -> str:
    """Rótulo do escopo: cargo, formação e regional, sem separador que o review trunque.

    ``review._label_of`` corta o rótulo em ``" - "``; um cargo como "Educação Especial -
    AEE" perderia o sufixo e dois cargos distintos virariam o mesmo escopo. Por isso os
    travessões internos são normalizados para espaço antes de compor o rótulo.
    """
    def clean(text):
        return re.sub(r"\s+[-–—]\s+", " ", " ".join((text or "").split())).strip()

    cargo, formacao = clean(cargo), clean(formacao)
    words = cargo.split()
    if words and words[-1].lower().strip(",;") in _CONNECTORS:
        core = " ".join(part for part in (cargo, formacao) if part)
    else:
        core = " / ".join(part for part in (cargo, formacao) if part)
    regional = re.sub(r"^DRE\s*[-–]\s*", "", (dre or "").strip())
    if regional:
        core = f"{core} / DRE {regional}" if core else f"DRE {regional}"
    return core


def locate_quote(page_text: str, cargo: str, tail: str, *, limit=260, skip=None):
    """Offsets do trecho literal da linha no texto do bloco armazenado.

    A mesma sequência numérica aparece em várias linhas; a âncora é o rótulo publicado
    antes dela. O rótulo montado pode ter palavra a mais (célula da página anterior) ou a
    menos (célula que continua na página seguinte), por isso são testados prefixos e
    sufixos do rótulo, vencendo o mais longo que existir antes da cauda. ``skip`` evita
    reutilizar o trecho de uma linha já emitida (linhas idênticas em regionais diferentes).
    """
    if not tail:
        return None
    words = (cargo or "").split()
    candidates = []
    for take in range(len(words), 0, -1):
        candidates.append(" ".join(words[:take]))
    for cut in range(1, len(words)):
        candidates.append(" ".join(words[cut:]))
    skip = skip or set()
    best = None
    best_length = -1
    start = 0
    while True:
        index = page_text.find(tail, start)
        if index < 0:
            break
        begin = max(0, index - 240)
        window = page_text[begin:index]
        for candidate in candidates:
            position = window.rfind(candidate)
            if position < 0:
                continue
            row_start = begin + position
            if index + len(tail) - row_start > limit or row_start in skip:
                continue
            length = len(candidate)
            if length > best_length:
                best, best_length = (row_start, index + len(tail), candidate), length
            break
        start = index + 1
    return best


def _proposal(contest_id, field, value, *, block_index, quote, start, end, page,
              header, label, reason):
    return dict(
        contest_id=contest_id, role_id=None, field_name=field,
        value_json=json.dumps(value),
        value_type="integer" if isinstance(value, int) else "string",
        extraction_method="quadro-colunas-pdf",
        ambiguity_reason=reason,
        evidence=dict(block_index=block_index, quote=quote, start_offset=start,
                      end_offset=end, page_number=page, header=header,
                      section=None, role_label=label))


def _region_marker(text: str, region: str, before: int, limit=1200):
    """Início do marcador da regional antes da linha (para desambiguar trecho repetido)."""
    if not region:
        return None
    for candidate in (f"DRE - {region}", f"DRE – {region}", f"DRE- {region}",
                      f"TOTAL – DRE - {region}", f"TOTAL - DRE - {region}"):
        index = text.rfind(candidate, 0, before)
        if index >= 0 and before - index <= limit:
            return index
    return None


def _region_name(row) -> str:
    """Nome da regional publicado na linha de totalização."""
    combined = " ".join(part for part in (row["dre"], row["municipios"]) if part)
    name = re.sub(r"^TOTAL\b", "", combined, flags=re.I).strip()
    name = re.sub(r"^[^\wÀ-ÿ]+", "", name)
    name = re.sub(r"^DRE\b", "", name, flags=re.I).strip()
    return re.sub(r"^[^\wÀ-ÿ]+", "", name).strip()


def parse_wide_table(blocks, contest_id: str, *, label_prefix: str, pdf_path=None,
                     definitions=None) -> dict:
    """Lê o quadro largo e devolve propostas candidatas + relatório auditável.

    ``definitions`` são as definições de sigla do próprio documento
    (`modality_legend.parse_definitions`). Sem definição da sigla, nenhuma proposta é
    gerada para ela: a semântica não pode ser presumida.
    """
    definitions = definitions or {}
    header_text = " | ".join(WIDE_HEADER)
    proposals, rows_report, pendencias = [], [], []
    emitted_quotes = set()
    used_starts = {}
    page_index = {}
    for index, block in enumerate(blocks):
        page = block.get("page_number")
        if isinstance(page, int):
            page_index.setdefault(page, index)
    if pdf_path is None:
        pendencias.append({"causa": "pdf_ausente",
                           "detalhe": "quadro largo exige o PDF local para ler colunas"})
        return {"version": VERSION, "proposals": [], "rows": [], "regions": [],
                "grand_total": None, "pendencias": pendencias}

    # Passo 1: linhas de todas as páginas, na ordem do documento.
    # O quadro largo termina no Anexo II-A (matriz de convocação): a matriz descreve a
    # ordem de chamada, não publica vagas novas. A página do quadro é reconhecida pelo
    # cabeçalho completo numa única linha — o sumário que cita "Anexo II" não conta.
    tables = []
    for page in sorted(page_index):
        words = page_words(pdf_path, page)
        if not words:
            continue
        assembled = assemble_rows(words)
        if assembled is None:
            continue
        tables.append((page, assembled))
    end_page = None
    for page, _ in tables:
        text = blocks[page_index[page]].get("text") or ""
        if re.search(r"ANEXO\s+II\s*[-–]\s*A\b", text, re.I):
            end_page = page
            break
    flat, leading_by_page = [], {}
    for page_number, assembled in tables:
        if end_page is not None and page_number >= end_page:
            continue
        leading_by_page[page_number] = assembled["leading"]
        for row in assembled["rows"]:
            flat.append({"page": page_number, "row": row,
                         "text": blocks[page_index[page_number]]["text"],
                         "numbers": _integers(row["values"])})
    # Só a última linha de dados de uma página pode continuar na página seguinte.
    for position, item in enumerate(flat):
        following = flat[position + 1] if position + 1 < len(flat) else None
        item["last"] = following is None or following["page"] != item["page"]

    # Passo 2: regionais fechadas pela linha de totalização; o nome vem do próprio total.
    regions, current = [], {"name": None, "items": [], "total": None}
    grand_total = None
    for item in flat:
        row, numbers = item["row"], item["numbers"]
        if not row["total"]:
            current["items"].append(item)
            continue
        if numbers is None:
            pendencias.append({"causa": "total_sem_numero", "page": item["page"],
                               "valores": row["values"]})
            continue
        name = _region_name(row)
        if "GERAL" in name.upper():
            grand_total = numbers
            continue
        current["total"] = numbers
        current["name"] = name or current["name"]
        regions.append(current)
        current = {"name": None, "items": [], "total": None}
    if current["items"]:
        regions.append(current)

    def emit(item, region_name):
        row, numbers, page, text = item["row"], item["numbers"], item["page"], item["text"]
        if not row["cargo"]:
            pendencias.append({"causa": "linha_sem_cargo", "page": page,
                               "valores": row["values"]})
            return
        if numbers is None:
            pendencias.append({"causa": "celula_nao_numerica", "page": page,
                               "cargo": row["cargo"], "valores": row["values"]})
            return
        note = ""
        if label_incomplete(row["cargo"], row["formacao"], row["escolaridade"]):
            if not item.get("last"):
                # Não é a última linha da página: a célula não continua na seguinte.
                pendencias.append({"causa": "rotulo_incompleto", "page": page,
                                   "cargo": row["cargo"], "valores": row["values"]})
                return
            # A célula continua no topo da página seguinte: costura o rótulo, mantendo a
            # evidência na página em que os números foram publicados.
            following = leading_by_page.get(page + 1) or {}
            for name, source in (("cargo", "CARGO"), ("formacao", "FORM"),
                                 ("escolaridade", "ESC")):
                extra = " ".join(text_ for _, _, text_ in sorted(following.get(source, [])))
                if extra:
                    row[name] = " ".join(part for part in (row[name], extra) if part)
            if label_incomplete(row["cargo"], row["formacao"], row["escolaridade"]):
                pendencias.append({"causa": "rotulo_incompleto", "page": page,
                                   "cargo": row["cargo"], "valores": row["values"]})
                return
            note = " [rotulo completado na pagina seguinte]"
        tail = " ".join(row["values"])
        prefix = " ".join(part for part in (row["cargo"], row["formacao"],
                                            row["escolaridade"]) if part)
        used = used_starts.setdefault(page, set())
        located = locate_quote(text, prefix, tail, skip=used)
        if located is None:
            pendencias.append({"causa": "trecho_nao_localizado", "page": page,
                               "cargo": row["cargo"], "valores": row["values"]})
            return
        start, end, matched = located
        if matched != prefix:
            # Palavra avulsa da linha anterior: o rótulo publicado começa depois dela.
            dropped = len(prefix.split()) - len(matched.split())
            words = row["cargo"].split()
            if 0 < dropped <= len(words):
                row["cargo"] = " ".join(words[dropped:]) or row["cargo"]
        label = compose_label(row["cargo"], row["formacao"], region_name)
        quote = text[start:end]
        key = (page, quote)
        if key in emitted_quotes and region_name:
            # Linha textualmente idêntica em outra regional: estende a evidência até o
            # marcador da regional para que o trecho identifique a linha publicada.
            marker = _region_marker(text, region_name, start)
            if marker is not None:
                start = marker
                quote = text[start:end]
                key = (page, quote)
        sums = sum(numbers[:7])
        consistent = sums == numbers[7]
        reason = label_prefix + label + note
        if schooling_incomplete(row["escolaridade"]):
            pendencias.append({"causa": "escolaridade_incompleta", "page": page,
                               "cargo": row["cargo"]})
        if not consistent:
            reason = (reason + " [conflito aritmetico: soma das modalidades "
                      f"{sums} != total {numbers[7]}]")
            pendencias.append({"causa": "soma_divergente", "page": page,
                               "cargo": row["cargo"], "soma": sums,
                               "total": numbers[7], "quote": quote})
        values = dict(zip(WIDE_HEADER, numbers))
        for sigla, field in FIELD_BY_SIGLA.items():
            if sigla not in values:
                continue
            if sigla != "Total":
                semantic = modality_legend.kind(definitions, sigla)
                if semantic == "unknown":
                    pendencias.append({"causa": "sigla_sem_definicao",
                                       "page": page, "sigla": sigla})
                    continue
                if sigla in ("PPIQ", "PI/PQ") and semantic != "unified":
                    # Coluna unificada sem definição de unificação: não persistir como
                    # exclusiva nem como unificada.
                    pendencias.append({"causa": "unificada_sem_definicao",
                                       "page": page, "sigla": sigla})
                    continue
                if sigla == "PI" and semantic != "exclusive":
                    pendencias.append({"causa": "pi_nao_exclusiva",
                                       "page": page, "sigla": sigla})
                    continue
            proposals.append(_proposal(
                contest_id, field, values[sigla], block_index=page_index[page],
                quote=quote, start=start, end=end, page=page,
                header=header_text, label=label, reason=reason))
        rows_report.append({"page": page, "cargo": row["cargo"],
                            "formacao": row["formacao"], "dre": region_name,
                            "escolaridade": row["escolaridade"],
                            "valores": values, "soma": sums,
                            "consistente": consistent, "quote": quote})
        key = (page, quote)
        if key in emitted_quotes:
            # Mesmo trecho e mesma regional: o armazenamento deduplica por evidência.
            pendencias.append({"causa": "linha_repetida_no_bloco", "page": page,
                               "cargo": row["cargo"], "regional": region_name,
                               "valores": values})
        emitted_quotes.add(key)
        used.add(start)

    # Passo 3: relatório das regionais e propostas por linha.
    region_report = []
    for region in regions:
        rows_numbers = [item["numbers"] for item in region["items"] if item["numbers"]]
        if region["total"] is None:
            region_report.append({"regiao": region["name"], "linhas": len(rows_numbers),
                                  "consistente": None,
                                  "motivo": "sem linha de totalização"})
        else:
            sums = [sum(row[column] for row in rows_numbers) for column in range(8)]
            closed = sums == region["total"]
            region_report.append({"regiao": region["name"], "linhas": len(rows_numbers),
                                  "soma": sums, "total": region["total"],
                                  "consistente": closed})
            if not closed:
                # A regional não fecha: o conflito precisa chegar à superfície, não só ao
                # relatório detalhado.
                pendencias.append({"causa": "regional_divergente",
                                   "regiao": region["name"], "soma": sums,
                                   "total": region["total"]})
        for item in region["items"]:
            emit(item, region["name"])

    grand = None
    if grand_total is not None:
        closed = [region["total"] for region in regions if region["total"] is not None]
        sums = [sum(total[column] for total in closed) for column in range(8)]
        grand = {"total": grand_total, "soma_regioes": sums,
                 "consistente": sums == grand_total}
        if not grand["consistente"]:
            pendencias.append({"causa": "total_geral_divergente",
                               "soma_regioes": sums, "total": grand_total})
    return {"version": VERSION, "proposals": proposals, "rows": rows_report,
            "regions": region_report, "grand_total": grand, "pendencias": pendencias}


# Cabeçalhos escritos por extenso (quadro com notação de reserva).
NOTATION_HEADER = (
    ("AMPLA", re.compile(r"ampla\s+concorr", re.I)),
    ("PCD", re.compile(r"(?:candidat|pessoas?|pessoa)[a-z]*\s+com\s+defici|\bPcD\b", re.I)),
    ("PP", re.compile(r"negros?|negras?|pretas?\s+e\s+pardas?", re.I)),
    ("PI", re.compile(r"ind[íi]genas?", re.I)),
    ("PQ", re.compile(r"quilombolas?", re.I)),
    ("TOTAL", re.compile(r"total\s+de\s+vagas", re.I)),
)
_NOTATION_CELL = re.compile(r"(?<![\w/.,])(\d{1,4}\s*\+\s*CR|\d{1,4}|CR\*?)(?![\w/.,])",
                            re.I)


def _notation_header(text: str, start: int):
    """Cabeçalho completo do quadro por extenso, na ordem canônica.

    Todas as modalidades precisam estar presentes e na ordem publicada: com uma coluna
    ausente, o alinhamento desloca e o valor de uma modalidade seria atribuído a outra.
    """
    window = text[start:start + 520]
    found = []
    for name, pattern in NOTATION_HEADER:
        match = pattern.search(window)
        if match:
            found.append((match.start(), match.end(), name))
    if len(found) != len(NOTATION_HEADER):
        return None, None
    found.sort()
    if found[-1][0] - found[0][0] > 420:
        return None, None
    names = [name for _, _, name in found]
    if names != [name for name, _ in NOTATION_HEADER]:
        return None, None
    return names, start + found[-1][1]


def parse_notation_table(blocks, contest_id: str, *, label_prefix: str) -> dict:
    """Quadro com cabeçalho por extenso e células ``N+CR`` / ``CR*`` (ex.: TJAP).

    Emite apenas quantidades **publicadas**. ``CR*`` gera uma proposta de notação
    (natureza reserva, asterisco presente) e uma pendência quando a nota do asterisco não
    é localizada; nunca gera número de vaga imediata.
    """
    proposals, rows_report, pendencias = [], [], []
    for index, block in enumerate(blocks):
        if block.get("page_number") is None:
            continue
        text = block["text"]
        position = 0
        while position < len(text):
            anchor = re.search(r"quadro\s+de\s+vagas", text[position:], re.I)
            if anchor is None:
                break
            start = position + anchor.start()
            names, data_start = _notation_header(text, start)
            if names is None:
                found = sum(1 for _, pattern in NOTATION_HEADER
                            if pattern.search(text[start:start + 520]))
                if found >= 3:
                    pendencias.append({"causa": "cabecalho_incompleto",
                                       "page": block.get("page_number"),
                                       "modalidades_encontradas": found,
                                       "quote": text[start:start + 160]})
                position = start + 1
                continue
            segment = text[data_start:data_start + 400]
            cells = list(_NOTATION_CELL.finditer(segment))
            if len(cells) < len(names):
                position = data_start
                continue
            head = cells[:len(names)]
            label = " ".join(segment[:head[0].start()].split()).strip(" |;,-")
            if not label or len(label) > 120:
                position = data_start
                continue
            parsed = [modality_legend.cr_notation(match.group(1)) for match in head]
            if any(item is None for item in parsed):
                position = data_start
                continue
            label_raw = segment[:head[0].start()]
            label_start = len(label_raw) - len(label_raw.lstrip())
            quote_start = data_start + label_start
            quote_end = data_start + head[-1].end()
            quote = text[quote_start:quote_end]
            by_name = dict(zip(names, parsed))
            immediate = {name: item["immediate"] for name, item in by_name.items()}
            known = {name: value for name, value in immediate.items()
                     if name != "TOTAL" and value is not None}
            total = immediate.get("TOTAL")
            consistent = total is not None and sum(known.values()) == total
            reason = label_prefix + label
            if not consistent:
                reason = (reason + f" [conflito aritmetico: modalidades "
                          f"{sum(known.values())} != total {total}]")
                pendencias.append({"causa": "soma_divergente", "page": block["page_number"],
                                   "cargo": label, "soma": sum(known.values()),
                                   "total": total, "quote": quote})
            if total is not None:
                proposals.append(_proposal(
                    contest_id, "immediate_vacancies", total, block_index=index,
                    quote=quote, start=quote_start, end=quote_end,
                    page=block["page_number"], header=" | ".join(names), label=label,
                    reason=reason))
            indigenous = by_name.get("PI")
            if indigenous:
                if indigenous["immediate"] is not None:
                    proposals.append(_proposal(
                        contest_id, "indigenous_vacancies", indigenous["immediate"],
                        block_index=index, quote=quote, start=quote_start,
                        end=quote_end, page=block["page_number"],
                        header=" | ".join(names), label=label, reason=reason))
                if indigenous["reserve"]:
                    # Reserva publicada sem quantidade: a notação é o dado, não um número.
                    # "0+CR" mantém as duas informações (zero imediato e reserva).
                    proposals.append(_proposal(
                        contest_id, "indigenous_reserve_notation", indigenous["raw"],
                        block_index=index, quote=quote, start=quote_start,
                        end=quote_end, page=block["page_number"],
                        header=" | ".join(names), label=label, reason=reason))
                    note = modality_legend.asterisk_note(text)
                    if indigenous["asterisk"] and note is None:
                        pendencias.append({"causa": "asterisco_sem_nota",
                                           "page": block["page_number"],
                                           "notacao": indigenous["raw"], "quote": quote})
            rows_report.append({"page": block["page_number"], "cargo": label,
                                "celulas": {name: item["raw"] for name, item in
                                            by_name.items()},
                                "quote": quote, "consistente": consistent})
            position = quote_end
    return {"version": VERSION, "proposals": proposals, "rows": rows_report,
            "regions": [], "pendencias": pendencias}


def report(db_path, *, contest_id=None, version_id=None) -> dict:
    """Relatório do quadro de vagas de uma versão já armazenada (somente leitura).

    Reúne o quadro largo (colunas) e o quadro com notação de reserva, com as linhas, as
    regionais, as pendências e as propostas candidatas. Nada é gravado.
    """
    from contextlib import closing
    from pathlib import Path
    from radar.document_store import connect_documents, is_readable_schema

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        if version_id is None:
            row = conn.execute(
                "SELECT v.id FROM versoes_documento v JOIN documentos d ON d.id=v.document_id "
                "WHERE (? IS NULL OR d.contest_id=?) AND d.tipo_documental IN "
                "('edital_abertura','edital_retificado') "
                "ORDER BY CASE d.tipo_documental WHEN 'edital_retificado' THEN 0 ELSE 1 END, "
                "d.published_at DESC, v.fetched_at DESC LIMIT 1",
                (contest_id, contest_id)).fetchone()
            if row is None:
                raise ValueError("versão não encontrada")
            version_id = row[0]
        meta = conn.execute(
            "SELECT d.contest_id, d.title, v.local_path, v.sha256 FROM versoes_documento v "
            "JOIN documentos d ON d.id=v.document_id WHERE v.id=?", (version_id,)).fetchone()
        if meta is None:
            raise ValueError("versão inexistente")
        blocks = [{"block_id": r[0], "page_number": r[1], "locator": r[2],
                   "start_offset": r[3], "end_offset": r[4], "text": r[5]}
                  for r in conn.execute(
                      "SELECT id,page_number,locator,start_offset,end_offset,text "
                      "FROM blocos_documento WHERE version_id=? "
                      "ORDER BY page_number,start_offset,id", (version_id,))]
        definitions = {}
        for block in blocks:
            for key, value in modality_legend.parse_definitions(
                    block.get("text") or "").items():
                definitions.setdefault(key, value)
        database = conn.execute("PRAGMA database_list").fetchone()
    artifact = None
    if meta[2] and database and database[2]:
        candidate = (Path(database[2]).resolve().parent / meta[2]).resolve()
        artifact = candidate if candidate.is_file() else None
    from radar.document_fields import LABEL_PREFIX
    from radar import vacancy_inline
    wide = parse_wide_table(blocks, meta[0], label_prefix=LABEL_PREFIX,
                            pdf_path=artifact, definitions=definitions)
    notation = parse_notation_table(blocks, meta[0], label_prefix=LABEL_PREFIX)
    inline = vacancy_inline.extract_distribution(blocks, meta[0],
                                                 label_prefix=LABEL_PREFIX)
    return {"version": VERSION, "version_id": version_id, "contest_id": meta[0],
            "title": meta[1], "sha256": meta[3],
            "definicoes": definitions,
            "quadro_colunas": {"rows": wide["rows"], "regions": wide["regions"],
                               "grand_total": wide["grand_total"],
                               "pendencias": wide["pendencias"]},
            "quadro_notacao": {"rows": notation["rows"],
                               "pendencias": notation["pendencias"]},
            "distribuicao_texto": {"rows": inline["rows"],
                                   "pendencias": inline["pendencias"]},
            "propostas": (len(wide["proposals"]) + len(notation["proposals"])
                          + len(inline["proposals"])),
            "limitacao": ("Leitura de quadro é candidata: nenhuma proposta é confirmada "
                          "aqui e nenhuma quantidade é rateada entre modalidades.")}
