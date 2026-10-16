"""Notificações nativas do Windows para alertas do Radar.

Canal: toast via Windows Runtime (`Windows.UI.Notifications`), acionado por
`scripts/notify.ps1` (Windows PowerShell). Requer um atalho no Menu Iniciar com o
AppUserModelID (`scripts/install_app_identity.ps1`) — requisito do Windows para
aplicativos desktop **não empacotados**.

Distinção honesta de estados:
- ``enviada`` = o sistema **aceitou** o envio (``Show()`` retornou sucesso).
- **não** significa que o usuário viu (o Windows pode suprimir por foco/assistência).

O canal nativo é opcional: desabilitado, os alertas persistentes continuam na interface.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from radar.document_store import connect_documents

AUMID = "RadarDeConcursos.Radar"
APP_SHORTCUT_NAME = "Radar de Concursos"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
LAST_SENT_KEY = "notifications.last_sent_at"

# Severidade mínima -> ordem (maior = mais grave).
_SEVERITY_RANK = {"info": 0, "atencao": 1, "critico": 2}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(ts):
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _state_get(conn, key):
    row = conn.execute("SELECT value FROM ops_state WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def _state_set(conn, key, value):
    conn.execute(
        "INSERT INTO ops_state(key, value, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, _now()))


def scripts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "scripts"


def app_shortcut_path() -> Path:
    appdata = Path.home() / "AppData" / "Roaming"
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{APP_SHORTCUT_NAME}.lnk"


def native_supported() -> bool:
    """Windows com PowerShell disponível (canal nativo viável)."""
    return sys.platform == "win32" and scripts_dir().joinpath("notify.ps1").exists()


def _run_powershell(script: Path, args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    command.extend(args)
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def ensure_app_identity(shortcut_dir: str | None = None) -> dict:
    """Registra (idempotente) a identidade do app para toasts. Não exige admin.

    ``shortcut_dir`` permite direcionar o atalho para outro diretório (testes isolados);
    em produção o padrão é o Menu Iniciar do usuário.
    """
    script = scripts_dir() / "install_app_identity.ps1"
    if not native_supported() or not script.exists():
        return {"ok": False, "error": "canal nativo indisponível", "shortcut": None}
    args = []
    if shortcut_dir:
        args = ["-ShortcutDir", shortcut_dir]
    try:
        result = _run_powershell(script, args, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "error": type(error).__name__, "shortcut": None}
    target = Path(shortcut_dir) / f"{APP_SHORTCUT_NAME}.lnk" if shortcut_dir else app_shortcut_path()
    return {"ok": result.returncode == 0, "shortcut": str(target),
            "error": None if result.returncode == 0 else (result.stderr or "").strip()[:200]}


def send_toast(title: str, body: str, *, launch: str | None = None, aumid: str = AUMID,
               runner=None) -> dict:
    """Envia um toast. ``runner`` injetável para testes (recebe título/corpo/launch)."""
    if runner is not None:
        return runner(title, body, launch)
    if not native_supported():
        return {"accepted": False, "error": "canal nativo indisponível"}
    script = scripts_dir() / "notify.ps1"
    args = ["-Title", title, "-Body", body, "-Aumid", aumid]
    if launch:
        args.extend(["-Launch", launch])
    try:
        result = _run_powershell(script, args, timeout=20)
    except (OSError, subprocess.SubprocessError) as error:
        return {"accepted": False, "error": type(error).__name__}
    out = (result.stdout or "").strip().splitlines()
    payload = out[-1] if out else ""
    try:
        parsed = json.loads(payload)
        return {"accepted": bool(parsed.get("accepted")), "error": parsed.get("error")}
    except (ValueError, TypeError):
        return {"accepted": False, "error": f"resposta inesperada (rc={result.returncode})"}


# --- Política de notificação -------------------------------------------------

def notification_config(config: dict) -> dict:
    notes = dict(config.get("notifications") or {})
    categories = notes.get("categories")
    if not isinstance(categories, list) or not categories:
        categories = ["prazo_isencao", "retificacao", "falha_fonte"]
    base_url = str(notes.get("base_url") or DEFAULT_BASE_URL)
    # Defesa em profundidade: o destino do clique só pode ser http(s) local/loopback.
    if not base_url.lower().startswith(("http://", "https://")):
        base_url = DEFAULT_BASE_URL
    try:
        min_interval = int(notes.get("min_interval_seconds", 30))
    except (TypeError, ValueError):
        min_interval = 30
    return {
        "enabled": bool(notes.get("local", False)),
        "categories": list(categories),
        "min_severity": notes.get("min_severity", "atencao"),
        "max_per_cycle": int(notes.get("max_per_cycle", 5)),
        "min_interval_seconds": max(0, min_interval),
        "base_url": base_url.rstrip("/"),
    }


def _severity_ok(severity: str, minimum: str) -> bool:
    return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK.get(minimum, 1)


def _contest_url(base_url: str, contest_id: str | None) -> str | None:
    if not contest_id:
        return base_url
    return f"{base_url}/#concurso={contest_id}"


def _clean(text) -> str:
    """Remove caracteres de controle inválidos em XML (o toast é montado em XML)."""
    return "".join(ch for ch in str(text or "") if ch >= " " or ch in "\t").strip()


def _message(alert: dict) -> tuple[str, str]:
    """(título, corpo) do toast — sem segredos e sem afirmar o que é pendente."""
    kind = alert.get("kind")
    titles = {
        "prazo_isencao": "Prazo de isenção da taxa",
        "retificacao": "Retificação publicada",
        "falha_fonte": "Fonte indisponível",
        "novo_candidato": "Novo candidato descoberto",
        "documento_recuperado": "Documento oficial recuperado",
        "lote_confirmacao": "Fila de confirmação",
    }
    title = _clean(titles.get(kind, alert.get("title") or "Radar de Concursos"))
    detail = _clean(alert.get("detail"))
    body = _clean(alert.get("title"))
    if detail:
        body = f"{body} — {detail}"
    return title[:120] or "Radar de Concursos", body[:240]


def dispatch(db_path, config: dict, *, now=None, runner=None, limit=None) -> dict:
    """Envia notificações nativas para alertas elegíveis, com dedup e limite por ciclo.

    - Só alertas não vistos/dispensados, não adiados, de categorias/severidade permitidas.
    - Um alerta já ``enviada`` não é reenviado; ``erro`` é retomado no próximo ciclo.
    - Respeita ``max_per_cycle``; o excedente fica como backlog (não é descartado).
    """
    notes = notification_config(config)
    result = {"enabled": notes["enabled"], "sent": 0, "errors": 0, "considered": 0,
              "suppressed": 0, "backlog": 0, "results": []}
    if not notes["enabled"]:
        return result

    now = now or _now()
    now_dt = _parse(now) or datetime.now(timezone.utc)
    max_cycle = max(0, int(limit if limit is not None else notes["max_per_cycle"]))
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            """SELECT id,kind,severity,contest_id,title,detail,snoozed_until,notify_state,
            notify_attempts FROM alertas
            WHERE seen_at IS NULL AND dismissed_at IS NULL
              AND (snoozed_until IS NULL OR snoozed_until <= ?)
              AND (notify_state IS NULL OR notify_state = 'erro')
            ORDER BY CASE severity WHEN 'critico' THEN 0 WHEN 'atencao' THEN 1 ELSE 2 END,
                     created_at ASC""", (now,)).fetchall()
        keys = ("id", "kind", "severity", "contest_id", "title", "detail", "snoozed_until",
                "notify_state", "notify_attempts")
        candidates = [dict(zip(keys, r)) for r in rows]
        eligible = [a for a in candidates
                    if a["kind"] in notes["categories"]
                    and _severity_ok(a["severity"], notes["min_severity"])]
        result["considered"] = len(eligible)
        result["suppressed"] = len(candidates) - len(eligible)
        # Intervalo mínimo entre envios: evita rajada de toasts em ciclos muito próximos.
        interval = notes["min_interval_seconds"]
        last_sent = _parse(_state_get(conn, LAST_SENT_KEY))
        if eligible and interval > 0 and last_sent is not None:
            if (now_dt - last_sent).total_seconds() < interval:
                result["suppressed"] += len(eligible)
                result["backlog"] = len(eligible)  # retomado no próximo ciclo, não descartado
                return result
        result["backlog"] = max(0, len(eligible) - max_cycle)
        for alert in eligible[:max_cycle]:
            title, body = _message(alert)
            launch = _contest_url(notes["base_url"], alert.get("contest_id"))
            outcome = send_toast(title, body, launch=launch, runner=runner)
            accepted = bool(outcome.get("accepted"))
            state = "enviada" if accepted else "erro"
            error = None if accepted else (outcome.get("error") or "falha ao exibir")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """UPDATE alertas SET notify_state=?, notified_at=?, notify_attempts=notify_attempts+1,
                notify_error=? WHERE id=?""", (state, now, error, alert["id"]))
            if accepted:
                _state_set(conn, LAST_SENT_KEY, now)
            conn.commit()
            result["sent" if accepted else "errors"] += 1
            result["results"].append({"id": alert["id"], "kind": alert["kind"],
                                      "state": state, "error": error})
    finally:
        conn.close()
    return result


def notification_state(db_path, *, limit: int = 200) -> dict:
    """Resumo do estado de notificação (para a saúde/observabilidade)."""
    conn = connect_documents(db_path)
    try:
        by_state = {row[0] or "pendente": row[1] for row in conn.execute(
            "SELECT notify_state, count(*) FROM alertas GROUP BY notify_state")}
        pending = conn.execute(
            """SELECT count(*) FROM alertas WHERE seen_at IS NULL AND dismissed_at IS NULL
            AND (notify_state IS NULL OR notify_state='erro')""").fetchone()[0]
        return {"by_state": by_state, "pending": pending}
    finally:
        conn.close()
