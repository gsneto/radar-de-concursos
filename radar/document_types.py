"""Classificação documental compartilhada pelas fontes oficiais.

O bucket de armazenamento (`kind`) permanece grosseiro — ``edital``/``retificacao``/
``outro`` — por compatibilidade. O **tipo fino** (`tipo_documental`) distingue edital de
abertura, edital retificado, retificação, anexo, cronograma, comunicado, resultado,
convocação, homologação, gabarito e prova. Nunca trata todo PDF como edital.
"""

from __future__ import annotations

import re

# Ordem importa: o primeiro marcador encontrado define o tipo fino.
_FINE_TYPES = (
    ("gabarito", ("gabarito",)),
    ("prova", ("provas aplicadas", "prova aplicada", "caderno de prova", "versão padrão")),
    ("homologacao", ("homologa",)),
    ("convocacao", ("convoca",)),
    ("resultado", ("resultado",)),
    ("cronograma", ("cronograma",)),
    ("anexo", ("anexo",)),
    ("comunicado", ("comunicado", "aviso", "informe", "nota de esclarecimento")),
)


def classify(title: str) -> str:
    """Tipo documental fino pelo título. Edital puro é ``edital_abertura``."""
    if not isinstance(title, str):
        return "outro"
    norm = " ".join(title.lower().split())
    if not norm:
        return "outro"
    if "errata" in norm:
        return "retificacao"
    # Retificação quando o título começa pelo marcador ("1ª Retificação", "Retificação do Edital").
    if re.match(r"^\s*\d*\s*[ªºo]?\s*retifica", norm):
        return "retificacao"
    is_edital = "edital" in norm
    if is_edital and any(marker in norm for marker in
                         ("atualizado", "consolidado", "alterado", "retificado")):
        return "edital_retificado"
    if is_edital and "retifica" in norm:
        return "retificacao"  # ex.: "Edital nº 6 (Retificação)" é a retificação
    # Tipos finos explícitos antes da heurística ampla de "retifica" (evita que um
    # "Cronograma ... conforme retificações" vire retificação).
    for fine, markers in _FINE_TYPES:
        if any(marker in norm for marker in markers):
            return fine
    if "retifica" in norm:
        return "retificacao"
    if is_edital:
        return "edital_abertura"
    return "outro"


def kind_for(document_type: str) -> str:
    """Bucket de armazenamento (`kind`) a partir do tipo fino."""
    if document_type in ("edital_abertura", "edital_retificado"):
        return "edital"
    if document_type == "retificacao":
        return "retificacao"
    return "outro"
