"""OCR opcional e controlado para PDFs sem camada de texto.

Diagnóstico que orienta este módulo (Fase 31):

- o PDF do "Edital nº 11" não tem **nenhuma fonte** e nenhum operador de texto: 2.635
  caminhos preenchidos por página (``producer = Microsoft: Print To PDF``). É texto
  convertido em contornos vetoriais, não digitalização (0 imagens) e não corrupção;
- nenhum extrator de texto recupera isso: só rasterizar + reconhecer.

Motores (ambos locais; nenhum dado sai da máquina):

- ``windows_ocr``: API nativa do Windows (``Windows.Media.Ocr``) via PowerShell 5.1.
  Verificado nesta máquina em 2026-10-17: modelo **pt-BR** presente, ~0,6 s/página.
  Zero dependência nova e zero custo de licença adicional (capacidade do SO).
- ``tesseract``: usado se o binário e o modelo ``por`` existirem. Requer instalação de
  sistema (não feita aqui).

Nada é executado por padrão. O OCR grava uma **camada derivada** (blocos + propostas
marcadas) e nunca substitui o PDF original. Texto reconhecido **não** confirma campo.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from radar.document_store import connect_documents, is_readable_schema

OCR_VERSION = "ocr_v2"
MIN_CHARS_PER_PAGE = 40
MANY_DRAWINGS = 500

# Limites de segurança (por chamada, não por documento).
MAX_PAGES_PER_CALL = 20
MAX_DPI = 400
DEFAULT_DPI = 300
PAGE_TIMEOUT_SECONDS = 120
MAX_RENDER_BYTES = 40 * 1024 * 1024
OCR_METHOD_PREFIX = "ocr:"
OCR_SCOPE_REASON = ("texto reconhecido por OCR — conferir no documento original antes de "
                    "usar como evidência")

# Script PowerShell 5.1 (WinRT). Lê o PNG, reconhece e grava UTF-8 num arquivo.
_WINDOWS_OCR_SCRIPT = r"""
param([string]$ImagePath, [string]$OutputPath, [string]$Language = "pt-BR")
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1" })[0]
function Await($op, $type) {
    $method = $asTaskGeneric.MakeGenericMethod($type)
    $task = $method.Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
$lang = [Windows.Globalization.Language]::new($Language)
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) { Write-Output "MODELO_AUSENTE"; exit 3 }
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$lines = @()
foreach ($line in $result.Lines) { $lines += $line.Text }
[System.IO.File]::WriteAllText($OutputPath, ($lines -join "`n"), (New-Object System.Text.UTF8Encoding($false)))
Write-Output "OK"
"""


class OcrError(ValueError):
    """Falha de OCR com código estável."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _windows_powershell() -> str | None:
    """PowerShell 5.1 (``powershell.exe``): o pwsh 7 não carrega WinRT aqui."""
    return shutil.which("powershell") or shutil.which("powershell.exe")


def windows_languages(timeout: int = 30) -> list[str]:
    """Idiomas de OCR instalados no Windows (lista vazia se indisponível)."""
    shell = _windows_powershell()
    if not shell:
        return []
    script = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
        "[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null;"
        "[Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | ForEach-Object { $_.LanguageTag }"
    )
    try:
        completed = subprocess.run(
            [shell, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return []
    text = completed.stdout.decode("utf-8", "replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


def tesseract_languages(timeout: int = 20) -> list[str]:
    binary = shutil.which("tesseract")
    if not binary:
        return []
    try:
        completed = subprocess.run([binary, "--list-langs"], capture_output=True,
                                   timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return []
    text = completed.stdout.decode("utf-8", "replace")
    return [line.strip() for line in text.splitlines()[1:] if line.strip()]


def availability() -> dict:
    """Disponibilidade real dos motores nesta máquina (sem instalar nada)."""
    pymupdf = (importlib.util.find_spec("pymupdf") is not None
               or importlib.util.find_spec("fitz") is not None)
    shell = _windows_powershell()
    windows_langs = windows_languages() if shell else []
    tesseract_bin = shutil.which("tesseract")
    tesseract_langs = tesseract_languages() if tesseract_bin else []
    engines = {}
    if shell:
        engines["windows_ocr"] = {
            "disponivel": "pt-BR" in windows_langs,
            "idiomas": windows_langs,
            "motivo": None if "pt-BR" in windows_langs else "modelo pt-BR ausente",
        }
    if tesseract_bin:
        engines["tesseract"] = {
            "disponivel": "por" in tesseract_langs,
            "idiomas": tesseract_langs,
            "motivo": None if "por" in tesseract_langs else "modelo por ausente",
        }
    motor = next((name for name, info in engines.items() if info["disponivel"]), None)
    return {
        "version": OCR_VERSION,
        "pymupdf": bool(pymupdf),
        "engines": engines,
        "motor_escolhido": motor,
        "motor_disponivel": bool(pymupdf and motor),
        "limites": {"paginas_por_chamada": MAX_PAGES_PER_CALL, "dpi_maximo": MAX_DPI,
                    "timeout_por_pagina_s": PAGE_TIMEOUT_SECONDS},
        "limitacao": ("OCR é opcional e nunca automático. Sem motor disponível, o documento "
                      "permanece pdf_sem_texto — não é conteúdo inexistente. O texto "
                      "reconhecido é camada derivada, nunca confirmação de campo."),
    }


def _artifact(db_path, digest: str, relative_path: str) -> Path:
    root = Path(db_path).resolve().parent / (Path(db_path).name + ".documents")
    artifact = (Path(db_path).resolve().parent / relative_path).resolve()
    if artifact.parent != root.resolve() or artifact.name != digest:
        raise ValueError("caminho de artefato inválido")
    return artifact


def _open_pdf(db_path, version_id: str):
    try:
        import pymupdf
    except ImportError as error:  # pragma: no cover - ambiente sem PyMuPDF
        raise OcrError("ocr_indisponivel", "PyMuPDF não instalado (necessário para rasterizar)") from error
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute(
            "SELECT v.sha256, v.local_path, v.content_type, v.byte_size, d.title, "
            "v.extraction_state, v.error_code FROM versoes_documento v "
            "JOIN documentos d ON d.id=v.document_id WHERE v.id=?", (version_id,)).fetchone()
    if not row:
        raise ValueError("versão inexistente")
    digest, relative_path, content_type, size, title, state, error_code = row
    if (content_type or "").split(";", 1)[0].lower() != "application/pdf":
        raise OcrError("ocr_nao_e_pdf", "somente PDF pode passar por OCR")
    artifact = _artifact(db_path, digest, relative_path)
    data = artifact.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("hash de artefato divergente")
    document = pymupdf.open(stream=data, filetype="pdf")
    return {"document": document, "title": title, "sha256": digest, "bytes": size,
            "state": state, "error_code": error_code}


def detect_need(db_path, version_id: str) -> dict:
    """Classifica a necessidade de OCR de uma versão PDF (somente leitura)."""
    opened = _open_pdf(db_path, version_id)
    document = opened["document"]
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
        fonts = sum(len(document[index].get_fonts(full=True)) for index in range(pages))
    finally:
        document.close()
    result = {"version": OCR_VERSION, "version_id": version_id, "title": opened["title"],
              "pages": pages, "text_chars": text_chars, "drawings": drawings,
              "images": images, "fonts": fonts,
              "extraction_state": opened["state"], "error_code": opened["error_code"],
              "needs_ocr": False, "reason": None}
    if text_chars >= pages * MIN_CHARS_PER_PAGE:
        result["reason"] = "texto_suficiente"
        return result
    result["needs_ocr"] = True
    if fonts == 0 and drawings >= MANY_DRAWINGS and not images:
        # Texto convertido em contornos: não é digitalização, não é corrupção.
        result["reason"] = "texto_vetorial_sem_camada_de_texto"
    elif images:
        result["reason"] = "pagina_imagem"
    elif text_chars == 0:
        result["reason"] = "sem_texto_sem_imagem"
    else:
        result["reason"] = "texto_parcial"
    return result


def ocr_report(db_path, *, limit=100) -> dict:
    """Versões que precisam de OCR, com motivo e disponibilidade do motor."""
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
        except OcrError as error:
            erros.append({"version_id": version_id, "erro": error.code})
            continue
        except Exception as error:  # PDF corrompido não derruba o relatório
            erros.append({"version_id": version_id, "erro": type(error).__name__})
            continue
        if item.get("needs_ocr") is None:
            nao_inspecionados += 1
        items.append(item)
    needing = [item for item in items if item.get("needs_ocr") is True]
    by_reason = {}
    for item in needing:
        by_reason[item["reason"]] = by_reason.get(item["reason"], 0) + 1
    engine = availability()
    return {"version": OCR_VERSION, "generated_at": _now(), "inspecionados": len(items),
            "nao_inspecionados": nao_inspecionados,
            "precisam_ocr": len(needing), "por_motivo": by_reason,
            "erros_inspecao": erros, "motor": engine, "itens": needing,
            "limitacao": ("Nenhum OCR é executado por este relatório. Sem motor, o documento "
                          "permanece pdf_sem_texto — não como inexistente.")}


def _render_page(document, index: int, dpi: int, target: Path) -> tuple[int, int]:
    page = document[index]
    # Pré-checagem de área: recusar antes de alocar memória por uma página anômala.
    rect = page.rect
    estimated = abs(rect.width * rect.height) * (dpi / 72.0) ** 2 * 3
    if estimated > MAX_RENDER_BYTES:
        raise OcrError("ocr_pagina_grande",
                       f"página renderizada excederia {MAX_RENDER_BYTES} bytes")
    pixmap = page.get_pixmap(dpi=dpi)
    pixmap.save(str(target))
    if not target.exists():
        raise OcrError("ocr_falhou", "rasterização não produziu imagem")
    return pixmap.width, pixmap.height


def _ocr_windows(image: Path, output: Path, language: str,
                 timeout: int) -> tuple[str, int]:
    shell = _windows_powershell()
    if not shell:
        raise OcrError("ocr_indisponivel", "PowerShell 5.1 indisponível")
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(_WINDOWS_OCR_SCRIPT)
        script = Path(handle.name)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(script), "-ImagePath", str(image), "-OutputPath", str(output),
             "-Language", language],
            capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise OcrError("ocr_timeout", "OCR excedeu o tempo limite") from error
    finally:
        script.unlink(missing_ok=True)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout = completed.stdout.decode("utf-8", "replace").strip()
    if completed.returncode != 0:
        if "MODELO_AUSENTE" in stdout:
            raise OcrError("ocr_modelo_ausente", f"modelo {language} ausente no Windows OCR")
        detail = completed.stderr.decode("utf-8", "replace")[:200]
        raise OcrError("ocr_falhou", f"Windows OCR falhou: {detail}")
    if not output.exists():
        raise OcrError("ocr_falhou", "Windows OCR não produziu saída")
    text = output.read_text(encoding="utf-8-sig", errors="replace")
    return text, elapsed_ms


def _ocr_tesseract(image: Path, language: str, timeout: int) -> tuple[str, int]:
    binary = shutil.which("tesseract")
    if not binary:
        raise OcrError("ocr_indisponivel", "Tesseract não instalado")
    started = time.monotonic()
    try:
        completed = subprocess.run([binary, str(image), "stdout", "-l", language],
                                   capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise OcrError("ocr_timeout", "OCR excedeu o tempo limite") from error
    if completed.returncode != 0:
        raise OcrError("ocr_falhou", "Tesseract falhou")
    text = completed.stdout.decode("utf-8", "replace")
    return text, int((time.monotonic() - started) * 1000)


def _recognize(engine: str, image: Path, language: str, timeout: int) -> tuple[str, int]:
    if engine == "windows_ocr":
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as handle:
            output = Path(handle.name)
        try:
            return _ocr_windows(image, output, language, timeout)
        finally:
            output.unlink(missing_ok=True)
    if engine == "tesseract":
        return _ocr_tesseract(image, language, timeout)
    raise OcrError("ocr_indisponivel", f"motor desconhecido: {engine}")


def _resolve_engine(engine: str | None) -> tuple[str, str, dict]:
    info = availability()
    if not info["pymupdf"]:
        raise OcrError("ocr_indisponivel", "PyMuPDF não instalado (rasterização)")
    if engine:
        chosen = info["engines"].get(engine)
        if not chosen:
            raise OcrError("ocr_indisponivel", f"motor não disponível: {engine}")
        if not chosen["disponivel"]:
            raise OcrError("ocr_modelo_ausente", chosen["motivo"] or "modelo ausente")
        language = "pt-BR" if engine == "windows_ocr" else "por"
        return engine, language, info
    motor = info["motor_escolhido"]
    if not motor:
        raise OcrError("ocr_indisponivel",
                       "nenhum motor com modelo português disponível")
    language = "pt-BR" if motor == "windows_ocr" else "por"
    return motor, language, info


def ocr_version(db_path, version_id: str, *, engine: str | None = None,
                pages: list[int] | None = None, dpi: int = DEFAULT_DPI,
                apply: bool = False, timeout: int = PAGE_TIMEOUT_SECONDS,
                now: str | None = None) -> dict:
    """Executa (ou simula) OCR de páginas selecionadas de uma versão.

    O PDF original nunca é alterado. Com ``apply=False`` devolve apenas o plano.
    """
    dpi = int(dpi)
    if dpi < 72 or dpi > MAX_DPI:
        raise OcrError("ocr_parametro_invalido", f"dpi fora da faixa 72..{MAX_DPI}")
    timeout = int(timeout)
    if timeout < 5 or timeout > 600:
        raise OcrError("ocr_parametro_invalido", "timeout fora da faixa 5..600")

    opened = _open_pdf(db_path, version_id)
    document = opened["document"]
    try:
        total = document.page_count
        selected = sorted({int(number) for number in (pages or range(1, min(total, MAX_PAGES_PER_CALL) + 1))})
        if not selected:
            raise OcrError("ocr_parametro_invalido", "nenhuma página selecionada")
        if any(number < 1 or number > total for number in selected):
            raise OcrError("ocr_parametro_invalido", f"página fora do documento (1..{total})")
        if len(selected) > MAX_PAGES_PER_CALL:
            raise OcrError("ocr_limite_paginas",
                           f"máximo de {MAX_PAGES_PER_CALL} páginas por chamada")

        with closing(connect_documents(db_path)) as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM blocos_documento WHERE version_id=?",
                (version_id,)).fetchone()[0]
        if apply and existing:
            # `record_analysis` recusa versão já analisada: falhar ANTES de rasterizar e
            # reconhecer evita custo inútil. Uma chamada de OCR por versão.
            raise OcrError("ocr_versao_ja_analisada",
                           "versão já possui blocos; OCR é uma chamada por versão")

        if not apply:
            info = availability()
            return {"version": OCR_VERSION, "version_id": version_id,
                    "title": opened["title"], "sha256": opened["sha256"],
                    "total_pages": total, "pages": selected, "dpi": dpi,
                    "motor": info["motor_escolhido"],
                    "motor_disponivel": info["motor_disponivel"],
                    "apply": False, "would_ocr": info["motor_disponivel"],
                    "limitacao": ("Simulação: nenhuma imagem é gerada e nenhum bloco é "
                                  "gravado. O PDF original permanece intacto.")}

        motor, language, info = _resolve_engine(engine)
        started = time.monotonic()
        blocks, page_metrics = [], []
        with tempfile.TemporaryDirectory(prefix="radar-ocr-") as folder:
            for number in selected:
                image = Path(folder) / f"page-{number}.png"
                width, height = _render_page(document, number - 1, dpi, image)
                if image.stat().st_size > MAX_RENDER_BYTES:
                    raise OcrError("ocr_arquivo_grande", "imagem renderizada excede o limite")
                text, elapsed_ms = _recognize(motor, image, language, timeout)
                normalized = " ".join(text.split())
                page_metrics.append({"page": number, "chars": len(normalized),
                                     "ms": elapsed_ms, "width": width, "height": height})
                if normalized:
                    blocks.append({"page_number": number, "locator": f"página {number}",
                                   "start_offset": 0, "end_offset": len(normalized),
                                   "text": normalized})
    finally:
        document.close()

    duration_ms = int((time.monotonic() - started) * 1000)
    if not blocks:
        raise OcrError("ocr_sem_texto", "motor não reconheceu texto nas páginas selecionadas")

    proposals = []
    if apply:
        from radar.document_fields import extract_field_proposals
        with closing(connect_documents(db_path)) as conn:
            row = conn.execute("SELECT contest_id, role_id FROM documentos d "
                               "JOIN versoes_documento v ON v.document_id=d.id "
                               "WHERE v.id=?", (version_id,)).fetchone()
        contest_id, role_id = row
        raw = extract_field_proposals(blocks, version_id, contest_id, role_id)
        for proposal in raw:
            proposal["extraction_method"] = OCR_METHOD_PREFIX + proposal["extraction_method"]
            existing = proposal.get("ambiguity_reason")
            proposal["ambiguity_reason"] = (
                f"{OCR_SCOPE_REASON}; {existing}" if existing else OCR_SCOPE_REASON)
            proposals.append(proposal)
        note = json.dumps({
            "extractor_version": OCR_VERSION, "engine": motor, "language": language,
            "dpi": dpi, "pages": selected, "total_pages": total,
            "duration_ms": duration_ms, "chars": sum(m["chars"] for m in page_metrics),
            "page_metrics": page_metrics, "derived_layer": True,
            "source_sha256": opened["sha256"],
        }, ensure_ascii=False)
        from radar.document_store import record_analysis
        record_analysis(db_path, version_id, blocks, proposals, note=note, partial=True)

    return {"version": OCR_VERSION, "version_id": version_id, "title": opened["title"],
            "sha256": opened["sha256"], "total_pages": total, "pages": selected,
            "dpi": dpi, "engine": motor, "language": language, "apply": True,
            "blocks": len(blocks), "proposals": len(proposals),
            "chars": sum(m["chars"] for m in page_metrics), "duration_ms": duration_ms,
            "page_metrics": page_metrics,
            "limitacao": ("Camada derivada: o PDF original não foi alterado e o texto "
                          "reconhecido não confirma nenhum campo.")}
