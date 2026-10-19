"""Sugestões de identidade canônica para linhas de quadro (Fase 43).

O quadro da SEDUC-PA publica **381 linhas**, mas apenas **7 cargos** e **27 combinações de
cargo + formação**, distribuídas em **24 regionais**. Tratar cada linha como um cargo
canônico distinto inventa 381 identidades; tratar todas as linhas do mesmo cargo como uma
oportunidade só apaga região e requisito.

Este módulo propõe a granularidade correta, com evidência:

- **cargo** + **formação/especialidade** = identidade candidata;
- **regional (DRE)** = dimensão da oportunidade, nunca parte da identidade;
- **linha documental** = oportunidade individual (381).

Nada é gravado. A sugestão é exibida com o trecho literal, o cabeçalho e os avisos; a
reconciliação da base real continua exigindo a decisão humana de `role_identity`.
"""

from __future__ import annotations

import re
from contextlib import closing

from radar.document_store import connect_documents, is_readable_schema

VERSION = "identity_suggestions_v1"

# Vocabulário do edital por (banco, concurso): os blocos são imutáveis por versão.
_VOCABULARY_CACHE: dict = {}
_VOCABULARY_LOCK = __import__("threading").Lock()

# Palavras que, sozinhas no fim, indicam célula cortada pela coluna ("Administraçã" + "o").
_CUT_TAIL = re.compile(r"^(?:[a-zà-ÿ]{1,3}|[A-ZÀ-Þ][a-zà-ÿ]{0,2})$")


def _tokens(text: str) -> list[str]:
    return [token for token in " ".join((text or "").split()).split(" ") if token]


def _vocabulary(conn, contest_id: str) -> dict[str, int]:
    """Contagem das palavras publicadas no edital (todas as versões do concurso).

    Serve de prova para recompor uma palavra partida: a forma reconstruída precisa
    existir **e** ser mais frequente que o fragmento. Sem essa prova, o texto fica como
    está.
    """
    cache_key = (str(conn.execute("PRAGMA database_list").fetchone()[2]), contest_id)
    with _VOCABULARY_LOCK:
        if cache_key in _VOCABULARY_CACHE:
            return _VOCABULARY_CACHE[cache_key]
    words: dict[str, int] = {}
    for (text,) in conn.execute(
            "SELECT b.text FROM blocos_documento b "
            "JOIN versoes_documento v ON v.id=b.version_id "
            "JOIN documentos d ON d.id=v.document_id WHERE d.contest_id=?", (contest_id,)):
        for token in (text or "").split():
            clean = token.strip(".,;:()[]\"'").casefold()
            if clean:
                words[clean] = words.get(clean, 0) + 1
    with _VOCABULARY_LOCK:
        _VOCABULARY_CACHE[cache_key] = words
        if len(_VOCABULARY_CACHE) > 4:
            _VOCABULARY_CACHE.pop(next(iter(_VOCABULARY_CACHE)), None)
    return words


def join_cut_words(text: str, vocabulary=None) -> tuple[str, bool]:
    """Recompõe palavras partidas pela coluna **quando o documento publica a forma**.

    "Administraçã" + "o" só vira "Administração" se "administração" aparecer no edital;
    "Governament" + "al" só vira "Governamental" se a forma existir e for mais frequente
    que o fragmento. "Especialista" + "em" nunca é juntado (a forma não existe), e
    "Professor" + "a" não vira "Professora" porque "professor" é mais frequente.
    """
    tokens = _tokens(text)
    if len(tokens) < 2 or not vocabulary:
        return " ".join(tokens), False
    def count(word):
        if isinstance(vocabulary, dict):
            return vocabulary.get(word, 0)
        return 1 if word in vocabulary else 0

    out = [tokens[0]]
    joined = False
    for token in tokens[1:]:
        previous = out[-1]
        candidate = (previous + token).casefold()
        if (len(token) <= 3 and token.isalpha() and previous[-1:].isalpha()
                and not previous.endswith(("-", "–", "/", ","))
                and count(candidate) > count(previous.casefold())):
            out[-1] = previous + token
            joined = True
        else:
            out.append(token)
    return " ".join(out), joined


_CONNECTORS = {"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o"}


def normalize_identity(cargo: str, formacao: str, vocabulary=None) -> dict:
    """Identidade candidata a partir do conteúdo publicado, com avisos explícitos.

    Três leituras estruturais, todas visíveis:

    - palavra partida pela coluna ("Administraçã o") só é recomposta se o documento
      publicar a forma;
    - cargo terminando em conectivo ("… Governamental e") recebe a formação como
      **continuação do próprio cargo**, não como especialidade;
    - formação igual, prefixo ou sufixo do cargo é repetição (não há especialidade).
    """
    cargo_text, cargo_joined = join_cut_words(cargo, vocabulary)
    form_text, form_joined = join_cut_words(formacao, vocabulary)
    warnings = []
    if cargo_joined:
        warnings.append({"codigo": "cargo_recomposto",
                         "texto": "palavra do cargo estava partida pela coluna"})
    if form_joined:
        warnings.append({"codigo": "formacao_recomposta",
                         "texto": "palavra da formação estava partida pela coluna"})

    words = cargo_text.split()
    if words and words[-1].lower().strip(",;") in _CONNECTORS and form_text:
        cargo_text = f"{cargo_text} {form_text}".strip()
        warnings.append({"codigo": "cargo_continuado_na_formacao",
                         "texto": ("o cargo termina em conectivo e a formação continua o "
                                   "nome do cargo; não há especialidade distinta")})
        form_text = ""

    specialty = None
    if form_text and form_text.casefold() != cargo_text.casefold():
        cargo_norm = cargo_text.casefold()
        form_norm = form_text.casefold()
        if cargo_norm.endswith(form_norm) or form_norm.endswith(cargo_norm):
            warnings.append({"codigo": "especialidade_repetida",
                             "texto": ("a coluna de formação repete parte do nome do "
                                       "cargo: não há especialidade distinta")})
        else:
            specialty = form_text
    elif form_text:
        warnings.append({"codigo": "especialidade_repetida",
                         "texto": ("a coluna de formação repete o nome do cargo: não há "
                                   "especialidade distinta")})
    if not form_text and not specialty and not any(
            item["codigo"] in ("cargo_continuado_na_formacao", "especialidade_repetida")
            for item in warnings):
        warnings.append({"codigo": "sem_formacao",
                         "texto": "a linha não publica formação/especialidade"})
    return {"cargo": cargo_text, "especialidade": specialty,
            "chave": (cargo_text, specialty), "avisos": warnings}


def _identity_key(cargo: str, formacao: str, vocabulary=None) -> tuple:
    return normalize_identity(cargo, formacao, vocabulary)["chave"]


def _existing_roles(conn, contest_id: str) -> list[dict]:
    return [{"role_id": row[0], "name": row[1], "specialty": row[2], "code": row[3]}
            for row in conn.execute(
                "SELECT id,name,specialty,code FROM cargos_identidade WHERE contest_id=?",
                (contest_id,))]


def _match_existing(candidate, roles):
    """Identidade existente compatível **exatamente** (nome e especialidade normalizados).

    Não usa similaridade: uma identidade só é sugerida quando o nome normalizado e a
    especialidade coincidem. Caso contrário, a sugestão é criar identidade nova.
    """
    def norm(text):
        return " ".join((text or "").casefold().split())

    for role in roles:
        if norm(role["name"]) != norm(candidate["cargo"]):
            continue
        if norm(role["specialty"]) != norm(candidate["especialidade"]):
            continue
        return role
    return None


def report(db_path, *, contest_id=None, items=None) -> dict:
    """Sugestões de identidade por cargo+formação, com linhas e regionais.

    Somente leitura: não cria identidade, não reconcilia, não altera propostas.
    """
    from radar import review_groups

    if contest_id is None:
        raise ValueError("contest_id obrigatório")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        roles = _existing_roles(conn, contest_id)
        vocabulary = _vocabulary(conn, contest_id)
        reconciled = {row[0] for row in conn.execute(
            "SELECT DISTINCT label FROM reconciliacoes_cargo WHERE contest_id=? "
            "AND state='confirmada'", (contest_id,))}

    if items is None:
        items, offset = [], 0
        while True:
            page = review_groups.groups(db_path, contest_id=contest_id, contexto=True,
                                        state="todos", limit=100, offset=offset)
            items.extend(page["itens"])
            offset += page["limit"]
            if not page["has_more"]:
                break

    grouped = {}
    for item in items:
        context = item["contexto"] or {}
        candidate = normalize_identity(context.get("cargo") or "",
                                       context.get("formacao") or "", vocabulary)
        entry = grouped.setdefault(candidate["chave"], {
            "cargo": candidate["cargo"], "especialidade": candidate["especialidade"],
            "avisos": list(candidate["avisos"]), "linhas": 0,
            "regionais": set(), "propostas": 0, "linhas_ids": [],
            "evidencia": [], "identidade_confirmada": 0,
        })
        entry["linhas"] += 1
        entry["propostas"] += len(item["propostas"])
        entry["regionais"].add(context.get("regional"))
        entry["linhas_ids"].append(item["linha_id"])
        if item["scope"] in reconciled or item["identidade"] == "reconciliado":
            entry["identidade_confirmada"] += 1
        if len(entry["evidencia"]) < 2:
            entry["evidencia"].append({
                "linha_id": item["linha_id"], "page": item["page_number"],
                "quote": context.get("trecho"),
                "regional": context.get("regional"),
                "document_id": item["document_id"],
                "version_id": item["version_id"], "sha256": item["sha256"]})

    suggestions = []
    for key, entry in grouped.items():
        match = _match_existing({"cargo": entry["cargo"],
                                 "especialidade": entry["especialidade"]}, roles)
        if match:
            action = "reconciliar_com_identidade_existente"
            role = {"role_id": match["role_id"], "name": match["name"],
                    "specialty": match["specialty"]}
        else:
            action = "criar_identidade"
            role = None
        suggestions.append({
            "chave": list(key),
            "cargo": entry["cargo"], "especialidade": entry["especialidade"],
            "linhas": entry["linhas"], "propostas": entry["propostas"],
            "regionais": sorted(name for name in entry["regionais"] if name),
            "linhas_confirmadas": entry["identidade_confirmada"],
            "acao_sugerida": action, "identidade_existente": role,
            "avisos": entry["avisos"], "evidencia": entry["evidencia"],
            "linhas_ids": entry["linhas_ids"],
        })
    suggestions.sort(key=lambda item: (-item["linhas"], item["cargo"],
                                       item["especialidade"] or ""))
    total_lines = sum(item["linhas"] for item in suggestions)
    return {
        "version": VERSION, "contest_id": contest_id,
        "linhas": total_lines, "identidades_candidatas": len(suggestions),
        "regionais": len({name for item in suggestions for name in item["regionais"]}),
        "por_acao": {
            "criar_identidade": sum(1 for item in suggestions
                                    if item["acao_sugerida"] == "criar_identidade"),
            "reconciliar_com_identidade_existente": sum(
                1 for item in suggestions
                if item["acao_sugerida"] == "reconciliar_com_identidade_existente"),
        },
        "itens": suggestions,
        "limitacao": ("Sugestão estrutural, não reconciliação. A regional é dimensão da "
                      "oportunidade, não parte da identidade; confirmar a identidade não "
                      "confirma vagas, requisitos nem reserva. Nada é gravado aqui."),
    }
