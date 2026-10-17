"""Simulados: seleção de questões, cronômetro, expiração e correção (Fase 23).

Implementação **própria**. O ExamSim (`rmssantos/examsim`) tem software MIT, mas o motor é
acoplado ao navegador e o **conteúdo de questões é explicitamente não redistribuível**
(`CONTENT-LICENSE.md`), então nada dele foi copiado — nem código de conteúdo, nem pacotes.

Regras de domínio:

- A seleção **nunca duplica** questão na mesma prova (por ``questao_id``).
- A prova guarda a **versão** de cada questão; a revisão posterior reflete o que foi aplicado.
- O tempo é calculado no **servidor** (``iniciado_em`` persistido), não no relógio do
  navegador. Uma prova cujo tempo expirou enquanto o app estava fechado é finalizada como
  ``expirado`` na próxima leitura.
- Questão não respondida **não** é erro na prática; num simulado **finalizado** ela entra no
  denominador (regra explícita), e o resultado informa isso.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

MAX_DURATION_SECONDS = 8 * 3600


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


def select_questions(questions, *, limit, seed=None, shuffle=True,
                     exclude_answered=(), disciplina=None, topico=None,
                     dificuldade=None, tags=None) -> list[dict]:
    """Seleciona questões elegíveis **sem duplicação**, de forma determinística com ``seed``.

    Só entram questões ``ativo``. ``exclude_answered`` remove ids já respondidos. A ordem é
    estável para o mesmo ``seed`` (reprodutível em teste e em retomada).
    """
    limit = max(0, int(limit))
    excluded = set(exclude_answered or ())
    wanted_tags = {str(t).strip().lower() for t in (tags or []) if str(t).strip()}
    pool, seen = [], set()
    for question in questions or []:
        qid = question.get("id")
        if not qid or qid in seen or qid in excluded:
            continue
        if question.get("estado") != "ativo":
            continue
        if disciplina and (question.get("disciplina") or "") != disciplina:
            continue
        if topico and (question.get("topico") or "") != topico:
            continue
        if dificuldade and (question.get("dificuldade") or "") != dificuldade:
            continue
        if wanted_tags:
            have = {str(t).strip().lower() for t in (question.get("tags") or [])}
            if not (wanted_tags & have):
                continue
        seen.add(qid)
        pool.append(question)

    if shuffle:
        pool = sorted(pool, key=lambda q: _shuffle_key(q["id"], seed))
    return pool[:limit]


def _shuffle_key(question_id: str, seed) -> str:
    """Chave de ordenação estável e determinística (hash de ``seed:id``)."""
    raw = f"{seed if seed is not None else ''}:{question_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def remaining_seconds(started_at, duration_seconds, *, now=None) -> int | None:
    """Segundos restantes (servidor). ``None`` quando a prova não tem limite de tempo."""
    if not duration_seconds:
        return None
    start = _parse_instant(started_at)
    if start is None:
        return None
    current = _parse_instant(now) if now else datetime.now(timezone.utc)
    elapsed = int((current - start).total_seconds())
    return max(0, int(duration_seconds) - max(0, elapsed))


def is_expired(started_at, duration_seconds, *, now=None) -> bool:
    remaining = remaining_seconds(started_at, duration_seconds, now=now)
    return remaining is not None and remaining <= 0


def elapsed_seconds(started_at, finished_at=None, *, now=None) -> int:
    start = _parse_instant(started_at)
    if start is None:
        return 0
    end = _parse_instant(finished_at) if finished_at else (_parse_instant(now) if now else datetime.now(timezone.utc))
    if end is None:
        return 0
    return max(0, int((end - start).total_seconds()))


def result(items, *, duration_seconds=None, started_at=None, finished_at=None, now=None,
           expired=False) -> dict:
    """Corrige o simulado **a partir das questões originalmente aplicadas** (``items``).

    ``items``: ``[{questao_id, questao_versao, gabarito, resposta, respondida, disciplina,
    topico}]``. Brancos entram no denominador (regra do simulado finalizado) e são
    contabilizados à parte — nunca escondidos.
    """
    total = len(items or [])
    respondidas = [i for i in items or [] if i.get("respondida")]
    acertos = [i for i in respondidas if str(i.get("resposta") or "").upper()
               == str(i.get("gabarito") or "").upper()]
    erros = len(respondidas) - len(acertos)
    brancos = total - len(respondidas)
    pct = int((len(acertos) / total) * 100 + 0.5) if total else None
    return {"total": total, "respondidas": len(respondidas), "acertos": len(acertos),
            "erros": erros, "brancos": brancos, "pct": pct,
            "tempo_usado_segundos": elapsed_seconds(started_at, finished_at, now=now),
            "duracao_segundos": duration_seconds, "expirado": bool(expired),
            "basis": (f"{pct}% de acerto sobre {total} questão(ões) aplicada(s); "
                      f"{brancos} em branco contam no denominador"
                      if total else "simulado sem questões: percentual não calculável"),
            "erradas": [i.get("questao_id") for i in respondidas
                        if str(i.get("resposta") or "").upper() != str(i.get("gabarito") or "").upper()],
            "por_disciplina": _group(items, "disciplina"),
            "por_topico": _group(items, "topico")}


def _group(items, key):
    groups: dict[str, list] = {}
    for item in items or []:
        name = (item.get(key) or "").strip() or "(sem informação)"
        groups.setdefault(name, []).append(item)
    out = []
    for name, rows in groups.items():
        respondidas = [r for r in rows if r.get("respondida")]
        acertos = [r for r in respondidas if str(r.get("resposta") or "").upper()
                   == str(r.get("gabarito") or "").upper()]
        pct = int((len(acertos) / len(rows)) * 100 + 0.5) if rows else None
        out.append({"grupo": name, "total": len(rows), "acertos": len(acertos),
                    "erros": len(respondidas) - len(acertos),
                    "brancos": len(rows) - len(respondidas), "pct": pct})
    out.sort(key=lambda g: (-g["total"], g["grupo"]))
    return out
