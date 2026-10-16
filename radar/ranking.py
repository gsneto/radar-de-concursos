"""Ranking explicável de oportunidades de concurso.

Função de pontuação **determinística, versionada e testável**. Cada critério contribui de
forma individual e explicável (``fatores``), e a ausência de dado **não** é tratada como
zero: um fator desconhecido fica de fora da soma e reduz a cobertura, sem misturar
"não sabemos" com "sabemos que não existe".

Princípios de produto (não são probabilidade de aprovação nem garantia de contratação):

- Uma oportunidade **distante** com muitas vagas indígenas imediatas e compatibilidade
  formal confirmada continua visível (piso de pontuação), não é excluída.
- A **urgência** de prazo é uma dimensão independente, exibida à parte — não torna um cargo
  formalmente incompatível uma boa oportunidade.
- Vagas de **cadastro de reserva** nunca são somadas às vagas imediatas.
"""

from __future__ import annotations

RANKING_VERSION = 1

# Pesos/escalas documentados (máximo de pontos por critério).
WEIGHTS = {
    "vagas_indigenas_imediatas": 4,   # 1->1, 2-4->2, 5-9->3, >=10->4
    "vagas_indigenas_reserva": 2,     # 0->0, >=1->1, >=5->2 (exibido à parte)
    "compatibilidade_si": 4,          # aceito 4, categoria 3, ambíguo 1, incompatível 0
    "proximidade_prova": 3,           # <=prática 3, <=2x 2, mais distante 1
    "confianca_evidencia": 2,         # 0..2 conforme dados decisivos confirmados
    "confirmacao_dados": 2,           # 0..2 conforme estado de confirmação dos dados-chave
}
TOTAL_MAX = sum(WEIGHTS.values())

# Piso que mantém visível uma oportunidade distante de alto potencial. Só se aplica a
# **forte** aderência formal (aceitação explícita de Sistemas de Informação) com várias vagas
# indígenas imediatas conhecidas — evita inflar um caso fraco.
EXCEPTIONAL_FLOOR = 10
_EXCEPTIONAL_MIN_INDIGENOUS = 3

SI_CONFIRMED = ("aceito_expressamente", "abrangido_por_categoria")

LABELS = {
    "boa_aderencia": "Boa aderência atual",
    "oportunidade_importante_distante": "Oportunidade importante (distante)",
    "exige_confirmacao": "Exige confirmação",
    "compatibilidade_desfavoravel": "Compatibilidade formal desfavorável",
    "sem_vagas_indigenas": "Sem vagas indígenas confirmadas",
    "sem_dados_suficientes": "Sem dados suficientes",
}


def _vagas_indigenas_imediatas(value):
    if value is None:
        return None, "vagas indígenas imediatas não informadas"
    if value <= 0:
        return 0, "sem vagas indígenas imediatas confirmadas"
    if value == 1:
        return 1, "1 vaga indígena imediata"
    if value <= 4:
        return 2, f"{value} vagas indígenas imediatas"
    if value <= 9:
        return 3, f"{value} vagas indígenas imediatas"
    return 4, f"{value} vagas indígenas imediatas (alta relevância)"


def _vagas_indigenas_reserva(value):
    if value is None:
        return None, "cadastro de reserva indígena não informado"
    if value <= 0:
        return 0, "sem cadastro de reserva indígena"
    if value < 5:
        return 1, f"{value} vaga(s) indígena(s) em cadastro de reserva"
    return 2, f"{value} vagas indígenas em cadastro de reserva"


def _compatibilidade(state):
    if state == "aceito_expressamente":
        return 4, "o edital cita expressamente Sistemas de Informação"
    if state == "abrangido_por_categoria":
        return 3, "abrangido por categoria ampla de TI com abertura a correlatos"
    if state == "ambiguo":
        return 1, "compatibilidade com SI ambígua nos requisitos"
    if state == "incompativel_com_requisito_explicito":
        return 0, "requisito documentado aponta formação incompatível"
    return None, "compatibilidade com SI não informada/extraída"


def _proximidade(distance, practical_km, uf, interest_states):
    if distance is None:
        return None, "distância da prova desconhecida"
    if practical_km and distance <= practical_km:
        return 3, f"prova a {distance} km (dentro da faixa prática)"
    if practical_km and distance <= 2 * practical_km:
        return 2, f"prova a {distance} km (fora da faixa prática)"
    if uf and uf in (interest_states or []):
        return 2, f"prova em {uf} (estado de interesse) a {distance} km"
    return 1, f"prova distante ({distance} km)"


def _confianca_evidencia(confidence):
    if confidence is None:
        return None, "confiança da evidência não determinada"
    if confidence == "alta":
        return 2, "evidência documental de alta confiança"
    if confidence == "media":
        return 1, "evidência documental parcial"
    return 0, "evidência documental frágil"


def _confirmacao(confirmed_fields, total_decisive):
    if total_decisive <= 0:
        return None, "sem campos decisivos identificados"
    ratio = confirmed_fields / total_decisive
    if ratio >= 0.99:
        return 2, "dados decisivos confirmados"
    if ratio >= 0.5:
        return 1, "parte dos dados decisivos confirmada"
    return 0, "dados decisivos ainda não confirmados"


def _label(si_state, indigenous_immediate, proximity_points, score, coverage):
    if si_state == "incompativel_com_requisito_explicito":
        return "compatibilidade_desfavoravel"
    if coverage < 0.4 or si_state in ("nao_extraido", "nao_informado"):
        return "exige_confirmacao" if coverage >= 0.2 else "sem_dados_suficientes"
    if si_state in SI_CONFIRMED and indigenous_immediate == 0:
        return "sem_vagas_indigenas"
    if si_state in SI_CONFIRMED and (indigenous_immediate or 0) >= 1:
        if proximity_points is not None and proximity_points <= 1:
            return "oportunidade_importante_distante"
        return "boa_aderencia"
    if si_state == "ambiguo" or indigenous_immediate is None:
        return "exige_confirmacao"
    return "sem_dados_suficientes"


def score_contest(*, indigenous_immediate, indigenous_reserve, si_compatibility,
                  distance_km=None, practical_distance_km=300, exam_uf=None,
                  interest_states=None, evidence_confidence=None,
                  confirmed_fields=0, total_decisive=0) -> dict:
    """Pontua um concurso de forma explicável.

    Devolve ``score``, ``possible`` (máximo atingível com os dados disponíveis),
    ``coverage``, ``label``, ``explain`` e a lista ``factors`` (cada um com valor, pontos,
    peso, contribuição e motivo). Determinístico para os mesmos dados.
    """
    factors = []

    def add(key, result):
        points, reason = result
        factors.append({"key": key, "points": points, "max": WEIGHTS[key],
                        "weight": WEIGHTS[key], "reason": reason,
                        "known": points is not None})

    add("vagas_indigenas_imediatas", _vagas_indigenas_imediatas(indigenous_immediate))
    add("vagas_indigenas_reserva", _vagas_indigenas_reserva(indigenous_reserve))
    add("compatibilidade_si", _compatibilidade(si_compatibility))
    add("proximidade_prova", _proximidade(distance_km, practical_distance_km, exam_uf, interest_states))
    add("confianca_evidencia", _confianca_evidencia(evidence_confidence))
    add("confirmacao_dados", _confirmacao(confirmed_fields, total_decisive))

    score = sum(f["points"] for f in factors if f["known"])
    possible = sum(f["max"] for f in factors if f["known"])
    coverage = round(possible / TOTAL_MAX, 3) if TOTAL_MAX else 0.0

    proximity_points = next(f["points"] for f in factors if f["key"] == "proximidade_prova")
    exceptional = (si_compatibility == "aceito_expressamente"
                   and indigenous_immediate is not None
                   and indigenous_immediate >= _EXCEPTIONAL_MIN_INDIGENOUS)
    floor_applied = False
    if exceptional and score < EXCEPTIONAL_FLOOR:
        score = EXCEPTIONAL_FLOOR
        floor_applied = True
    possible = max(possible, score)  # o piso nunca faz score > possible

    label = _label(si_compatibility, indigenous_immediate, proximity_points, score, coverage)
    explain = "; ".join(f["reason"] for f in factors if f["known"]) or "sem dados decisivos"
    return {"version": RANKING_VERSION, "score": score, "possible": possible,
            "max_score": TOTAL_MAX, "coverage": coverage, "label": label,
            "label_text": LABELS[label], "exceptional": exceptional,
            "floor_applied": floor_applied, "factors": factors, "explain": explain}
