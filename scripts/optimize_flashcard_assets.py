"""Gera variantes WebP otimizadas para todos os flashcards IA em JPG.

Mantém os arquivos `.jpg` originais intactos para fallback `<picture>` e download HD,
gerando `.webp` com redução >= 65% sem exigir pacotes extras no `.venv`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLASHCARDS_DIR = ROOT / "web-react" / "public" / "flashcards"


def _convert_with_pillow(jpg_path: Path, webp_path: Path, quality: int = 80) -> bool:
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError:
        return False

    with Image.open(jpg_path) as img:
        rgb = img.convert("RGB")
        rgb.save(webp_path, format="WEBP", quality=quality, method=6)
    return True


def _convert_with_ffmpeg(jpg_path: Path, webp_path: Path, quality: int = 80) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    cmd = [
        ffmpeg,
        "-y",
        "-v",
        "error",
        "-i",
        str(jpg_path),
        "-c:v",
        "libwebp",
        "-quality",
        str(quality),
        "-compression_level",
        "6",
        str(webp_path),
    ]
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return res.returncode == 0 and webp_path.is_file()


def optimize_all(quality: int = 80) -> int:
    jpg_files = sorted(FLASHCARDS_DIR.glob("*.jpg"))
    if not jpg_files:
        print(f"Nenhum arquivo .jpg encontrado em {FLASHCARDS_DIR}", file=sys.stderr)
        return 1

    total_jpg = 0
    total_webp = 0

    for jpg_path in jpg_files:
        webp_path = jpg_path.with_suffix(".webp")
        ok = _convert_with_pillow(jpg_path, webp_path, quality=quality)
        if not ok:
            ok = _convert_with_ffmpeg(jpg_path, webp_path, quality=quality)
        if not ok:
            print(
                f"Erro: nem Pillow nem ffmpeg disponíveis para converter {jpg_path.name}",
                file=sys.stderr,
            )
            return 1

        jpg_bytes = jpg_path.stat().st_size
        webp_bytes = webp_path.stat().st_size
        total_jpg += jpg_bytes
        total_webp += webp_bytes
        saving = (1.0 - (webp_bytes / jpg_bytes)) * 100.0 if jpg_bytes else 0.0
        print(
            f"{jpg_path.name:28s} {jpg_bytes / 1024:7.1f} KB -> "
            f"{webp_path.name:28s} {webp_bytes / 1024:6.1f} KB (-{saving:.1f}%)"
        )

    overall_saving = (1.0 - (total_webp / total_jpg)) * 100.0 if total_jpg else 0.0
    print(
        f"\nTotal ({len(jpg_files)} flashcards): "
        f"{total_jpg / (1024 * 1024):.2f} MB -> {total_webp / (1024 * 1024):.2f} MB "
        f"(-{overall_saving:.1f}%)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(optimize_all())
