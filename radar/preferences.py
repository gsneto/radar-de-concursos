"""Preferências geográficas do usuário (locais, validadas, sem dados pessoais).

Guardadas na configuração local (`radar_ops.json`, que é ignorado pelo Git). **Não** são
enviadas a nenhum site de concursos nem a serviços externos. Não se usa endereço residencial
exato: um município de referência é suficiente. Bahia e Pernambuco são **preferências
configuráveis**, nunca filtros obrigatórios — a cobertura nacional é preservada.
"""

from __future__ import annotations

import copy

from radar.location import valid_uf

PRIORITIES = ("equilibrado", "proximidade", "potencial")

DEFAULTS = {
    "reference_municipio": None,   # município de referência do usuário (opcional)
    "reference_uf": None,          # UF de referência (opcional)
    "interest_states": ["BA", "PE"],
    "practical_distance_km": 300,  # faixa considerada "prática" (linha reta)
    "priority": "equilibrado",     # proximidade x potencial
    "coordinates_path": None,      # provedor local opcional de coordenadas (JSON)
}

# Chaves aceitas (evita gravar campos arbitrários/dados pessoais no config).
_ALLOWED = set(DEFAULTS)


class PreferenceError(ValueError):
    """Preferência inválida."""


def validate(prefs: dict) -> dict:
    """Valida e normaliza preferências; rejeita campos desconhecidos e valores inválidos."""
    if not isinstance(prefs, dict):
        raise PreferenceError("preferências devem ser um objeto")
    unknown = sorted(set(prefs) - _ALLOWED)
    if unknown:
        raise PreferenceError(f"campos de preferência desconhecidos: {', '.join(unknown)}")
    out = dict(DEFAULTS)
    out.update({key: prefs[key] for key in prefs})

    ref_uf = out.get("reference_uf")
    if ref_uf is not None and not valid_uf(ref_uf):
        raise PreferenceError("reference_uf inválida")
    out["reference_uf"] = ref_uf.upper() if ref_uf else None

    ref_mun = out.get("reference_municipio")
    if ref_mun is not None:
        if not isinstance(ref_mun, str) or not ref_mun.strip():
            raise PreferenceError("reference_municipio inválido")
        cleaned = ref_mun.strip()
        # Só o nome do município: rejeita endereço residencial (números, vírgulas, "rua/av").
        if (len(cleaned) > 60 or any(ch.isdigit() for ch in cleaned)
                or "," in cleaned or ";" in cleaned
                or any(word in cleaned.lower() for word in
                       ("rua ", "avenida ", "av.", "travessa", "número", "numero", "apto", "apartamento",
                        "cep", "bairro", "lote", "quadra"))):
            raise PreferenceError("reference_municipio deve ser apenas o nome do município")
        ref_mun = cleaned
    out["reference_municipio"] = ref_mun if isinstance(ref_mun, str) and ref_mun else None

    states = out.get("interest_states")
    if not isinstance(states, list) or any(not valid_uf(s) for s in states):
        raise PreferenceError("interest_states deve ser uma lista de UFs válidas")
    out["interest_states"] = sorted({s.upper() for s in states})

    distance = out.get("practical_distance_km")
    if isinstance(distance, bool) or not isinstance(distance, int) or distance < 0:
        raise PreferenceError("practical_distance_km deve ser inteiro não negativo")

    if out.get("priority") not in PRIORITIES:
        raise PreferenceError("priority inválida")

    coords = out.get("coordinates_path")
    if coords is not None and (not isinstance(coords, str) or not coords.strip()):
        raise PreferenceError("coordinates_path inválido")
    out["coordinates_path"] = coords.strip() if isinstance(coords, str) and coords.strip() else None
    return out


def load(config: dict) -> dict:
    """Preferências efetivas (defaults + config), já validadas com tolerância a dados ruins."""
    raw = (config or {}).get("preferences")
    if not isinstance(raw, dict):
        return copy.deepcopy(DEFAULTS)
    try:
        return validate(raw)
    except PreferenceError:
        # Config inválida não deve derrubar a priorização: cai nos defaults.
        return copy.deepcopy(DEFAULTS)
