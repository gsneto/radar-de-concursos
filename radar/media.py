"""Mídia local de flashcards: validação por assinatura binária e armazenamento por hash.

Decisões (documentadas em `docs/superpowers/specs/2026-10-17-advanced-practice-navigation-media-adaptive-packages-design.md`):

- **Nada de confiar no cliente**: nome, extensão e `Content-Type` são ignorados. O tipo é
  determinado pelos **magic bytes** do próprio conteúdo (PNG, JPEG, GIF, WebP).
- **Sem dependências**: `imghdr` foi removido no Python 3.13 e `Pillow` seria uma dependência
  pesada; as assinaturas são explícitas e auditáveis (OWASP recomenda validação de assinatura).
- **SVG é recusado** (pode executar script quando servido).
- **Nome do arquivo é o SHA-256**: elimina path traversal, colisão de nomes e sobrescrita
  acidental; o mesmo conteúdo é deduplicado naturalmente.
- Arquivos ficam **fora do webroot** (`data/estudo-midia/`), servidos por rota com
  `Content-Type` fixo e `X-Content-Type-Options: nosniff`.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

# Limite padrão por imagem (configurável por parâmetro). 8 MiB cobre diagramas com folga.
DEFAULT_MAX_BYTES = 8 * 1024 * 1024

# Assinaturas aceitas: (mime, extensão, verificador).
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_JPEG_SIG = b"\xff\xd8\xff"
_GIF87 = b"GIF87a"
_GIF89 = b"GIF89a"


class MediaError(ValueError):
    """Arquivo de mídia inválido, inseguro ou grande demais."""


def _png_size(data: bytes):
    """(largura, altura) do IHDR do PNG, ou ``None`` se o cabeçalho não for coerente."""
    if len(data) < 33 or data[12:16] != b"IHDR":
        return None
    try:
        width, height = struct.unpack(">II", data[16:24])
    except struct.error:
        return None
    if not (0 < width <= 20000 and 0 < height <= 20000):
        return None
    return width, height


def _gif_size(data: bytes):
    if len(data) < 10:
        return None
    try:
        width, height = struct.unpack("<HH", data[6:10])
    except struct.error:
        return None
    if not (0 < width <= 20000 and 0 < height <= 20000):
        return None
    return width, height


def _jpeg_size(data: bytes):
    """Percorre os marcadores JPEG até o SOFn para obter largura/altura."""
    index = 2
    length = len(data)
    while index + 9 < length:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        try:
            segment_length = struct.unpack(">H", data[index + 2:index + 4])[0]
        except struct.error:
            return None
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if index + 9 > length:
                return None
            height, width = struct.unpack(">HH", data[index + 5:index + 9])
            if 0 < width <= 20000 and 0 < height <= 20000:
                return width, height
            return None
        if segment_length < 2:
            return None
        index += 2 + segment_length
    return None


def _webp_size(data: bytes):
    """(largura, altura) do WebP (VP8/VP8L/VP8X)."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk = data[12:16]
    try:
        if chunk == b"VP8X":
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return (width, height) if 0 < width <= 20000 and 0 < height <= 20000 else None
        if chunk == b"VP8 ":
            width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
            height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
            return (width, height) if 0 < width <= 20000 and 0 < height <= 20000 else None
        if chunk == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return (width, height) if 0 < width <= 20000 and 0 < height <= 20000 else None
    except (struct.error, IndexError):
        return None
    return None


def detect_image(data: bytes) -> dict:
    """Identifica o tipo real da imagem pelas assinaturas; recusa o que não for suportado.

    Devolve ``{mime, extensao, largura, altura}``. Levanta ``MediaError`` para conteúdo vazio,
    não reconhecido, SVG (script) ou cabeçalho incoerente.
    """
    if not isinstance(data, (bytes, bytearray)) or len(data) < 16:
        raise MediaError("arquivo vazio ou pequeno demais para ser uma imagem")
    data = bytes(data)
    if data.startswith(_PNG_SIG):
        size = _png_size(data)
        if size is None:
            raise MediaError("PNG com cabeçalho inválido")
        return {"mime": "image/png", "extensao": "png", "largura": size[0], "altura": size[1]}
    if data.startswith(_JPEG_SIG):
        size = _jpeg_size(data)
        if size is None:
            raise MediaError("JPEG com cabeçalho inválido")
        return {"mime": "image/jpeg", "extensao": "jpg", "largura": size[0], "altura": size[1]}
    if data.startswith(_GIF87) or data.startswith(_GIF89):
        size = _gif_size(data)
        if size is None:
            raise MediaError("GIF com cabeçalho inválido")
        return {"mime": "image/gif", "extensao": "gif", "largura": size[0], "altura": size[1]}
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        size = _webp_size(data)
        if size is None:
            raise MediaError("WebP com cabeçalho inválido")
        return {"mime": "image/webp", "extensao": "webp", "largura": size[0], "altura": size[1]}
    head = data[:512].lstrip().lower()
    if head.startswith(b"<svg") or b"<svg" in head:
        raise MediaError("SVG não é aceito (pode executar script)")
    raise MediaError("formato de imagem não suportado (use PNG, JPEG, GIF ou WebP)")


def validate_image(data, *, max_bytes: int = DEFAULT_MAX_BYTES) -> dict:
    """Valida tamanho + conteúdo e devolve metadados com o hash (identificador estável)."""
    if not isinstance(data, (bytes, bytearray)):
        raise MediaError("conteúdo inválido")
    if len(data) == 0:
        raise MediaError("arquivo vazio")
    if len(data) > max_bytes:
        raise MediaError(f"imagem acima do limite de {max_bytes // (1024 * 1024)} MiB")
    info = detect_image(data)
    digest = hashlib.sha256(bytes(data)).hexdigest()
    return {**info, "sha256": digest, "bytes": len(data)}


def media_dir(db_path) -> Path:
    """Diretório de mídia ao lado do banco, fora do webroot (não é servido estaticamente)."""
    root = Path(db_path).resolve().parent
    return root / "estudo-midia"


def store_image(db_path, data, *, max_bytes: int = DEFAULT_MAX_BYTES,
                origem: str = "usuario", licenca=None) -> dict:
    """Grava a imagem (nome = sha256) de forma atômica e idempotente; devolve metadados.

    Nunca sobrescreve conteúdo diferente: o nome é o hash, então um arquivo existente com o
    mesmo nome **é** o mesmo conteúdo.
    """
    info = validate_image(data, max_bytes=max_bytes)
    directory = media_dir(db_path)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{info['sha256']}.{info['extensao']}"
    if not target.exists():
        temp = target.with_name(target.name + ".tmp")
        temp.write_bytes(bytes(data))
        temp.replace(target)  # atômico
    return {**info, "path": target, "origem": origem, "licenca": licenca}


def media_path(db_path, sha256: str, extensao: str) -> Path | None:
    """Caminho do arquivo de mídia, ou ``None`` se ausente/inválido."""
    if not isinstance(sha256, str) or len(sha256) != 64 or not all(
            ch in "0123456789abcdef" for ch in sha256.lower()):
        return None
    if extensao not in ("png", "jpg", "gif", "webp"):
        return None
    candidate = media_dir(db_path) / f"{sha256.lower()}.{extensao}"
    return candidate if candidate.is_file() else None


def read_media(db_path, sha256: str, extensao: str) -> bytes | None:
    path = media_path(db_path, sha256, extensao)
    return path.read_bytes() if path else None

def delete_media(db_path, sha256: str, extensao: str) -> bool:
    """Remove o arquivo da mídia do disco (idempotente e restrito ao diretório de mídia)."""
    path = media_path(db_path, sha256, extensao)
    if path is None:
        return False
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
