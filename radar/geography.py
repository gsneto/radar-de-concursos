"""Distância geográfica honesta entre municípios de referência.

Calcula distância **geográfica em linha reta** (fórmula de Haversine) entre coordenadas de
municípios. Nunca apresenta essa distância como distância rodoviária ou tempo de viagem —
para isso seria necessário um serviço específico, que este projeto não integra.

Coordenadas vêm de um **seed embutido, limitado e documentado** (capitais e alguns
municípios de referência) mais um **provedor de arquivo local opcional** que o usuário pode
fornecer. Quando não há coordenada, devolve "desconhecida" e o motivo — jamais inventa.

Nenhuma preferência ou dado pessoal é enviado a serviços externos.
"""

from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path

EARTH_RADIUS_KM = 6371.0088

# Seed embutido: (município normalizado, UF) -> (latitude, longitude).
# Fontes: coordenadas aproximadas de capitais e de Paulo Afonso/BA (referência do projeto).
# É um conjunto **limitado**; ausência aqui não significa "inexistente", apenas "não temos
# coordenada". O usuário pode ampliar via arquivo local (`load_provider`).
_SEED = {
    ("salvador", "BA"): (-12.9777, -38.5016),
    ("recife", "PE"): (-8.0476, -34.8770),
    ("maceio", "AL"): (-9.6658, -35.7350),
    ("aracaju", "SE"): (-10.9472, -37.0731),
    ("fortaleza", "CE"): (-3.7319, -38.5267),
    ("natal", "RN"): (-5.7945, -35.2110),
    ("joao pessoa", "PB"): (-7.1195, -34.8450),
    ("teresina", "PI"): (-5.0892, -42.8019),
    ("sao luis", "MA"): (-2.5307, -44.3068),
    ("belem", "PA"): (-1.4558, -48.4902),
    ("manaus", "AM"): (-3.1190, -60.0217),
    ("rio branco", "AC"): (-9.9754, -67.8249),
    ("porto velho", "RO"): (-8.7608, -63.8999),
    ("boa vista", "RR"): (2.8235, -60.6758),
    ("macapa", "AP"): (0.0349, -51.0694),
    ("palmas", "TO"): (-10.1844, -48.3336),
    ("cuiaba", "MT"): (-15.6014, -56.0979),
    ("campo grande", "MS"): (-20.4697, -54.6201),
    ("goiania", "GO"): (-16.6869, -49.2648),
    ("brasilia", "DF"): (-15.7939, -47.8828),
    ("belo horizonte", "MG"): (-19.9167, -43.9345),
    ("vitoria", "ES"): (-20.3155, -40.3128),
    ("rio de janeiro", "RJ"): (-22.9068, -43.1729),
    ("sao paulo", "SP"): (-23.5505, -46.6333),
    ("curitiba", "PR"): (-25.4284, -49.2733),
    ("florianopolis", "SC"): (-27.5954, -48.5480),
    ("porto alegre", "RS"): (-30.0346, -51.2177),
    # Municípios de referência do projeto (não capitais).
    ("paulo afonso", "BA"): (-9.3983, -38.2147),
    ("guajara mirim", "RO"): (-10.7833, -65.3333),
}

_CACHE: dict = {}


def _norm(text) -> str:
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join("".join(ch if ch.isalnum() else " " for ch in ascii_text.lower()).split())


def _valid_coord(lat, lon) -> bool:
    """Coordenada finita e dentro das faixas geográficas válidas."""
    return (isinstance(lat, (int, float)) and not isinstance(lat, bool)
            and isinstance(lon, (int, float)) and not isinstance(lon, bool)
            and math.isfinite(lat) and math.isfinite(lon)
            and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0)


def load_provider(path=None) -> dict:
    """Carrega um provedor de coordenadas local (JSON) e mescla com o seed.

    Formato do arquivo: ``{"Municipio": {"uf": "BA", "lat": -9.4, "lon": -38.2}, ...}``.
    Falha de leitura não quebra o sistema: retorna apenas o seed. Resultado é cacheado.
    """
    key = str(path) if path else ""
    if key in _CACHE:
        return _CACHE[key]
    table = dict(_SEED)
    if path:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _CACHE[key] = table
            return table
        if isinstance(raw, dict):
            for municipio, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                lat, lon = entry.get("lat"), entry.get("lon")
                uf = entry.get("uf")
                if _valid_coord(lat, lon) and isinstance(uf, str):
                    table[(_norm(municipio), uf.upper())] = (float(lat), float(lon))
    _CACHE[key] = table
    return table


def coordinates(municipio, uf, *, provider=None) -> tuple[float, float] | None:
    """Coordenadas ``(lat, lon)`` do município, ou ``None`` quando desconhecidas."""
    if not municipio or not uf:
        return None
    table = provider if provider is not None else load_provider()
    coord = table.get((_norm(municipio), str(uf).upper()))
    if not coord or not _valid_coord(coord[0], coord[1]):
        return None
    return (float(coord[0]), float(coord[1]))


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distância geográfica em linha reta (km) entre dois pares ``(lat, lon)``."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def distance_from_reference(municipio, uf, *, reference, provider=None) -> dict:
    """Distância geográfica (linha reta) do município até a referência do usuário.

    Sempre identifica a natureza do número como ``geografica_linha_reta`` e explica o
    motivo quando a distância é desconhecida. Nunca devolve distância rodoviária.
    """
    out = {"distance_km": None, "kind": "geografica_linha_reta", "known": False, "reason": None}
    if not reference or not reference.get("municipio") or not reference.get("uf"):
        out["reason"] = "referência geográfica do usuário não definida"
        return out
    if not municipio or not uf:
        out["reason"] = "município/UF de destino não confirmados"
        return out
    origin = coordinates(reference.get("municipio"), reference.get("uf"), provider=provider)
    dest = coordinates(municipio, uf, provider=provider)
    if origin is None or dest is None:
        out["reason"] = "sem coordenadas confiáveis para o município"
        return out
    out["distance_km"] = round(haversine_km(origin, dest), 1)
    out["known"] = True
    return out
