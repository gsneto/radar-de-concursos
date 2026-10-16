"""Resolvers de referência oficial para a fila de confirmação.

Cada resolver recebe o candidato (metadados de descoberta) e devolve uma referência
oficial plausível, ou ``None``. A rede é injetável (testes). Nenhuma URL da PCI
autoriza download: a URL oficial descoberta passa pelas defesas de download e pela
allowlist do projeto.

Fontes: catálogo oficial da **FGV Conhecimento** e a **busca pública do DOU**
(Imprensa Nacional). Não se faz scraping de mecanismos de busca.
"""

from __future__ import annotations

import json
import re
import unicodedata
import urllib.request

from radar import dou_source
from radar.quadrix_source import QUADRIX_AGENCY

FGV_CATALOG_URL = "https://conhecimento.fgv.br/concursos"
DOU_SEARCH_URL = "https://www.in.gov.br/consulta/-/buscar/dou"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TIMEOUT_SECONDS = 30
MAX_BYTES = 4 * 1024 * 1024

_STOPWORDS = {"de", "da", "do", "das", "dos", "e", "para", "concurso", "publico", "publica",
              "processo", "seletivo", "simplificado", "abre", "edital", "retificacao", "vagas",
              "cargo", "cargos", "nivel", "medio", "superior"}


def _normalize(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", ascii_text.lower()).split())


def _tokens(text) -> set[str]:
    return {t for t in _normalize(text).split() if len(t) >= 4 and t not in _STOPWORDS}


def _http_get(url: str, opener=None) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"})
    if opener is None:
        opener = urllib.request.urlopen
    with opener(request, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("resposta excede o limite de bytes")
    return dou_source.decode_body(body)


class FgvCatalogResolver:
    """Casa o candidato com o catálogo oficial da FGV (banca organizadora)."""

    name = "fgv"

    def __init__(self, catalog_fetcher=None):
        self._fetch = catalog_fetcher or (lambda: _http_get(FGV_CATALOG_URL))
        self._cache = None

    def _entries(self):
        from radar.fgv_source import parse_catalog
        if self._cache is None:
            self._cache = parse_catalog(self._fetch())
        return self._cache

    def resolve(self, candidate: dict) -> dict | None:
        cand_tokens = _tokens(candidate.get("title") or "")
        if not cand_tokens:
            return None
        try:
            entries = self._entries()
        except Exception:
            return None
        best = None
        best_score = 0
        ties = 0
        for entry in entries:
            entry_tokens = _tokens(entry.get("title") or "")
            shared = cand_tokens & entry_tokens
            if not shared:
                continue
            score = len(shared)
            if score > best_score:
                best, best_score, ties = entry, score, 1
            elif score == best_score:
                ties += 1
        if best is None or best_score < 2:
            return None
        if ties > 1:
            ambiguity = "múltiplos concursos com título semelhante no catálogo"
        elif best_score < 3:
            ambiguity = "correspondência parcial de título"
        else:
            ambiguity = None
        return {
            "official_url": best["url"], "source": "FGV Conhecimento",
            "title": best["title"], "confidence": "alta" if best_score >= 3 else "media",
            "ambiguity": ambiguity,
            "reason": "catálogo FGV por título" if not ambiguity else "título parcialmente coincidente",
        }


class DouSearchResolver:
    """Consulta a busca pública do DOU (federal) e devolve a matéria mais provável."""

    name = "dou"

    def __init__(self, search_fetcher=None):
        self._fetch = search_fetcher or self._default_fetch

    def _default_fetch(self, query: str) -> str:
        from urllib.parse import quote
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=180)
        url = (f"{DOU_SEARCH_URL}?q={quote(query)}&s=todos&exactDate=personalizado"
               f"&publishFrom={start.strftime('%d-%m-%Y')}&publishTo={today.strftime('%d-%m-%Y')}")
        return _http_get(url)

    def _results(self, query: str):
        html = self._fetch(query)
        try:
            return dou_source.parse_edition(html)["items"]
        except (ValueError, json.JSONDecodeError):
            return []

    def resolve(self, candidate: dict) -> dict | None:
        org = candidate.get("title") or ""
        org_tokens = _tokens(org)
        if not org_tokens:
            return None
        query = (" ".join(sorted(org_tokens)) + " concurso")[:120]
        try:
            results = self._results(query)
        except Exception:
            return None
        best = None
        best_score = 0
        for item in results:
            hay = f"{item.get('title','')} {item.get('artType','')} {item.get('hierarchyStr','')} {item.get('content','')}"
            norm_hay = _normalize(hay)
            # Só concursos: descarta licitações, contratos e extratos (falsos positivos).
            if "concurso" not in norm_hay:
                continue
            shared = org_tokens & _tokens(hay)
            score = len(shared)
            if "edital" in _normalize(item.get("artType", "") or item.get("title", "")):
                score += 1  # viés para editais
            if score > best_score:
                best, best_score = item, score
        if best is None or best_score < 2:
            return None
        url_title = best.get("urlTitle")
        if not url_title:
            return None
        return {
            "official_url": "https://www.in.gov.br/web/dou/-/" + str(url_title),
            "source": "Diário Oficial da União (Seção 3)",
            "title": best.get("title") or org,
            "confidence": "media",
            "ambiguity": "matéria do DOU casa por órgão; conferir vínculo" if best_score < 3 else None,
            "reason": "busca pública do DOU por órgão (concurso)",
        }


class QuadrixResolver:
    """Casa o candidato com o catálogo oficial do Quadrix e prefere o edital completo."""

    name = "quadrix"

    def __init__(self, catalog_fetcher=None, detail_fetcher=None):
        if catalog_fetcher is None:
            from radar.quadrix_source import fetch_catalog
            catalog_fetcher = lambda: fetch_catalog("todos", 1, 1000)
        self._fetch_catalog = catalog_fetcher
        if detail_fetcher is None:
            from radar.quadrix_source import fetch_detail
            detail_fetcher = fetch_detail
        self._fetch_detail = detail_fetcher
        self._cache = None

    def _entries(self):
        from radar.quadrix_source import parse_catalog
        if self._cache is None:
            self._cache = parse_catalog(self._fetch_catalog())
        return self._cache

    def _best_edital(self, entry):
        from radar.quadrix_source import parse_detail
        try:
            detail = parse_detail(self._fetch_detail(entry["id"]))
        except Exception:
            return None
        editais = [d for d in detail["documents"] if d["document_type"] == "edital_abertura"]
        if not editais:
            editais = [d for d in detail["documents"] if d["kind"] == "edital"]
        return editais[0] if editais else None

    def resolve(self, candidate: dict) -> dict | None:
        cand_tokens = _tokens(candidate.get("title") or "")
        if not cand_tokens:
            return None
        try:
            entries = self._entries()
        except Exception:
            return None
        best = None
        best_score = 0
        ties = 0
        for entry in entries:
            shared = cand_tokens & _tokens(entry.get("title") or "")
            if not shared:
                continue
            score = len(shared)
            if score > best_score:
                best, best_score, ties = entry, score, 1
            elif score == best_score:
                ties += 1
        if best is None or best_score < 2:
            return None
        if ties > 1:
            ambiguity = "múltiplos certames com título semelhante no catálogo"
        elif best_score < 3:
            ambiguity = "correspondência parcial de título"
        else:
            ambiguity = None
        edital = self._best_edital(best)
        if edital is not None:
            return {
                "official_url": edital["url"], "source": QUADRIX_AGENCY,
                "title": edital["title"], "confidence": "alta" if best_score >= 3 else "media",
                "ambiguity": ambiguity,
                "reason": "edital do concurso no site da banca (Quadrix)",
            }
        # Página oficial localizada, mas sem arquivo recuperável: registra a referência
        # sem baixar (o host do site não é autorizado para download).
        return {
            "official_url": best["url"], "source": QUADRIX_AGENCY, "title": best["title"],
            "confidence": "media", "ambiguity": ambiguity, "no_download": True,
            "reason": "página oficial localizada; sem edital publicado recuperável",
        }


def default_resolvers():
    """Cadeia padrão: bancas (FGV, Quadrix) e depois DOU (federal)."""
    return [FgvCatalogResolver(), QuadrixResolver(), DouSearchResolver()]
