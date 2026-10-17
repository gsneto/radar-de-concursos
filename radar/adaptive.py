"""Prática adaptativa determinística e explicável (Fase 24).

## Por que não IRT nem Elo (pesquisa da fase)

- **IRT (2PL)**: exige parâmetros calibrados por item (dificuldade/discriminação) e volume de
  respostas para estimar habilidade. O Radar tem um banco pequeno e criado pelo usuário, sem
  calibração — usar IRT daria números com aparência científica e validade nenhuma.
- **Elo/Glicko**: melhor que IRT aqui, mas ainda exige rating de dificuldade por item que o
  Radar não possui; introduziria um segundo modelo de "habilidade" concorrente com o perfil
  declarado. Fica registrado como caminho futuro **se** houver volume e calibração.
- **Escolhido**: pontuação de **fraqueza ponderada**, determinística, auditável e testável.
  Cada fator tem peso fixo e motivo textual; empates são resolvidos por hash estável
  (`seed:id`), então o mesmo estado produz a mesma ordem.

## Regras de honestidade

- Com **poucas tentativas** por tópico (`MIN_EVIDENCE`), a confiança é ``baixa`` e o peso de
  fraqueza é limitado — evita concluir "ponto fraco" a partir de 1 erro.
- O desempenho **não** sobrescreve a familiaridade declarada: ele entra como evidência
  adicional (fator `lacuna_perfil` só lê o perfil, nunca escreve).
- A sessão adaptativa **não** é comparável a um simulado tradicional: a seleção muda. O
  resultado informa isso explicitamente.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

ALGORITHM_VERSION = "adaptive_v1"

# Evidência mínima por tópico para confiar em uma taxa de acerto.
MIN_EVIDENCE = 3
# Janela de tentativas recentes consideradas por tópico.
RECENT_WINDOW = 8
# Dias sem praticar a partir dos quais a revisão é considerada atrasada.
STALE_DAYS = 14

# Pesos (máximo de cada fator). Somam 10 — a explicação lista a contribuição de cada um.
WEIGHTS = {
    "erro_recente": 3,        # 0..3 proporção de erros recentes (com evidência suficiente)
    "pouco_praticado": 2,     # 0..2 tópico com 0/1/2 tentativas
    "revisao_atrasada": 2,    # 0..2 dias desde a última prática
    "lacuna_perfil": 2,       # 0..2 perfil declara não conhecer / precisa revisar
    "dificuldade": 1,         # 0..1 preferência leve por dificuldade média
}
MAX_SCORE = sum(WEIGHTS.values())

MODES = ("tradicional", "adaptativa", "revisao_erros", "personalizada")


def _parse_day(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _days_since(value, now) -> float | None:
    parsed = _parse_day(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 86400.0)


def topic_history(attempts, *, now=None) -> dict:
    """Agrega o histórico por tópico: tentativas, acertos, erros recentes e última prática.

    Considera apenas tentativas **respondidas** (branco não é erro nem acerto).
    """
    now = _parse_day(now) if now else datetime.now(timezone.utc)
    ordered = sorted(
        (a for a in attempts or [] if a.get("respondida")),
        key=lambda a: (_parse_day(a.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
                       str(a.get("created_at") or "")),
    )
    out: dict[str, dict] = {}
    for attempt in ordered:
        topic = (attempt.get("topico") or "").strip() or "(sem tópico)"
        entry = out.setdefault(topic, {"topico": topic, "tentativas": 0, "acertos": 0,
                                       "erros": 0, "ultima_pratica": None, "recentes": []})
        entry["tentativas"] += 1
        correct = attempt.get("correta") is True
        entry["acertos" if correct else "erros"] += 1
        created = attempt.get("created_at")
        parsed = _parse_day(created)
        if parsed is not None and (entry["ultima_pratica"] is None
                                   or parsed > _parse_day(entry["ultima_pratica"])):
            entry["ultima_pratica"] = created
        entry["recentes"].append(correct)
    for entry in out.values():
        entry["recentes"] = entry["recentes"][-RECENT_WINDOW:]
    return out


def _fator_erro_recente(entry, now):
    """Peso do erro recente. Com pouca evidência o peso é **limitado** (nunca conclusão forte)."""
    if entry is None or not entry["recentes"]:
        return 0, "sem tentativas recentes"
    recent = entry["recentes"]
    errors = sum(1 for ok in recent if not ok)
    ratio = errors / len(recent)
    if entry["tentativas"] < MIN_EVIDENCE:
        # 1–2 tentativas: o erro conta, mas no máximo 1 ponto (evidência insuficiente).
        if errors:
            return 1, (f"{errors}/{len(recent)} erro(s) recente(s) — evidência insuficiente "
                       "para peso alto")
        return 0, "sem erros, mas evidência ainda é insuficiente"
    if ratio >= 0.6:
        return 3, f"{errors}/{len(recent)} erros recentes neste tópico"
    if ratio >= 0.3:
        return 2, f"{errors}/{len(recent)} erros recentes neste tópico"
    if errors:
        return 1, f"{errors}/{len(recent)} erro(s) recente(s)"
    return 0, "nenhum erro recente"


def _fator_pouco_praticado(entry):
    if entry is None or entry["tentativas"] == 0:
        return 2, "tópico ainda não praticado"
    if entry["tentativas"] == 1:
        return 2, "apenas 1 tentativa registrada"
    if entry["tentativas"] == 2:
        return 1, "apenas 2 tentativas registradas"
    return 0, f"{entry['tentativas']} tentativas registradas"


def _fator_revisao_atrasada(entry, now):
    if entry is None or not entry.get("ultima_pratica"):
        return 0, "sem prática registrada"
    days = _days_since(entry["ultima_pratica"], now)
    if days is None:
        return 0, "data de prática inválida"
    if days >= 2 * STALE_DAYS:
        return 2, f"sem praticar há {int(days)} dias"
    if days >= STALE_DAYS:
        return 1, f"sem praticar há {int(days)} dias"
    return 0, f"praticado há {int(days)} dia(s)"


def _fator_lacuna_perfil(profile_entry):
    if not profile_entry:
        return 0, "tópico sem avaliação no perfil"
    if profile_entry.get("revisar"):
        return 2, "perfil marcou este tópico para revisão"
    nivel = profile_entry.get("nivel")
    if nivel == "nao_conheco":
        return 2, "perfil declara que ainda não conhece o tópico"
    if nivel == "nao_avaliado":
        return 1, "familiaridade ainda não avaliada"
    if nivel == "basico":
        return 1, "perfil declara conhecimento básico"
    return 0, "perfil declara conhecimento intermediário/avançado"


def _fator_dificuldade(question, accuracy):
    difficulty = (question.get("dificuldade") or "").strip()
    if difficulty not in ("facil", "media", "dificil"):
        return 0, "questão sem dificuldade declarada"
    if accuracy is None:
        return 1 if difficulty == "media" else 0, (
            f"dificuldade {difficulty} (sem histórico: preferência por nível médio)")
    if accuracy >= 0.8 and difficulty == "dificil":
        return 1, "bom desempenho: incluir questão difícil"
    if accuracy < 0.4 and difficulty == "facil":
        return 1, "desempenho baixo: reforçar com questão fácil"
    return 0, f"dificuldade {difficulty} adequada ao desempenho atual"


def score_question(question, *, history, profile, now=None, global_accuracy=None) -> dict:
    """Pontua uma questão para prática adaptativa, com fatores e motivos rastreáveis."""
    now = _parse_day(now) if now else datetime.now(timezone.utc)
    topic = (question.get("topico") or "").strip() or "(sem tópico)"
    entry = history.get(topic)
    key = question.get("conceito_key")
    profile_entry = (profile or {}).get(key) if key else None
    factors = []
    for name, result in (
        ("erro_recente", _fator_erro_recente(entry, now)),
        ("pouco_praticado", _fator_pouco_praticado(entry)),
        ("revisao_atrasada", _fator_revisao_atrasada(entry, now)),
        ("lacuna_perfil", _fator_lacuna_perfil(profile_entry)),
        ("dificuldade", _fator_dificuldade(question, global_accuracy)),
    ):
        points, reason = result
        factors.append({"fator": name, "pontos": points, "max": WEIGHTS[name], "motivo": reason})
    score = sum(f["pontos"] for f in factors)
    confidence = "baixa" if (entry is None or entry["tentativas"] < MIN_EVIDENCE) else "media"
    if entry is not None and entry["tentativas"] >= MIN_EVIDENCE * 2:
        confidence = "alta"
    return {"score": score, "max_score": MAX_SCORE, "confidence": confidence,
            "topico": topic, "factors": factors,
            "explicacao": "; ".join(f["motivo"] for f in factors if f["pontos"] > 0)
                           or "tópico sem sinal de fraqueza"}


def _stable_key(question_id, seed) -> str:
    raw = f"{ALGORITHM_VERSION}:{seed if seed is not None else ''}:{question_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def rank_questions(questions, *, history, profile, now=None, seed=None,
                   global_accuracy=None) -> list[dict]:
    """Ordena candidatos por fraqueza (maior primeiro), com desempate determinístico."""
    scored = []
    for question in questions or []:
        result = score_question(question, history=history, profile=profile, now=now,
                                global_accuracy=global_accuracy)
        scored.append({**result, "questao_id": question.get("id"), "questao": question})
    scored.sort(key=lambda item: (-item["score"], _stable_key(item["questao_id"], seed)))
    return scored


def next_question(questions, *, history, profile, now=None, seed=None, exclude=(),
                  global_accuracy=None) -> dict | None:
    """Próxima questão da sessão adaptativa (``None`` se não houver candidato)."""
    excluded = set(exclude or ())
    pool = [q for q in questions or [] if q.get("id") not in excluded and q.get("estado") == "ativo"]
    ranked = rank_questions(pool, history=history, profile=profile, now=now, seed=seed,
                            global_accuracy=global_accuracy)
    return ranked[0] if ranked else None


def session_plan(questions, *, history, profile, limit, now=None, seed=None,
                 global_accuracy=None) -> list[dict]:
    """Plano de sessão adaptativa: os ``limit`` candidatos de maior fraqueza, já ordenados."""
    ranked = rank_questions(questions, history=history, profile=profile, now=now, seed=seed,
                            global_accuracy=global_accuracy)
    return ranked[:max(0, int(limit))]


def review_questions(attempts, questions) -> list[dict]:
    """Questões previamente erradas (modo revisão de erros), sem duplicar."""
    wrong = {a.get("questao_id") for a in attempts or []
             if a.get("respondida") and a.get("correta") is False}
    return [q for q in questions or [] if q.get("id") in wrong and q.get("estado") == "ativo"]


MODE_LABELS = {
    "tradicional": "Simulado tradicional (conjunto fixo)",
    "adaptativa": "Prática adaptativa (próxima questão por desempenho)",
    "revisao_erros": "Revisão de erros",
    "personalizada": "Prática personalizada",
}

# Aviso obrigatório: resultado adaptativo não é comparável a um simulado tradicional.
ADAPTIVE_CAVEAT = (
    "Sessão adaptativa: as questões foram escolhidas pelo seu desempenho, então o percentual "
    "de acerto NÃO é comparável ao de um simulado tradicional de conjunto fixo."
)
