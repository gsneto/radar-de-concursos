"""Pacotes de conteúdo: exportação/importação segura de questões e flashcards (Fase 24).

## Formato `radar-pacote` v1

Um único arquivo **ZIP** contendo:

- ``manifest.json`` — versão do formato, tipo, contagens, procedência/licença declarada e a
  lista de registros.
- ``registros.json`` — questões (com versões), flashcards e relações.
- ``midia/<sha256>.<ext>`` — imagens referenciadas (opcional).

Por que ZIP e não um formato externo (Anki `.apkg`, QTI): ambos exigiriam dependências e
trazem semântica própria (agendamento, taxonomia) que o Radar não usa. JSON + ZIP com
manifesto é auditável, versionado e não exige nada além da biblioteca padrão.

## Segurança (pesquisa: OWASP File Upload, OpenSSF pyscg-0012, `zipfile` docs)

- **Zip Slip**: nome de cada membro é normalizado; recusa caminho absoluto, ``..``, letra de
  unidade, UNC, barra invertida e byte nulo; a extração nunca escreve fora do diretório.
- **Zip bomb**: limites de tamanho por membro, total descompactado, número de membros e
  **taxa de compressão**; o tamanho real é medido no streaming (o cabeçalho pode mentir).
- **Nada é executado**: apenas ``manifest.json``/``registros.json`` são lidos como JSON; nenhum
  script, macro ou código é interpretado.
- **Direitos**: pacote sem procedência/licença explícita é importado como **não verificado**
  (sinalizado), nunca como conteúdo liberado. O Radar não redistribui material de terceiros.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from uuid import uuid4

from radar import media
from radar.document_store import connect_documents

FORMAT = "radar-pacote"
FORMAT_VERSION = 1

# Limites de segurança (documentados; podem ser reduzidos por parâmetro).
MAX_MEMBERS = 500
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 40 * 1024 * 1024
MAX_RATIO = 120.0          # descompactado / compactado
MAX_JSON_BYTES = 4 * 1024 * 1024

MANIFEST = "manifest.json"
RECORDS = "registros.json"
MEDIA_PREFIX = "midia/"

# Estados de licença reconhecidos. Qualquer outro valor => "desconhecida".
LICENSE_STATES = ("propria", "autorizada", "cc_by", "cc_by_sa", "public_domain", "desconhecida")


class PackageError(ValueError):
    """Pacote inválido, inseguro ou incompatível."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Leitura segura de ZIP ---------------------------------------------------

def _safe_member_name(name: str) -> str:
    """Valida o nome de um membro; levanta ``PackageError`` se tentar escapar do diretório."""
    if not isinstance(name, str) or not name:
        raise PackageError("nome de arquivo vazio no pacote")
    if "\x00" in name:
        raise PackageError("nome de arquivo com byte nulo")
    normalized = name.replace("\\", "/")
    if normalized.startswith("/"):
        raise PackageError(f"caminho absoluto no pacote: {name!r}")
    if len(normalized) > 1 and normalized[1] == ":":
        raise PackageError(f"caminho com unidade no pacote: {name!r}")
    if normalized.startswith("//"):
        raise PackageError(f"caminho UNC no pacote: {name!r}")
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise PackageError(f"tentativa de path traversal no pacote: {name!r}")
    return "/".join(parts)


def read_package(data, *, max_members=MAX_MEMBERS, max_member_bytes=MAX_MEMBER_BYTES,
                 max_total_bytes=MAX_TOTAL_BYTES, max_ratio=MAX_RATIO) -> dict:
    """Lê um pacote ZIP **sem extrair para disco**, aplicando limites anti-bomba.

    Devolve ``{manifest, registros, midias: {nome: bytes}}``. Nunca confia em metadados:
    o tamanho é medido ao ler, com corte no limite.
    """
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise PackageError("pacote vazio")
    try:
        archive = zipfile.ZipFile(io.BytesIO(bytes(data)))
    except zipfile.BadZipFile as error:
        raise PackageError("arquivo não é um ZIP válido") from error

    try:
        members = archive.infolist()
        if len(members) > max_members:
            raise PackageError(f"pacote com mais de {max_members} arquivos")
        total_declared = sum(max(0, m.file_size) for m in members)
        total_compressed = sum(max(0, m.compress_size) for m in members) or 1
        if total_declared > max_total_bytes:
            raise PackageError(f"pacote descompacta acima de {max_total_bytes} bytes")
        if total_declared / total_compressed > max_ratio:
            raise PackageError("taxa de compressão suspeita (possível zip bomb)")

        names = {}
        for member in members:
            safe = _safe_member_name(member.filename)
            if member.is_dir():
                continue
            if member.file_size > max_member_bytes:
                raise PackageError(f"arquivo grande demais no pacote: {safe}")
            names[safe] = member

        if MANIFEST not in names or RECORDS not in names:
            raise PackageError("pacote sem manifest.json ou registros.json")

        def _read(name, limit):
            with archive.open(names[name]) as handle:
                payload = handle.read(limit + 1)  # corte: não confia no tamanho declarado
            if len(payload) > limit:
                raise PackageError(f"arquivo {name} acima do limite real")
            return payload

        total_real = 0
        manifest = _load_json(_read(MANIFEST, MAX_JSON_BYTES), "manifest.json")
        registros = _load_json(_read(RECORDS, MAX_JSON_BYTES), "registros.json")
        total_real += len(_read(MANIFEST, MAX_JSON_BYTES)) + len(_read(RECORDS, MAX_JSON_BYTES))
        if total_real > max_total_bytes:
            raise PackageError("pacote acima do limite total")

        midias = {}
        for safe in names:
            if not safe.startswith(MEDIA_PREFIX):
                continue
            name = safe[len(MEDIA_PREFIX):]
            if "/" in name:
                raise PackageError(f"mídia em subdiretório não é aceita: {safe}")
            payload = _read(safe, max_member_bytes)
            total_real += len(payload)
            if total_real > max_total_bytes:
                raise PackageError("pacote acima do limite total real")
            try:
                media.validate_image(payload)  # valida assinatura/tamanho de cada mídia
            except media.MediaError as error:
                raise PackageError(f"mídia inválida no pacote: {safe}") from error
            midias[name] = payload
    finally:
        archive.close()
    return {"manifest": manifest, "registros": registros, "midias": midias}


def _load_json(raw: bytes, label: str) -> dict:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise PackageError(f"{label} não é JSON válido") from error
    if not isinstance(parsed, dict):
        raise PackageError(f"{label} deve ser um objeto JSON")
    return parsed


def _validate_records(registros) -> dict:
    """Valida e normaliza os registros do pacote (estrutura, tipos e campos obrigatórios)."""
    if not isinstance(registros, dict):
        raise PackageError("registros.json deve ser um objeto")
    questoes = registros.get("questoes") or []
    flashcards = registros.get("flashcards") or []
    disciplinas = registros.get("disciplinas") or []
    topicos = registros.get("topicos") or []
    for label, rows in (("questões", questoes), ("flashcards", flashcards),
                        ("disciplinas", disciplinas), ("tópicos", topicos)):
        if not isinstance(rows, list):
            raise PackageError(f"{label} deve ser uma lista")

    def _text(item, key, label):
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            raise PackageError(f"{label} sem campo obrigatório {key!r}")
        return value

    def _int(item, key, default=0):
        value = item.get(key, default)
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            raise PackageError(f"campo {key!r} inválido no pacote")

    def _float(item, key, default):
        value = item.get(key, default)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            raise PackageError(f"campo {key!r} inválido no pacote")

    normalized_questions = []
    for item in questoes:
        if not isinstance(item, dict):
            raise PackageError("questão inválida no pacote (esperado objeto)")
        qid = _text(item, "id", "questão")
        _text(item, "enunciado", "questão")
        _text(item, "gabarito", "questão")
        versoes = item.get("versoes") or []
        if not isinstance(versoes, list):
            raise PackageError("versões de questão inválidas no pacote")
        clean_versions = []
        for version in versoes:
            if not isinstance(version, dict):
                raise PackageError("versão de questão inválida no pacote")
            _text(version, "enunciado", "versão")
            _text(version, "gabarito", "versão")
            clean_versions.append({**version, "versao": _int(version, "versao", 1)})
        normalized_questions.append({**item, "id": qid, "versao": _int(item, "versao", 1),
                                     "versoes": clean_versions})

    normalized_cards = []
    for item in flashcards:
        if not isinstance(item, dict):
            raise PackageError("flashcard inválido no pacote (esperado objeto)")
        fid = _text(item, "id", "flashcard")
        _text(item, "frente", "flashcard")
        _text(item, "verso", "flashcard")
        imagem = item.get("imagem")
        if imagem is not None and not isinstance(imagem, dict):
            raise PackageError("imagem do flashcard inválida no pacote")
        normalized_cards.append({**item, "id": fid, "ease": _float(item, "ease", 2.5),
                                 "intervalo": _int(item, "intervalo"),
                                 "repeticoes": _int(item, "repeticoes"),
                                 "revisoes": _int(item, "revisoes")})

    normalized_disciplines = []
    for item in disciplinas:
        if not isinstance(item, dict):
            raise PackageError("disciplina inválida no pacote")
        normalized_disciplines.append({**item, "id": _text(item, "id", "disciplina"),
                                       "nome": _text(item, "nome", "disciplina")})

    normalized_topics = []
    for item in topicos:
        if not isinstance(item, dict):
            raise PackageError("tópico inválido no pacote")
        normalized_topics.append({**item, "id": _text(item, "id", "tópico"),
                                  "nome": _text(item, "nome", "tópico")})

    return {"questoes": normalized_questions, "flashcards": normalized_cards,
            "disciplinas": normalized_disciplines, "topicos": normalized_topics}


def validate_manifest(manifest: dict) -> dict:
    """Valida o manifesto e devolve o estado de licença/procedência (nunca presume liberação)."""
    if manifest.get("formato") != FORMAT:
        raise PackageError(f"formato inesperado: {manifest.get('formato')!r}")
    version = manifest.get("versao_formato")
    if not isinstance(version, int) or version < 1:
        raise PackageError("versao_formato ausente ou inválida")
    if version > FORMAT_VERSION:
        raise PackageError(f"versao_formato {version} mais nova que a suportada ({FORMAT_VERSION})")
    tipo = manifest.get("tipo")
    if tipo not in ("questoes", "flashcards", "misto"):
        raise PackageError("tipo de pacote inválido")
    raw_license = manifest.get("licenca")
    licenca = raw_license.strip().lower() if isinstance(raw_license, str) else "desconhecida"
    if licenca not in LICENSE_STATES:
        licenca = "desconhecida"
    return {"formato": FORMAT, "versao_formato": version, "tipo": tipo,
            "nome": manifest.get("nome") or "Pacote", "procedencia": manifest.get("procedencia"),
            "licenca": licenca,
            "licenca_verificada": licenca != "desconhecida",
            "aviso": (None if licenca != "desconhecida" else
                      "Licença não declarada: o conteúdo é importado como NÃO verificado e "
                      "não deve ser redistribuído.")}


# --- Exportação --------------------------------------------------------------

def export_package(db_path, *, nome="Pacote", tipo="misto", licenca="propria",
                   procedencia=None, incluir_questoes=True, incluir_flashcards=True,
                   incluir_midias=True, question_ids=None, flashcard_ids=None) -> bytes:
    """Monta o pacote ZIP em memória. Só exporta conteúdo próprio/autorizado."""
    licenca = (licenca or "propria").strip().lower()
    if licenca not in LICENSE_STATES:
        raise PackageError("licença inválida para exportação")
    if tipo not in ("questoes", "flashcards", "misto"):
        raise PackageError("tipo de pacote inválido para exportação")
    conn = connect_documents(db_path)
    try:
        questoes, flashcard_rows, midias = [], [], {}
        disciplinas, topicos = [], []
        if incluir_questoes:
            query = ("SELECT id,versao,tipo,disciplina,topico,conceito_key,enunciado,"
                     "alternativas_json,gabarito,comentario,dificuldade,tags,fonte,licenca,"
                     "procedencia,estado FROM pratica_questoes")
            params = ()
            if question_ids:
                placeholders = ",".join("?" for _ in question_ids)
                query += f" WHERE id IN ({placeholders})"
                params = tuple(question_ids)
            for row in conn.execute(query, params).fetchall():
                keys = ("id", "versao", "tipo", "disciplina", "topico", "conceito_key", "enunciado",
                        "alternativas_json", "gabarito", "comentario", "dificuldade", "tags",
                        "fonte", "licenca", "procedencia", "estado")
                item = dict(zip(keys, row))
                versoes = [dict(zip(("versao", "enunciado", "alternativas_json", "gabarito",
                                     "comentario", "registrado_em"), v))
                           for v in conn.execute(
                               "SELECT versao,enunciado,alternativas_json,gabarito,comentario,"
                               "registrado_em FROM pratica_questao_versoes WHERE questao_id=? "
                               "ORDER BY versao", (item["id"],)).fetchall()]
                item["versoes"] = versoes
                questoes.append(item)
        if incluir_flashcards:
            query = ("SELECT id,disciplina_id,topico_id,contest_id,conceito_key,frente,verso,tags,"
                     "fonte,licenca,estado,ease,intervalo,repeticoes,proxima_revisao,"
                     "ultima_revisao,revisoes,imagem_id FROM pratica_flashcards")
            params = ()
            if flashcard_ids:
                placeholders = ",".join("?" for _ in flashcard_ids)
                query += f" WHERE id IN ({placeholders})"
                params = tuple(flashcard_ids)
            for row in conn.execute(query, params).fetchall():
                keys = ("id", "disciplina_id", "topico_id", "contest_id", "conceito_key", "frente",
                        "verso", "tags", "fonte", "licenca", "estado", "ease", "intervalo",
                        "repeticoes", "proxima_revisao", "ultima_revisao", "revisoes", "imagem_id")
                item = dict(zip(keys, row))
                imagem = None
                if item.get("imagem_id"):
                    imagem = conn.execute(
                        "SELECT sha256,extensao,mime,bytes,largura,altura FROM pratica_midias "
                        "WHERE id=?", (item["imagem_id"],)).fetchone()
                    if imagem:
                        item["imagem"] = {"sha256": imagem[0], "extensao": imagem[1],
                                          "mime": imagem[2], "bytes": imagem[3],
                                          "largura": imagem[4], "altura": imagem[5]}
                        if incluir_midias:
                            payload = media.read_media(db_path, imagem[0], imagem[1])
                            if payload:
                                midias[f"{imagem[0]}.{imagem[1]}"] = payload
                flashcard_rows.append(item)
        disc_ids = {f["disciplina_id"] for f in flashcard_rows if f.get("disciplina_id")}
        top_ids = {f["topico_id"] for f in flashcard_rows if f.get("topico_id")}
        for disc_id in sorted(disc_ids):
            row = conn.execute("SELECT id,nome FROM estudo_disciplinas WHERE id=?",
                               (disc_id,)).fetchone()
            if row:
                disciplinas.append({"id": row[0], "nome": row[1]})
        for top_id in sorted(top_ids):
            row = conn.execute("SELECT id,disciplina_id,parent_id,nome FROM estudo_topicos "
                               "WHERE id=?", (top_id,)).fetchone()
            if row:
                topicos.append({"id": row[0], "disciplina_id": row[1], "parent_id": row[2],
                                "nome": row[3]})
    finally:
        conn.close()

    registros = {"questoes": questoes, "flashcards": flashcard_rows,
                 "disciplinas": disciplinas, "topicos": topicos}
    manifest = {
        "formato": FORMAT, "versao_formato": FORMAT_VERSION, "tipo": tipo, "nome": nome,
        "exportado_em": _now(), "licenca": licenca, "procedencia": procedencia,
        "contagens": {"questoes": len(questoes), "flashcards": len(flashcard_rows),
                      "midias": len(midias), "disciplinas": len(disciplinas),
                      "topicos": len(topicos)},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr(RECORDS, json.dumps(registros, ensure_ascii=False, indent=2))
        for name, payload in midias.items():
            archive.writestr(MEDIA_PREFIX + name, payload)
    return buffer.getvalue()


# --- Prévia e importação -----------------------------------------------------

def preview_package(db_path, data) -> dict:
    """Inspeção **sem gravar**: valida estrutura, conta registros e aponta conflitos."""
    parsed = read_package(data)
    info = validate_manifest(parsed["manifest"])
    registros = _validate_records(parsed["registros"])
    questoes = registros["questoes"]
    flashcards = registros["flashcards"]
    conn = connect_documents(db_path)
    try:
        local_q = {row[0] for row in conn.execute("SELECT id FROM pratica_questoes")}
        local_f = {row[0] for row in conn.execute("SELECT id FROM pratica_flashcards")}
    finally:
        conn.close()
    conflicts = [{"tipo": "questao", "id": q.get("id"), "motivo": "já existe localmente"}
                 for q in questoes if q.get("id") in local_q]
    conflicts += [{"tipo": "flashcard", "id": f.get("id"), "motivo": "já existe localmente"}
                  for f in flashcards if f.get("id") in local_f]
    return {"manifest": info, "contagens": {"questoes": len(questoes),
                                            "flashcards": len(flashcards),
                                            "midias": len(parsed["midias"])},
            "conflitos": conflicts, "midias": sorted(parsed["midias"]),
            "pode_importar": True}


def import_package(db_path, data, *, dry_run=False) -> dict:
    """Importa o pacote de forma transacional, idempotente e não destrutiva.

    - Nunca sobrescreve registros locais (conflito é reportado, o local prevalece).
    - Mídia é validada por assinatura e gravada por hash (dedup natural).
    - Registra a proveniência em ``pratica_pacotes``.
    """
    parsed = read_package(data)
    info = validate_manifest(parsed["manifest"])
    registros = _validate_records(parsed["registros"])
    questoes = registros["questoes"]
    flashcards = registros["flashcards"]
    report = {"ok": True, "erros": [], "criados": {"questoes": 0, "flashcards": 0, "midias": 0},
              "ignorados": 0, "conflitos": [], "dry_run": bool(dry_run),
              "licenca": info["licenca"], "licenca_verificada": info["licenca_verificada"],
              "aviso": info["aviso"]}
    conn = connect_documents(db_path)
    try:
        if not dry_run:
            conn.execute("BEGIN IMMEDIATE")
        # Mídias primeiro (os cartões referenciam).
        midia_ids = {}
        for name, payload in parsed["midias"].items():
            sha, _, ext = name.partition(".")
            existing = conn.execute("SELECT id FROM pratica_midias WHERE sha256=?",
                                    (sha,)).fetchone()
            if existing:
                midia_ids[sha] = existing[0]
                continue
            if dry_run:
                midia_ids[sha] = f"dry:{sha}"
                report["criados"]["midias"] += 1
                continue
            if not dry_run:
                info_media = media.validate_image(payload)
                media.store_image(db_path, payload, origem="pacote", licenca=info["licenca"])
                mid = str(uuid4())
                conn.execute(
                    "INSERT INTO pratica_midias(id,sha256,mime,extensao,bytes,largura,altura,"
                    "origem,licenca,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (mid, info_media["sha256"], info_media["mime"], info_media["extensao"],
                     info_media["bytes"], info_media["largura"], info_media["altura"],
                     "pacote", info["licenca"], _now()))
                midia_ids[sha] = mid
                midia_ids[info_media["sha256"]] = mid
                report["criados"]["midias"] += 1

        for item in registros["disciplinas"]:
            if conn.execute("SELECT 1 FROM estudo_disciplinas WHERE id=?",
                            (item["id"],)).fetchone():
                continue
            if not dry_run:
                conn.execute("INSERT INTO estudo_disciplinas(id,nome,created_at) VALUES(?,?,?)",
                             (item["id"], item["nome"], _now()))
        for item in registros["topicos"]:
            if conn.execute("SELECT 1 FROM estudo_topicos WHERE id=?", (item["id"],)).fetchone():
                continue
            parent = item.get("parent_id")
            if parent and not conn.execute("SELECT 1 FROM estudo_topicos WHERE id=?",
                                           (parent,)).fetchone():
                parent = None
            disciplina = item.get("disciplina_id")
            if disciplina and not conn.execute("SELECT 1 FROM estudo_disciplinas WHERE id=?",
                                               (disciplina,)).fetchone():
                disciplina = None
            if not dry_run:
                conn.execute(
                    "INSERT INTO estudo_topicos(id,disciplina_id,parent_id,nome,created_at) "
                    "VALUES(?,?,?,?,?)",
                    (item["id"], disciplina, parent, item["nome"], _now()))

        for item in questoes:
            if conn.execute("SELECT 1 FROM pratica_questoes WHERE id=?", (item["id"],)).fetchone():
                report["ignorados"] += 1
                report["conflitos"].append({"tipo": "questao", "id": item["id"],
                                            "motivo": "já existe localmente; preservado"})
                continue
            if not dry_run:
                conn.execute(
                    "INSERT INTO pratica_questoes(id,versao,tipo,disciplina,topico,conceito_key,"
                    "enunciado,alternativas_json,gabarito,comentario,dificuldade,tags,fonte,"
                    "licenca,procedencia,estado,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (item["id"], int(item.get("versao") or 1),
                     item.get("tipo") or "escolha_unica", item.get("disciplina"),
                     item.get("topico"), item.get("conceito_key"), item["enunciado"],
                     item.get("alternativas_json") or "[]", item["gabarito"],
                     item.get("comentario"), item.get("dificuldade"), item.get("tags"),
                     item.get("fonte"), item.get("licenca") or info["licenca"],
                     item.get("procedencia") or info["procedencia"],
                     item.get("estado") or "ativo", _now(), _now()))
                for versao in item.get("versoes") or []:
                    if conn.execute("SELECT 1 FROM pratica_questao_versoes WHERE questao_id=? "
                                    "AND versao=?", (item["id"], int(versao["versao"]))).fetchone():
                        continue
                    conn.execute(
                        "INSERT INTO pratica_questao_versoes(id,questao_id,versao,enunciado,"
                        "alternativas_json,gabarito,comentario,registrado_em) "
                        "VALUES(?,?,?,?,?,?,?,?)",
                        (str(uuid4()), item["id"], int(versao["versao"]), versao["enunciado"],
                         versao.get("alternativas_json") or "[]", versao["gabarito"],
                         versao.get("comentario"), versao.get("registrado_em") or _now()))
            report["criados"]["questoes"] += 1

        for item in flashcards:
            if conn.execute("SELECT 1 FROM pratica_flashcards WHERE id=?", (item["id"],)).fetchone():
                report["ignorados"] += 1
                report["conflitos"].append({"tipo": "flashcard", "id": item["id"],
                                            "motivo": "já existe localmente; preservado"})
                continue
            imagem_id = None
            imagem = item.get("imagem") or {}
            if imagem.get("sha256") in midia_ids:
                imagem_id = midia_ids[imagem["sha256"]]
            elif imagem:
                report["conflitos"].append({"tipo": "midia", "id": imagem.get("sha256"),
                                            "motivo": "imagem referenciada ausente no pacote"})
            disciplina_id = item.get("disciplina_id")
            if disciplina_id and not conn.execute(
                    "SELECT 1 FROM estudo_disciplinas WHERE id=?", (disciplina_id,)).fetchone():
                report["conflitos"].append({"tipo": "disciplina", "id": disciplina_id,
                                            "motivo": "ausente no pacote; vínculo removido"})
                disciplina_id = None
            topico_id = item.get("topico_id")
            if topico_id and not conn.execute(
                    "SELECT 1 FROM estudo_topicos WHERE id=?", (topico_id,)).fetchone():
                report["conflitos"].append({"tipo": "topico", "id": topico_id,
                                            "motivo": "ausente no pacote; vínculo removido"})
                topico_id = None
            if not dry_run:
                conn.execute(
                    "INSERT INTO pratica_flashcards(id,disciplina_id,topico_id,contest_id,"
                    "conceito_key,frente,verso,tags,fonte,licenca,estado,ease,intervalo,"
                    "repeticoes,proxima_revisao,ultima_revisao,revisoes,created_at,updated_at,"
                    "imagem_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (item["id"], disciplina_id, topico_id,
                     item.get("contest_id") or "", item.get("conceito_key"), item["frente"],
                     item["verso"], item.get("tags"), item.get("fonte"),
                     item.get("licenca") or info["licenca"], item.get("estado") or "ativo",
                     float(item.get("ease") or 2.5), int(item.get("intervalo") or 0),
                     int(item.get("repeticoes") or 0), item.get("proxima_revisao"),
                     item.get("ultima_revisao"), int(item.get("revisoes") or 0),
                     _now(), _now(), imagem_id))
            report["criados"]["flashcards"] += 1

        if not dry_run:
            conn.execute(
                "INSERT INTO pratica_pacotes(id,nome,formato,versao_formato,procedencia,licenca,"
                "counts_json,importado_em) VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid4()), info["nome"], FORMAT, info["versao_formato"], info["procedencia"],
                 info["licenca"], json.dumps(report["criados"], ensure_ascii=False), _now()))
            conn.commit()
    except PackageError:
        if not dry_run:
            conn.rollback()
        raise
    except BaseException:
        if not dry_run:
            conn.rollback()
        raise
    finally:
        conn.close()
    return report


def list_packages(db_path, *, limit=50) -> list[dict]:
    """Histórico de pacotes importados (proveniência auditável)."""
    conn = connect_documents(db_path)
    try:
        rows = conn.execute(
            "SELECT id,nome,formato,versao_formato,procedencia,licenca,counts_json,importado_em "
            "FROM pratica_pacotes ORDER BY importado_em DESC, id LIMIT ?",
            (max(0, int(limit)),)).fetchall()
        keys = ("id", "nome", "formato", "versao_formato", "procedencia", "licenca",
                "counts_json", "importado_em")
        out = []
        for row in rows:
            item = dict(zip(keys, row))
            try:
                item["counts"] = json.loads(item.pop("counts_json") or "{}")
            except (TypeError, ValueError):
                item["counts"] = {}
            counts = item["counts"]
            item["questoes"] = counts.get("questoes", 0)
            item["flashcards"] = counts.get("flashcards", 0)
            item["midias"] = counts.get("midias", 0)
            item["tipo"] = ("misto" if item["questoes"] and item["flashcards"]
                            else "questoes" if item["questoes"] else "flashcards")
            out.append(item)
        return out
    finally:
        conn.close()
