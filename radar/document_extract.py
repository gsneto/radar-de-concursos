"""Extrai texto citável de HTML público e PDF textual, sem OCR implícito."""

from __future__ import annotations

import logging
from html.parser import HTMLParser
from io import BytesIO

# O pypdf emite avisos de estrutura no logger/stderr. Eles não são erro de extração e não
# podem poluir a saída JSON da CLI nem o log operacional.
logging.getLogger("pypdf").setLevel(logging.ERROR)


_MAX_BYTES = 20 * 1024 * 1024
# Edições oficiais diárias podem passar de 300 páginas; o limite protege contra
# PDFs anômalos sem impedir o processamento de uma edição real.
_MAX_PAGES = 400
# Listas de resultado chegam a 3.000 páginas. Extrair o **prefixo** documentado é melhor do
# que recusar o documento: o cabeçalho do ato identifica órgão, número e data, e a limitação
# fica registrada na versão. Nunca lemos o arquivo inteiro nesses casos.
# Versão do extrator: gravada no evento de análise para rastrear mudanças de comportamento.
EXTRACTOR_VERSION = "extract_v2"

# Códigos estáveis de falha/limitação de extração.
PDF_SEM_TEXTO = "pdf_sem_texto"
PDF_PAGINAS_EXCEDIDAS = "pdf_paginas_excedidas"
PDF_ILEGIVEL = "pdf_ilegivel"
TIPO_INVALIDO = "tipo_invalido"


class ExtractionError(ValueError):
    """Falha de extração com código estável (nunca só ``ValueError``)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


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
            text = ' | '.join(self._row)
            if text.strip():
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


def extract_document(content: bytes, content_type: str, *, max_pages: int | None = None,
                     prefix_pages: int | None = None) -> dict:
    """Extrai blocos e declara a limitação real (truncamento, ausência de texto).

    ``prefix_pages`` só é usado quando o PDF excede ``max_pages``: lê apenas o prefixo e
    devolve ``truncated=True`` com a contagem total de páginas. Sem ele, o documento é
    recusado com ``pdf_paginas_excedidas`` — nunca silenciosamente ignorado.
    """
    if max_pages is None:
        max_pages = _MAX_PAGES  # resolvido em tempo de chamada (testável)
    if not isinstance(content, bytes) or not content or len(content) > _MAX_BYTES:
        raise ExtractionError('documento_invalido', 'documento vazio ou grande demais')
    mime = content_type.split(';', 1)[0].strip().lower()
    if mime == 'text/html':
        parser = _HTMLBlocks()
        try:
            parser.feed(content.decode('utf-8'))
            parser.close()
        except UnicodeDecodeError as error:
            raise ExtractionError('html_invalido', 'HTML não codificado em UTF-8') from error
        if not parser.blocks:
            raise ExtractionError('html_sem_texto', 'HTML sem texto extraível')
        return {'blocks': parser.blocks, 'truncated': False, 'total_pages': None,
                'limitation': None, 'extractor_version': EXTRACTOR_VERSION}
    if mime != 'application/pdf' or not content.startswith(b'%PDF-'):
        raise ExtractionError(TIPO_INVALIDO, 'tipo ou assinatura de documento inválido')
    try:
        from pypdf import PdfReader
    except ImportError as error:  # dependência ausente não pode prender a versão
        raise ExtractionError('extrator_indisponivel',
                              'pypdf não instalado neste ambiente') from error
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ExtractionError('pdf_criptografado', 'PDF criptografado')
        total = len(reader.pages)
        if total <= 0:
            raise ExtractionError(PDF_SEM_TEXTO, 'PDF sem páginas')
        truncated = False
        limit = total
        if total > max_pages:
            if prefix_pages is None:
                raise ExtractionError(PDF_PAGINAS_EXCEDIDAS,
                                      f'PDF com {total} páginas excede o limite de {max_pages}')
            limit = max(1, min(int(prefix_pages), max_pages))
            truncated = True
        blocks = []
        for number, page in enumerate(reader.pages, 1):
            if number > limit:
                break
            text = ' '.join((page.extract_text() or '').split())
            if text:
                blocks.append(dict(page_number=number, locator=f'página {number}',
                                   start_offset=0, end_offset=len(text), text=text))
        if not blocks:
            raise ExtractionError(PDF_SEM_TEXTO, 'PDF sem texto extraível (possível digitalização)')
        limitation = None
        if truncated:
            limitation = (f'extração limitada às {limit} primeiras de {total} páginas; '
                          f'conteúdo posterior não lido')
        return {'blocks': blocks, 'truncated': truncated, 'total_pages': total,
                'limitation': limitation, 'extractor_version': EXTRACTOR_VERSION}
    except ExtractionError:
        raise
    except Exception as error:
        raise ExtractionError(PDF_ILEGIVEL, 'PDF ilegível') from error


def extract_blocks(content: bytes, content_type: str,
                   max_pages: int | None = None) -> list[dict]:
    """Compatibilidade: apenas os blocos (recusa PDF acima do limite)."""
    return extract_document(content, content_type, max_pages=max_pages)['blocks']
