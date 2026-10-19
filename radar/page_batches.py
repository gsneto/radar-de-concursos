"""Lotes de páginas para PDF longo (Fase 32).

Um PDF de 3.000 páginas não deve ser lido inteiro: o prefixo de 40 páginas (Fase 30) já
registra a limitação. Este módulo acrescenta o passo seguinte, com três regras:

1. **Inventário justificado** — cada documento parcial é classificado pelo conteúdo real das
   páginas ainda não lidas. Lista de resultado/homologação/isenção com dados pessoais não é
   processada: a justificativa fica registrada em vez de o documento ser silenciosamente
   ignorado.
2. **Índice de páginas** — mostra em que página está cada tipo de conteúdo útil, para escolher
   o lote sem varrer o arquivo inteiro.
3. **Lote com checkpoint** — acrescenta páginas ainda não extraídas (`append_page_analysis`),
   com limite por chamada, página final devolvida e retomada a partir do checkpoint. Página já
   gravada nunca é regravada, então repetir o lote é seguro.
"""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import closing
from io import BytesIO
from pathlib import Path

from radar.document_store import (append_page_analysis, connect_documents,
                                  is_readable_schema, mark_extraction_complete)

BATCH_VERSION = "page_batches_v1"
DEFAULT_BATCH_PAGES = 40

# Conteúdo pessoal em lista de resultado: nunca é insumo de campo do concurso.
PERSONAL_TOKENS = {
    "nome_do_candidato": r"\bnome\s+do\s+candidato\b|\bcandidato\s*:",
    "data_de_nascimento": r"\bdata\s+de\s+nascimento\b",
    "documento_identidade": r"\b(?:cpf|rg)\b",
    "nota": r"\bnota\s*(?:final|da\s+prova|obtida)?\b",
    "classificacao": r"\bclassifica[çc][ãa]o\b",
    "resultado": r"\bresultado\b|\bhomologa[çc][ãa]o\b",
    "isencao": r"\bisen[çc][ãa]o\b|\bpedido\s+de\s+isen[çc][ãa]o\b",
}
_PERSONAL = {name: re.compile(pattern, re.I) for name, pattern in PERSONAL_TOKENS.items()}
# Conteúdo útil para o radar (vaga, requisito, data, local).
USEFUL_TOKENS = {
    "vagas": r"\bquadro\s+de\s+vagas\b|\bvagas?\s+(?:para|de)\b|\bNTE\b|\bN[ÚU]CLEO\b",
    "requisito": r"\brequisitos?\b|\bescolaridade\b|\bdiploma\b",
    "prazo": r"\binscri[çc][õo]es\b|\bcronograma\b",
    "local": r"\blocal\s+de\s+prova\b",
    "cargo": r"\bcargo\b|\bfun[çc][ãa]o\s+tempor",
}
_USEFUL = {name: re.compile(pattern, re.I) for name, pattern in USEFUL_TOKENS.items()}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load(db_path, version_id: str):
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute(
            "SELECT v.sha256,v.local_path,v.content_type,d.contest_id,d.role_id,d.title "
            "FROM versoes_documento v JOIN documentos d ON d.id=v.document_id WHERE v.id=?",
            (version_id,)).fetchone()
        if not row:
            raise ValueError("versão inexistente")
        pages = [page for page in conn.execute(
            "SELECT DISTINCT page_number FROM blocos_documento WHERE version_id=? "
            "ORDER BY page_number", (version_id,))]
    digest, relative_path, content_type, contest_id, role_id, title = row
    root = (Path(db_path).resolve().parent / (Path(db_path).name + ".documents")).resolve()
    artifact = (Path(db_path).resolve().parent / relative_path).resolve()
    if artifact.parent != root or artifact.name != digest:
        raise ValueError("caminho de artefato inválido")
    content = artifact.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("hash de artefato divergente")
    return {"version_id": version_id, "sha256": digest, "content": content,
            "content_type": content_type, "contest_id": contest_id, "role_id": role_id,
            "title": title, "extracted_pages": [page[0] for page in pages]}


def _reader(content: bytes):
    """Abre o PDF com as mesmas recusas do extrator (criptografado/ilegível)."""
    from pypdf import PdfReader
    from radar.document_extract import PDF_ILEGIVEL, ExtractionError
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ExtractionError("pdf_criptografado", "PDF criptografado")
        return reader
    except ExtractionError:
        raise
    except Exception as error:
        raise ExtractionError(PDF_ILEGIVEL, "PDF ilegível") from error


def _page_texts(content: bytes, pages: list[int]) -> dict[int, str]:
    reader = _reader(content)
    texts = {}
    for number in pages:
        if 1 <= number <= len(reader.pages):
            texts[number] = " ".join((reader.pages[number - 1].extract_text() or "").split())
    return texts


def _total_pages(content: bytes) -> int:
    return len(_reader(content).pages)


def page_index(db_path, version_id: str, *, pages: list[int] | None = None,
               sample: int = 60) -> dict:
    """Em que página está cada tipo de conteúdo (útil, pessoal).

    Sem ``pages``, amostra as páginas **não lidas** em passo regular (no máximo ``sample``):
    um PDF de 1.400 páginas não é lido inteiro só para classificar o restante.
    """
    loaded = _load(db_path, version_id)
    total = _total_pages(loaded["content"])
    if pages is None:
        unread = [page for page in range(1, total + 1)
                  if page not in set(loaded["extracted_pages"])]
        step = max(1, -(-len(unread) // max(1, int(sample))))  # ceil
        pages = unread[::step][:max(1, int(sample))]
        if unread and pages[-1] != unread[-1]:
            pages[-1] = unread[-1]  # a última página também precisa ser classificada
    texts = _page_texts(loaded["content"], pages)
    index = []
    for number in sorted(texts):
        text = texts[number]
        index.append({
            "page": number,
            "extracted": number in loaded["extracted_pages"],
            "chars": len(text),
            "util": [name for name, pattern in _USEFUL.items() if pattern.search(text)],
            "pessoal": [name for name, pattern in _PERSONAL.items() if pattern.search(text)],
        })
    return {"version": BATCH_VERSION, "version_id": version_id, "total_pages": total,
            "paginas": index}


# Atos que publicam nome/nota/resultado de candidato, não regra do concurso.
_RESULT_ACT = re.compile(
    r"\bresultado\b|\bhomologa[çc][ãa]o\b|\bisenc[ãa]o\b|\bconvoca|\bconvoca[çc][ãa]o\b|"
    r"\bgabarito\b|\bclassifica[çc][ãa]o\b|\ban[áa]lise\s+dos\s+pedidos\b", re.I)


def _classify(index: list[dict], title: str = "") -> dict:
    """Decide se o restante do documento deve ser processado, com justificativa explícita.

    Lista nominal de resultado tem precedência: publicar nome, nota ou classificação de
    candidato não alimenta campo do concurso e exporia dados pessoais sem ganho.
    """
    missing = [item for item in index if not item["extracted"]]
    if not missing:
        return {"processar": False, "classificacao": "completo",
                "justificativa": "todas as páginas já foram extraídas"}
    util = [item for item in missing if item["util"]]
    pessoal = [item for item in missing if item["pessoal"]]
    kinds = sorted({kind for item in pessoal for kind in item["pessoal"]})
    if _RESULT_ACT.search(title or ""):
        # Ato de resultado é lista: as páginas seguintes repetem nome/nota/classificação.
        # O que interessa ao radar (regra, vaga, requisito) está no edital, não aqui.
        detalhe = (f"com {len(pessoal)} de {len(missing)} páginas amostradas nominais "
                   f"({', '.join(kinds)})" if pessoal else
                   "sem marcador nominal legível nas páginas amostradas")
        return {"processar": False, "classificacao": "dados_pessoais_lista_resultado",
                "justificativa": (f"ato de resultado ({title[:60]}) {detalhe}; as páginas "
                                  "restantes repetem a mesma lista nominal, que não alimenta "
                                  "campo do concurso e exporia dados pessoais sem ganho"),
                "tipos_pessoais": kinds}
    if pessoal and len(pessoal) >= len(util):
        return {"processar": False, "classificacao": "dados_pessoais_lista_resultado",
                "justificativa": (f"{len(pessoal)} de {len(missing)} páginas não lidas são lista "
                                  f"nominal ({', '.join(kinds)}); não alimentam campo do concurso "
                                  "e o processamento exporia dados pessoais sem ganho"),
                "tipos_pessoais": kinds}
    if util and len(util) >= max(1, len(missing) // 4):
        return {"processar": True, "classificacao": "conteudo_util",
                "justificativa": (f"{len(util)} de {len(missing)} páginas não lidas têm conteúdo "
                                  "de edital (vaga, requisito, prazo, local ou cargo)")}
    return {"processar": False, "classificacao": "sem_conteudo_util",
            "justificativa": (f"{len(missing)} páginas não lidas sem marcador de edital nem de "
                              "lista nominal; nada a extrair")}


def partial_inventory(db_path, *, limit: int = 500) -> dict:
    """Documentos com extração parcial, com o motivo e a decisão de processar ou não."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute(
            """SELECT v.id,d.title,d.contest_id,MAX(b.page_number),e.note
               FROM versoes_documento v JOIN documentos d ON d.id=v.document_id
               JOIN blocos_documento b ON b.version_id=v.id
               LEFT JOIN eventos_documentais e
                 ON e.version_id=v.id AND e.event_type='analise'
               WHERE e.note LIKE '%"truncated": true%'
               GROUP BY v.id ORDER BY d.title LIMIT ?""", (int(limit),)).fetchall()
    items = []
    for version_id, title, contest_id, max_page, note in rows:
        try:
            meta = json.loads(note) if note else {}
        except (TypeError, ValueError):
            meta = {}
        if not meta.get("truncated"):
            continue
        total = meta.get("total_pages")
        if not isinstance(max_page, int) or not isinstance(total, int):
            continue
        if total <= max_page:
            continue
        try:
            index = page_index(db_path, version_id)
        except Exception as error:  # um PDF ilegível não interrompe o inventário
            items.append({"version_id": version_id, "title": title,
                          "contest_id": contest_id, "erro": type(error).__name__})
            continue
        decision = _classify(index["paginas"], title or "")
        items.append({"version_id": version_id, "title": title, "contest_id": contest_id,
                      "paginas_extraidas": max_page, "total_pages": total,
                      "paginas_nao_lidas": total - max_page,
                      "limitacao_registrada": meta.get("limitation"), **decision})
    parciais = [item for item in items if item.get("classificacao") or item.get("erro")]
    return {"version": BATCH_VERSION, "parciais": parciais,
            "total": len(parciais),
            "processar": sum(1 for item in parciais if item.get("processar")),
            "justificados_sem_processar": sum(1 for item in parciais
                                              if item.get("processar") is False)}


def append_pages(db_path, version_id: str, *, start_page: int | None = None,
                 end_page: int | None = None, max_pages: int = DEFAULT_BATCH_PAGES,
                 dry_run: bool = True, checkpoint: str | None = None) -> dict:
    """Acrescenta um lote de páginas ainda não extraídas, com limite e retomada.

    ``start_page`` padrão é a primeira página não lida. Nunca regrava página já extraída;
    ``checkpoint`` (caminho JSON) guarda a próxima página para retomar o lote seguinte.
    """
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages <= 0:
        raise ValueError("max_pages precisa ser inteiro positivo")
    loaded = _load(db_path, version_id)
    total = _total_pages(loaded["content"])
    extracted = set(loaded["extracted_pages"])
    first = int(start_page) if start_page else next(
        (page for page in range(1, total + 1) if page not in extracted), total + 1)
    if first > total:
        if not dry_run:
            mark_extraction_complete(db_path, version_id)
        return {"version": BATCH_VERSION, "version_id": version_id,
                "dry_run": bool(dry_run), "total_pages": total, "start_page": None,
                "end_page": None, "paginas_no_lote": [], "next_page": None,
                "added_blocks": 0, "added_proposals": 0,
                "motivo": "todas as páginas já foram extraídas"}
    last = int(end_page) if end_page else min(total, first + max(0, int(max_pages)) - 1)
    last = min(last, first + max(0, int(max_pages)) - 1)
    wanted = [page for page in range(first, last + 1) if page not in extracted]
    report = {"version": BATCH_VERSION, "version_id": version_id, "dry_run": bool(dry_run),
              "total_pages": total, "start_page": first, "end_page": last,
              "paginas_no_lote": wanted, "next_page": None,
              "added_blocks": 0, "added_proposals": 0}
    if not wanted:
        report["next_page"] = None
        report["motivo"] = "nenhuma página nova no intervalo"
        return report
    if dry_run:
        report["next_page"] = last + 1 if last < total else None
        return report

    from radar.document_extract import ExtractionError, extract_document
    from radar.document_fields import extract_field_proposals
    texts = _page_texts(loaded["content"], wanted)
    blocks = [dict(page_number=number, locator=f"página {number}", start_offset=0,
                   end_offset=len(text), text=text)
              for number, text in sorted(texts.items()) if text]
    if not blocks:
        report["motivo"] = "páginas do lote sem texto extraível"
        report["next_page"] = last + 1 if last < total else None
        if last >= total:
            mark_extraction_complete(db_path, version_id)
        if checkpoint:
            _write_checkpoint(checkpoint, version_id, report["next_page"])
        return report
    try:
        proposals = extract_field_proposals(blocks, version_id, loaded["contest_id"],
                                            loaded["role_id"])
    except ExtractionError:
        proposals = []
    limitation = (f"lote de páginas {blocks[0]['page_number']}–{blocks[-1]['page_number']} "
                  f"de {total}; páginas anteriores mantidas")
    result = append_page_analysis(db_path, version_id, blocks, proposals,
                                  note=json.dumps({"extractor_version": BATCH_VERSION,
                                                   "limitation": limitation},
                                                  ensure_ascii=False),
                                  partial=(last < total))
    report.update({"added_blocks": result.get("added_blocks", 0),
                   "added_proposals": result.get("added_proposals", 0),
                   "skipped_pages": result.get("skipped_pages", []),
                   "next_page": last + 1 if last < total else None,
                   "limitation": limitation})
    if checkpoint:
        _write_checkpoint(checkpoint, version_id, report["next_page"])
    return report


def _write_checkpoint(path_value: str, version_id: str, next_page) -> None:
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version_id": version_id, "next_page": next_page,
                                "atualizado_em": _now()}, ensure_ascii=False),
                    encoding="utf-8")


def batch_report(db_path, *, limit: int = 500) -> dict:
    """Resumo: parciais, quantos processar e quantos estão justificados sem processar."""
    inventory = partial_inventory(db_path, limit=limit)
    return {"version": BATCH_VERSION,
            "parciais": inventory["total"],
            "processar": inventory["processar"],
            "justificados_sem_processar": inventory["justificados_sem_processar"],
            "itens": inventory["parciais"]}
