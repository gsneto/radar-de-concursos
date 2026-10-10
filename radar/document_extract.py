"""Extrai texto citável de HTML público e PDF textual, sem OCR implícito."""

from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO


_MAX_BYTES = 20 * 1024 * 1024
# Edições oficiais diárias podem passar de 300 páginas; o limite protege contra
# PDFs anômalos sem impedir o processamento de uma edição real.
_MAX_PAGES = 400


class _HTMLBlocks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self._skip = 0
        self._tag = None
        self._parts = []
        self._row = None
        self._cell = None
        self._table = -1

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'head'):
            self._skip += 1
        elif self._skip:
            return
        elif tag == 'table':
            self._table += 1
        elif tag == 'tr':
            self._row = []
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = []
        elif self._row is None and tag in ('p', 'li', 'h1', 'h2', 'h3', 'h4'):
            self._tag = tag
            self._parts = []

    def handle_data(self, data):
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
        elif self._row is None and self._tag:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'head'):
            self._skip = max(0, self._skip - 1)
            return
        if tag in ('td', 'th') and self._cell is not None:
            self._row.append(' '.join(' '.join(self._cell).split()))
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            text = ' | '.join(cell for cell in self._row if cell)
            if text:
                self.blocks.append(dict(page_number=None, locator='linha de tabela',
                                        table=self._table, start_offset=0, end_offset=len(text), text=text))
            self._row = None
        elif tag == self._tag and not self._skip:
            text = ' '.join(' '.join(self._parts).split())
            if text:
                self.blocks.append(dict(page_number=None, locator=self._tag,
                                        start_offset=0, end_offset=len(text), text=text))
            self._tag = None
            self._parts = []


def extract_blocks(content: bytes, content_type: str, max_pages: int = _MAX_PAGES) -> list[dict]:
    if not isinstance(content, bytes) or not content or len(content) > _MAX_BYTES:
        raise ValueError('documento vazio ou grande demais')
    mime = content_type.split(';', 1)[0].strip().lower()
    if mime == 'text/html':
        parser = _HTMLBlocks()
        try:
            parser.feed(content.decode('utf-8'))
            parser.close()
        except UnicodeDecodeError as error:
            raise ValueError('HTML não codificado em UTF-8') from error
        if not parser.blocks:
            raise ValueError('HTML sem texto extraível')
        return parser.blocks
    if mime != 'application/pdf' or not content.startswith(b'%PDF-'):
        raise ValueError('tipo ou assinatura de documento inválido')
    from pypdf import PdfReader
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted or not 0 < len(reader.pages) <= max_pages:
            raise ValueError('PDF criptografado, vazio ou páginas em excesso')
        blocks = []
        for number, page in enumerate(reader.pages, 1):
            text = ' '.join((page.extract_text() or '').split())
            if text:
                blocks.append(dict(page_number=number, locator=f'página {number}',
                                   start_offset=0, end_offset=len(text), text=text))
        if not blocks:
            raise ValueError('PDF sem texto extraível')
        return blocks
    except ValueError:
        raise
    except Exception as error:
        raise ValueError('PDF ilegível') from error
