"""Lógica pura da gestão de estudos (progresso, revisões espaçadas, agregados, cronômetro).

Parte deste módulo é **adaptada** do projeto open source `matheussilva421/estudo-organizado`
(licença MIT, commit `eb8cc6cf`): o cálculo de datas de revisão espaçada, a agregação de
tempo estudado por disciplina e o cálculo de progresso de conteúdo. As adaptações e a
atribuição estão documentadas em `docs/superpowers/specs/2026-10-16-study-platform-open-source-mining.md`.

Tudo aqui é **função pura** (sem banco, sem DOM, sem relógio implícito), o que torna o
comportamento testável e determinístico. Dados de estudo são **pessoais** e nunca são
enviados às fontes de concursos nem expostos pelo contrato v1.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Frequências de revisão padrão (dias), no espírito do projeto de origem.
DEFAULT_REVISION_DAYS = (1, 7, 30, 90)

# Estados de progresso de um tópico (separados do catálogo).
TOPIC_STATES = ("nao_iniciado", "estudando", "revisado", "concluido")

# Teto plausível de uma sessão de estudo (24 h): uma sessão que "atravessa" um fechamento
# longo do aplicativo não pode virar horas de estudo dormindo.
MAX_SESSION_SECONDS = 24 * 3600


def local_today(now=None) -> date:
    """Data **local** do usuário (o "dia de estudo" é local, não UTC)."""
    if now is None:
        return datetime.now().astimezone().date()
    parsed = _parse_instant(now)
    return parsed.astimezone().date() if parsed else datetime.now().astimezone().date()


def _parse_day(value) -> date | None:
    """Interpreta ``YYYY-MM-DD`` (ou ISO com hora) como ``date``; ``None`` se inválido."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def revision_dates(data_conclusao, feitas, adiamentos: int = 0, freqs=DEFAULT_REVISION_DAYS) -> list[str]:
    """Datas de revisão pendentes a partir da conclusão, revisões feitas e adiamentos.

    Adaptado de ``calcRevisionDates`` (MIT, estudo-organizado). Cada revisão feita consome
    a próxima frequência; ``adiamentos`` desloca a agenda em dias. Devolve lista vazia quando
    a data de conclusão é inválida ou não há mais revisões.
    """
    base = _parse_day(data_conclusao)
    if base is None:
        return []
    base = base + timedelta(days=max(0, int(adiamentos or 0)))
    done = len(feitas or [])
    return [(base + timedelta(days=int(days))).isoformat() for days in freqs[done:]]


def pending_revisions(progressos, *, today=None, freqs=DEFAULT_REVISION_DAYS) -> list[dict]:
    """Revisões vencidas (``<= hoje``) para os progressos concluídos.

    Adaptado de ``getPendingRevisoes`` (MIT, estudo-organizado). ``progressos`` são dicts com
    ``id``, ``state``, ``data_conclusao``, ``adiamentos`` e ``revisoes`` (lista de datas já
    feitas). Devolve ``[{progresso_id, data}]`` — a primeira data pendente de cada tópico.
    """
    today = _parse_day(today) or local_today()
    out = []
    for item in progressos or []:
        if item.get("state") != "concluido" or not item.get("data_conclusao"):
            continue
        datas = revision_dates(item["data_conclusao"], item.get("revisoes") or [],
                               item.get("adiamentos") or 0, freqs)
        for dia in datas:
            day = _parse_day(dia)
            if day is not None and day <= today:
                out.append({"progresso_id": item.get("id"), "data": dia})
                break
    return out


def _axis(done, total) -> dict:
    safe_done = max(0, int(done)) if isinstance(done, (int, float)) else 0
    safe_total = max(0, int(total)) if isinstance(total, (int, float)) else 0
    # Arredondamento "meio para cima" (igual ao Math.round do frontend; evita o bancário).
    pct = int((safe_done / safe_total) * 100 + 0.5) if safe_total > 0 else 0
    return {"done": safe_done, "total": safe_total, "pct": pct}


def content_progress(disciplinas) -> dict:
    """Progresso de conteúdo (tópicos) por disciplina e geral.

    Adaptado de ``calculateContentProgress`` (MIT, estudo-organizado). ``disciplinas`` é uma
    lista de ``{topicos: [{state}]}``; um tópico conta como feito quando ``state == 'concluido'``.
    """
    disciplinas = [d for d in (disciplinas or []) if d]
    total = sum(len(d.get("topicos") or []) for d in disciplinas)
    done = sum(1 for d in disciplinas for t in (d.get("topicos") or [])
               if t.get("state") == "concluido")
    topics = _axis(done, total)
    return {"topics": topics, "overall": dict(topics)}


def elapsed_seconds(session: dict, *, now=None) -> int:
    """Segundos efetivamente estudados na sessão, considerando pausa/andamento.

    Adaptado de ``getElapsedSeconds`` (MIT, estudo-organizado): soma o acumulado ao segmento
    em andamento (``now - inicio``). Para sessões pausadas/concluídas, apenas o acumulado.
    Nunca devolve valor negativo.
    """
    base = max(0, int(session.get("duracao_segundos") or 0))
    if session.get("estado") != "em_andamento" or not session.get("inicio"):
        return base
    start = _parse_instant(session["inicio"])
    current = _parse_instant(now) if now else datetime.now(timezone.utc)
    if start is None or current is None:
        return base
    return base + max(0, int((current - start).total_seconds()))


def capped_elapsed(session: dict, *, now=None, max_seconds: int = MAX_SESSION_SECONDS) -> int:
    """``elapsed_seconds`` limitado a ``max_seconds`` (evita "tempo dormindo" virar estudo).

    Diferente do projeto de origem (que confia no relógio do navegador), aqui uma sessão que
    atravessa um fechamento longo do aplicativo é truncada no teto plausível.
    """
    return min(elapsed_seconds(session, now=now), max(0, int(max_seconds)))


def _parse_instant(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _study_day(session: dict) -> str | None:
    return (session.get("fim") or session.get("inicio") or "")[:10] or None


def total_study_seconds(sessions, *, days=None, today=None) -> int:
    """Total de segundos das sessões **concluídas** (opcionalmente nos últimos ``days``).

    Adaptado de ``totalStudySeconds`` (MIT, estudo-organizado).
    """
    cutoff = None
    if days:
        ref = _parse_day(today) or datetime.now(timezone.utc).date()
        cutoff = (ref - timedelta(days=int(days) - 1)).isoformat()
    total = 0
    for session in sessions or []:
        if session.get("estado") != "concluida":
            continue
        day = _study_day(session)
        if cutoff and (not day or day < cutoff):
            continue
        total += max(0, int(session.get("duracao_segundos") or 0))
    return total


def minutes_by_discipline(sessions, *, since=None) -> dict:
    """Minutos estudados por disciplina (sessões concluídas), opcionalmente desde ``since``.

    Adaptado de ``computeStudiedMinutesByDiscipline`` (MIT, estudo-organizado).
    """
    totals: dict[str, int] = {}
    for session in sessions or []:
        if session.get("estado") != "concluida":
            continue
        disc = session.get("disciplina_id")
        if not disc:
            continue
        minutos = round(max(0, int(session.get("duracao_segundos") or 0)) / 60)
        if minutos <= 0:
            continue
        day = _study_day(session)
        if since and (not day or day < since):
            continue
        totals[disc] = totals.get(disc, 0) + minutos
    return totals


def validate_session(started_at, finished_at, *, max_seconds: int = 24 * 3600) -> int:
    """Duração válida (s) entre início e fim; rejeita tempos impossíveis/negativos.

    Guarda contra relógio invertido e contra sessões absurdamente longas (padrão 24 h).
    """
    start = _parse_instant(started_at)
    end = _parse_instant(finished_at)
    if start is None or end is None:
        raise ValueError("datas da sessão inválidas")
    seconds = int((end - start).total_seconds())
    if seconds < 0:
        raise ValueError("fim anterior ao início da sessão")
    if seconds > max_seconds:
        raise ValueError("duração da sessão acima do limite plausível")
    return seconds
