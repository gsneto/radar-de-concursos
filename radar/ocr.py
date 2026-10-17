"""Detecção de PDFs que precisam de OCR e disponibilidade real do motor.

Nada aqui executa OCR por padrão. O objetivo é **medir** a necessidade e expor o motivo:

- ``sem_texto_sem_imagem``: página sem texto e sem imagem — texto desenhado como vetores
  (o caso do "Edital nº 11", com milhares de pequenos caminhos);
- ``pagina_imagem``: página coberta por imagem (digitalização clássica);
- ``texto_parcial``: há texto, mas em quantidade suspeita para o tamanho da página.

Motivo para não rodar OCR automaticamente (pesquisa em 2026-10-17):

- OCR é ~1000x mais lento que extração de texto e consome CPU/memória;
- Tesseract não é dependência do projeto e não está instalado nesta máquina;
- OCRmyPDF é MPL-2.0, mas exige Ghostscript (AGPLv3) e Tesseract — decisão de licença e
  instalação que não deve ser tomada em silêncio;
- a documentação do PyMuPDF recomenda justamente detectar (imagem, ausência de texto,
  milhares de vetores) antes de acionar OCR.

Enquanto o motor não existir, o documento fica classificado como ``pdf_sem_texto`` — nunca
como "sem conteúdo".
"""

from __future__ import annotations

import importlib.util
import shutil
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from radar.document_store import connect_documents, is_readable_schema

OCR_VERSION = "ocr_v1"
MIN_CHARS_PER_PAGE = 40
MANY_DRAWINGS = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def availability() -> dict:
    """Disponibilidade real do motor de OCR nesta máquina (sem instalar nada)."""
    tesseract = shutil.which("tesseract")
    pymupdf = importlib.util.find_spec("pymupdf") is not None or \
        importlib.util.find_spec("fitz") is not None
    pytesseract = importlib.util.find_spec("pytesseract") is not None
    ocrmypdf = importlib.util.find_spec("ocrmypdf") is not None
    return {
        "version": OCR_VERSION,
        "tesseract_binario": bool(tesseract),
        "pymupdf": bool(pymupdf),
        "pytesseract": bool(pytesseract),
        "ocrmypdf": bool(ocrmypdf),
        "motor_disponivel": bool(tesseract and pymupdf),
        "limitacao": ("OCR não é executado sem motor instalado. Instalar Tesseract é decisão "
                      "de sistema (licença e manutenção), não automática."),
    }


def _artifact(db_path, digest: str, relative_path: str) -> Path:
    root = Path(db_path).resolve().parent / (Path(db_path).name + ".documents")
    artifact = (Path(db_path).resolve().parent / relative_path).resolve()
    if artifact.parent != root.resolve() or artifact.name != digest:
        raise ValueError("caminho de artefato inválido")
    return artifact


def detect_need(db_path, version_id: str) -> dict:
    """Classifica a necessidade de OCR de uma versão PDF (somente leitura)."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute(
            "SELECT v.sha256, v.local_path, v.content_type, v.byte_size, d.title, "
            "v.extraction_state, v.error_code FROM versoes_documento v "
            "JOIN documentos d ON d.id=v.document_id WHERE v.id=?",
            (version_id,)).fetchone()
    if not row:
        raise ValueError("versão inexistente")
    digest, relative_path, content_type, size, title, state, error_code = row
    result = {"version": OCR_VERSION, "version_id": version_id, "title": title,
              "content_type": content_type, "byte_size": size,
              "extraction_state": state, "error_code": error_code,
              "needs_ocr": False, "reason": None, "pages": None}
    if (content_type or "").split(";", 1)[0].lower() != "application/pdf":
        result["reason"] = "nao_e_pdf"
        return result
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - ambiente sem PyMuPDF
        # Sem inspetor: não afirmar "não precisa". Conta páginas/texto com pypdf (dependência
        # declarada) e marca a inspeção como indisponível.
        try:
            from io import BytesIO

            from pypdf import PdfReader
            reader = PdfReader(BytesIO(_artifact(db_path, digest, relative_path).read_bytes()))
            pages = len(reader.pages)
            text_chars = sum(len((page.extract_text() or "").strip())
                             for page in reader.pages)
        except Exception:
            result["needs_ocr"] = None
            result["reason"] = "inspecao_indisponivel"
            return result
        result["pages"] = pages
        result["text_chars"] = text_chars
        result["inspected_with"] = "pypdf"
        result["needs_ocr"] = None
        result["reason"] = ("inspecao_indisponivel" if text_chars < pages * MIN_CHARS_PER_PAGE
                            else "texto_suficiente")
        return result
    artifact = _artifact(db_path, digest, relative_path)
    try:
        document = pymupdf.open(stream=artifact.read_bytes(), filetype="pdf")
    except Exception:
        result["needs_ocr"] = None
        result["reason"] = "inspecao_indisponivel"
        return result
    try:
        pages = document.page_count
        text_chars = 0
        drawings = 0
        images = 0
        for index in range(pages):
            page = document[index]
            text_chars += len(page.get_text().strip())
            drawings += len(page.get_drawings())
            images += len(page.get_images(full=True))
    finally:
        document.close()
    result["pages"] = pages
    result["text_chars"] = text_chars
    result["drawings"] = drawings
    result["images"] = images
    if text_chars >= pages * MIN_CHARS_PER_PAGE:
        result["reason"] = "texto_suficiente"
        return result
    result["needs_ocr"] = True
    if drawings >= MANY_DRAWINGS and not images:
        result["reason"] = "texto_vetorial_sem_camada_de_texto"
    elif images:
        result["reason"] = "pagina_imagem"
    elif text_chars == 0:
        result["reason"] = "sem_texto_sem_imagem"
    else:
        result["reason"] = "texto_parcial"
    return result


def ocr_report(db_path, *, limit=100) -> dict:
    """Versões que precisam de OCR, com o motivo e a disponibilidade do motor."""
    limit = int(limit)
    if limit < 1 or limit > 1000:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT v.id, v.error_code FROM versoes_documento v
            JOIN documentos d ON d.id=v.document_id
            WHERE v.content_type LIKE 'application/pdf%'
              AND NOT EXISTS (SELECT 1 FROM blocos_documento b WHERE b.version_id=v.id)
            ORDER BY v.byte_size, v.id LIMIT ?""", (limit,)).fetchall()
    items, nao_inspecionados, erros = [], 0, []
    for version_id, error_code in rows:
        try:
            item = detect_need(db_path, version_id)
        except Exception as error:  # PDF corrompido não derruba o relatório
            erros.append({"version_id": version_id, "erro": type(error).__name__})
            continue
        if item.get("needs_ocr") is None:
            nao_inspecionados += 1
        if item.get("needs_ocr") is None and error_code == "pdf_sem_texto":
            # A extração já provou a ausência de texto: não esconder o caso por falta de inspetor.
            item["needs_ocr"] = True
            item["reason"] = "sem_texto_confirmado_na_extracao"
        items.append(item)
    needing = [item for item in items if item.get("needs_ocr") is True]
    by_reason = {}
    for item in needing:
        by_reason[item["reason"]] = by_reason.get(item["reason"], 0) + 1
    engine = availability()
    return {"version": OCR_VERSION, "generated_at": _now(), "inspecionados": len(items),
            "nao_inspecionados": nao_inspecionados,
            "precisam_ocr": len(needing), "por_motivo": by_reason,
            "erros_inspecao": erros,
            "motor": engine, "itens": needing,
            "limitacao": ("Nenhum OCR é executado nesta fase. Sem motor instalado, o "
                          "documento permanece como pdf_sem_texto — não como inexistente. "
                          "necessidade de OCR não inspecionada nunca vira 'não precisa'.")}


def ocr_version(db_path, version_id: str) -> dict:
    """Executa OCR **somente** se o motor estiver instalado; caso contrário, recusa."""
    engine = availability()
    if not engine["motor_disponivel"]:
        raise ValueError("ocr_indisponivel: instale Tesseract e PyMuPDF para habilitar")
    import pymupdf
    need = detect_need(db_path, version_id)
    if not need["needs_ocr"]:
        return {"version": OCR_VERSION, "version_id": version_id, "ocr": False,
                "reason": need["reason"]}
    with closing(connect_documents(db_path)) as conn:
        row = conn.execute("SELECT sha256, local_path FROM versoes_documento WHERE id=?",
                           (version_id,)).fetchone()
    artifact = _artifact(db_path, row[0], row[1])
    document = pymupdf.open(stream=artifact.read_bytes(), filetype="pdf")
    blocks = []
    try:
        for index in range(document.page_count):
            page = document[index]
            textpage = page.get_textpage_ocr(language="por", dpi=300)
            text = " ".join((page.get_text(textpage=textpage) or "").split())
            if text:
                blocks.append({"page_number": index + 1, "locator": f"página {index + 1}",
                               "start_offset": 0, "end_offset": len(text), "text": text})
    finally:
        document.close()
    if not blocks:
        raise ValueError("ocr_sem_texto: motor não reconheceu texto")
    return {"version": OCR_VERSION, "version_id": version_id, "ocr": True,
            "blocks": len(blocks), "pages": need["pages"],
            "reason": need["reason"], "motor": engine}
