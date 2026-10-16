"""Configuração operacional central do Radar (uma fonte de verdade, validável).

Resolve caminhos de forma robusta e **não** depende de `python` do PATH nem de caminhos
temporários: o executável do Python, o banco ativo e o diretório de logs vêm daqui.

Ordem de precedência: defaults → arquivo `radar_ops.json` (raiz do projeto) → variáveis
de ambiente `RADAR_*`. Nada de segredos é lido nem gravado.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_FILENAME = "radar_ops.json"
DEFAULT_DB_RELATIVE = "data/radar.sqlite3"
DEFAULT_LOGS_RELATIVE = "logs"

# Fontes habilitadas por padrão (identificadores estáveis das fases anteriores).
DEFAULT_SOURCES = ("guajara", "dou", "fgv", "quadrix", "pci")

DEFAULTS = {
    "project_root": None,          # resolvido para a raiz do repositório
    "python": None,                # resolvido para sys.executable
    "db_path": DEFAULT_DB_RELATIVE,
    "logs_dir": DEFAULT_LOGS_RELATIVE,
    "monitor_interval_hours": 6,
    "queue_interval_hours": 6,
    "batch_limit": 10,
    "source_timeout_seconds": 30,
    "max_documents_per_source": 5,
    "analyze": True,
    "sources": {},                 # {nome: {"enabled": bool, "min_interval_hours": int}}
    "notifications": {
        "local": False,
        "categories": ["prazo_isencao", "retificacao", "falha_fonte"],
        "min_severity": "atencao",
        "max_per_cycle": 5,
        "min_interval_seconds": 30,
        "base_url": "http://127.0.0.1:8000",
    },
    "triage_horizon_days": 7,
    "max_new_alerts_per_cycle": 200,
}

# Intervalos mínimos por fonte (evita consultas repetidas entre ciclos).
DEFAULT_MIN_INTERVAL_HOURS = {
    "guajara": 6, "dou": 6, "fgv": 6, "quadrix": 6, "pci": 6,
}


def project_root() -> Path:
    """Raiz do repositório (dois níveis acima deste arquivo: ``radar/ops_config.py``)."""
    return Path(__file__).resolve().parent.parent


def default_config_path(root: Path | None = None) -> Path:
    return (root or project_root()) / CONFIG_FILENAME


def _env_overrides() -> dict:
    mapping = {
        "RADAR_DB": "db_path",
        "RADAR_LOGS_DIR": "logs_dir",
        "RADAR_PYTHON": "python",
        "RADAR_PROJECT_ROOT": "project_root",
        "RADAR_MONITOR_INTERVAL_HOURS": ("monitor_interval_hours", int),
        "RADAR_QUEUE_INTERVAL_HOURS": ("queue_interval_hours", int),
        "RADAR_BATCH_LIMIT": ("batch_limit", int),
    }
    overrides = {}
    for env_name, target in mapping.items():
        raw = os.environ.get(env_name)
        if raw is None or raw == "":
            continue
        if isinstance(target, tuple):
            key, caster = target
            try:
                overrides[key] = caster(raw)
            except ValueError:
                continue
        else:
            overrides[target] = raw
    return overrides


def load_config(path: str | Path | None = None) -> dict:
    """Carrega e resolve a configuração (defaults → arquivo → ambiente)."""
    root = project_root()
    file_cfg = {}
    config_path = Path(path) if path else default_config_path(root)
    if config_path.exists():
        try:
            file_cfg = json.loads(config_path.read_text(encoding="utf-8")) or {}
        except (ValueError, OSError):
            file_cfg = {}

    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in file_cfg.items() if k in DEFAULTS})
    cfg.update(_env_overrides())

    # Raiz do projeto: explícita ou a do repositório.
    root = Path(cfg.get("project_root") or root).expanduser().resolve()
    cfg["project_root"] = str(root)

    # Python: explícito ou o interpretador atual (o validado no projeto).
    cfg["python"] = str(cfg.get("python") or sys.executable)

    # Caminhos relativos são resolvidos contra a raiz do projeto.
    cfg["db_path"] = _resolve(root, cfg["db_path"])
    cfg["logs_dir"] = _resolve(root, cfg["logs_dir"])

    # Normaliza as fontes (merge com os defaults por fonte).
    sources = {}
    file_sources = cfg.get("sources") or {}
    for name in DEFAULT_SOURCES:
        entry = file_sources.get(name) or {}
        sources[name] = {
            "enabled": bool(entry.get("enabled", True)),
            "min_interval_hours": int(entry.get("min_interval_hours",
                                                DEFAULT_MIN_INTERVAL_HOURS.get(name, 6))),
        }
    cfg["sources"] = sources

    notes = dict(DEFAULTS.get("notifications") or {})
    notes.update(cfg.get("notifications") or {})
    cfg["notifications"] = notes
    return cfg

def _resolve(root: Path, value: str) -> str:
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = root / p
    return str(p.resolve())


def enabled_source_names(cfg: dict) -> list[str]:
    return [name for name, opts in cfg["sources"].items() if opts.get("enabled")]


def validate_config(cfg: dict) -> list[str]:
    """Devolve a lista de erros de configuração (vazia = válida)."""
    errors = []
    root_value = cfg.get("project_root")
    if not root_value:
        errors.append("project_root não definido")
    elif not Path(root_value).is_dir():
        errors.append(f"project_root inexistente: {root_value}")
    python = cfg.get("python")
    if not python or not Path(python).exists():
        errors.append(f"python inexistente: {python}")
    db = cfg.get("db_path")
    if not db:
        errors.append("db_path não definido")
    else:
        # O banco pode ainda não existir: o ciclo o cria. Basta que o diretório seja
        # criável (o ancestral existente mais próximo é um diretório).
        parent = Path(db).parent
        ancestor = parent
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        if not ancestor.is_dir():
            errors.append(f"diretório do banco inválido: {parent}")
    if not isinstance(cfg.get("batch_limit"), int) or isinstance(cfg.get("batch_limit"), bool) \
            or cfg.get("batch_limit") < 1:
        errors.append("batch_limit deve ser inteiro >= 1")
    if not enabled_source_names(cfg):
        errors.append("nenhuma fonte habilitada")
    return errors


def save_default_config(path: str | Path | None = None, *, overwrite: bool = False) -> Path:
    """Escreve um `radar_ops.json` com os defaults resolvidos (sem segredos)."""
    target = Path(path) if path else default_config_path()
    if target.exists() and not overwrite:
        return target
    cfg = load_config()
    payload = {
        "project_root": cfg["project_root"],
        "python": cfg["python"],
        "db_path": "data/radar.sqlite3",
        "logs_dir": "logs",
        "monitor_interval_hours": cfg["monitor_interval_hours"],
        "queue_interval_hours": cfg["queue_interval_hours"],
        "batch_limit": cfg["batch_limit"],
        "source_timeout_seconds": cfg["source_timeout_seconds"],
        "max_documents_per_source": cfg["max_documents_per_source"],
        "analyze": cfg["analyze"],
        "sources": cfg["sources"],
        "notifications": cfg["notifications"],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
