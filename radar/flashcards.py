"""Flashcards: agendamento SM-2-lite e lógica pura de revisão (Fase 23).

O agendador é **adaptado** de `mqqikq/flashcards-api` (`app/scheduler.py`, licença MIT, commit
`894ff4a`), preservando a semântica do algoritmo original:

- ``quality < 3`` é um lapso: zera repetições e volta o intervalo para 1 dia, **sem** mexer no
  fator de facilidade (só um acerto ajusta o ease).
- ``quality >= 3`` avança: 1 dia na 1ª, 6 dias na 2ª, e ``intervalo * ease`` depois — usando o
  ease **anterior** a esta revisão.
- O ease nunca cai abaixo de 1.3.

Adaptações documentadas em `THIRD_PARTY_NOTICES.md`: retorno como ``dict`` (sem dataclass
própria), datas em ``date``/ISO e validação de faixa preservada.

Decisão de arquitetura (ver doc da fase): **não** se adotou FSRS — exigiria a dependência
externa ``typing-extensions``, quebrando o princípio *stdlib-only*, e o SM-2-lite cobre o
escopo. Também não se mantêm dois agendadores: a revisão de **tópicos** (Fase 21,
``study.revision_dates``) permanece separada e intocada; a de **cartões** é esta.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

DEFAULT_EASE = 2.5
MIN_EASE = 1.3

# Avaliações aceitas (0–5, como no SM-2 clássico). 0–2 = lapso; 3–5 = acerto.
QUALITY_MIN = 0
QUALITY_MAX = 5
LAPSE_THRESHOLD = 3


def _parse_day(value) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def utc_today(now=None) -> date:
    """Data UTC — a mesma referência para vencimento e estatísticas (evita divergência)."""
    if isinstance(now, str):
        parsed = _parse_day(now)
        if parsed:
            return parsed
    if isinstance(now, datetime):
        return (now if now.tzinfo else now.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).date()
    return datetime.now(timezone.utc).date()


def schedule_review(*, ease: float, interval: int, repetitions: int, quality: int,
                    today=None) -> dict:
    """Calcula o próximo estado de agendamento do cartão (SM-2-lite, adaptado — MIT).

    Devolve ``{ease, intervalo, repeticoes, proxima_revisao}`` com a data ISO do próximo
    vencimento. Determinístico: mesmas entradas produzem a mesma saída.
    """
    if not isinstance(quality, int) or isinstance(quality, bool) or not (
            QUALITY_MIN <= quality <= QUALITY_MAX):
        raise ValueError(f"qualidade deve estar entre {QUALITY_MIN} e {QUALITY_MAX}")
    ease = float(ease)
    if ease < MIN_EASE:
        ease = MIN_EASE
    interval = max(0, int(interval))
    repetitions = max(0, int(repetitions))
    day = _parse_day(today) or utc_today()

    if quality < LAPSE_THRESHOLD:
        repetitions = 0
        interval = 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 6
        else:
            interval = round(interval * ease)
        ease = max(MIN_EASE, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

    return {"ease": ease, "intervalo": interval, "repeticoes": repetitions,
            "proxima_revisao": (day + timedelta(days=interval)).isoformat()}


def is_due(card: dict, *, today=None) -> bool:
    """O cartão está vencido para revisão? (cartão novo, sem data, conta como vencido)."""
    if card.get("estado") != "ativo":
        return False
    due = _parse_day(card.get("proxima_revisao"))
    if due is None:
        return True
    return due <= (_parse_day(today) or utc_today())


def queue(cards, *, today=None, limit=None) -> dict:
    """Separa os cartões em ``novos``, ``vencidos`` e ``futuros``, na ordem de estudo.

    Cartões novos (nunca revisados) primeiro, depois os vencidos por data mais antiga. Nunca
    inclui arquivados. ``limit`` corta a fila final (sem descartar os demais: eles continuam
    no banco e voltam na próxima consulta).
    """
    today_day = _parse_day(today) or utc_today()
    novos, vencidos, futuros = [], [], []
    for card in cards or []:
        if card.get("estado") != "ativo":
            continue
        due = _parse_day(card.get("proxima_revisao"))
        if due is None or not card.get("revisoes"):
            novos.append(card)
        elif due <= today_day:
            vencidos.append(card)
        else:
            futuros.append(card)
    vencidos.sort(key=lambda c: (c.get("proxima_revisao") or "", c.get("id") or ""))
    ordered = novos + vencidos
    if limit is not None:
        ordered = ordered[:max(0, int(limit))]
    return {"novos": novos, "vencidos": vencidos, "futuros": futuros,
            "fila": ordered, "total_pendente": len(novos) + len(vencidos)}


def stats(cards, reviews, *, today=None) -> dict:
    """Estatísticas de prática **derivadas dos dados persistidos** (nunca fictícias).

    ``reviews`` são os registros de revisão (``{qualidade, revisado_em}``). O percentual de
    acerto considera apenas revisões efetivamente registradas (não cartões abertos).
    """
    today_day = _parse_day(today) or utc_today()
    ativos = [c for c in cards or [] if c.get("estado") == "ativo"]
    arquivados = [c for c in cards or [] if c.get("estado") == "arquivado"]
    novos = sum(1 for c in ativos if not c.get("revisoes"))
    pendentes = sum(1 for c in ativos if is_due(c, today=today_day))
    acertos = sum(1 for r in reviews or [] if int(r.get("qualidade", 0)) >= LAPSE_THRESHOLD)
    total_revisoes = len(reviews or [])
    pct = int((acertos / total_revisoes) * 100 + 0.5) if total_revisoes else None
    return {"ativos": len(ativos), "arquivados": len(arquivados), "novos": novos,
            "pendentes": pendentes, "revisoes": total_revisoes, "acertos": acertos,
            "pct_acerto": pct,
            "basis": (f"{pct}% sobre {total_revisoes} revisão(ões) registrada(s)"
                      if total_revisoes else "sem revisões registradas: acerto não calculável")}
