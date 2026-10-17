"""Esquema aditivo do histórico documental; nunca migra durante leitura v1."""

from __future__ import annotations

import sqlite3
import hashlib
import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from radar.document_fields import label_from_ambiguity


_DDL = (
    """CREATE TABLE concursos_identidade (
        id TEXT PRIMARY KEY, created_at TEXT NOT NULL)""",
    """CREATE TABLE observacoes_concurso (
        id TEXT PRIMARY KEY, contest_id TEXT NOT NULL REFERENCES concursos_identidade(id),
        source_url TEXT NOT NULL, competition_id TEXT NOT NULL, observed_at TEXT NOT NULL,
        UNIQUE(source_url, competition_id))""",
    """CREATE TABLE cargos_identidade (
        id TEXT PRIMARY KEY, contest_id TEXT NOT NULL REFERENCES concursos_identidade(id),
        name TEXT NOT NULL, specialty TEXT, created_at TEXT NOT NULL)""",
    """CREATE TABLE observacoes_cargo (
        id TEXT PRIMARY KEY, role_id TEXT NOT NULL REFERENCES cargos_identidade(id),
        observation_id TEXT NOT NULL REFERENCES observacoes_concurso(id),
        role TEXT NOT NULL, observed_at TEXT NOT NULL,
        UNIQUE(observation_id, role))""",
    """CREATE TABLE documentos (
        id TEXT PRIMARY KEY, contest_id TEXT NOT NULL REFERENCES concursos_identidade(id),
        observation_id TEXT NOT NULL REFERENCES observacoes_concurso(id),
        role_id TEXT REFERENCES cargos_identidade(id),
        kind TEXT NOT NULL CHECK(kind IN ('edital','retificacao','outro')),
        official_url TEXT NOT NULL, final_url TEXT, issuer TEXT, published_at TEXT,
        source_identifier TEXT, title TEXT NOT NULL, discovered_at TEXT NOT NULL,
        last_checked_at TEXT, discovery_url TEXT NOT NULL,
        discovery_method TEXT NOT NULL CHECK(discovery_method IN ('automatico','manual')),
        UNIQUE(observation_id, official_url))""",
    """CREATE TABLE documento_urls (
        document_id TEXT NOT NULL REFERENCES documentos(id), url TEXT NOT NULL,
        observed_at TEXT NOT NULL, is_primary INTEGER NOT NULL CHECK(is_primary IN (0,1)),
        PRIMARY KEY(document_id,url))""",
    """CREATE TABLE versoes_documento (
        id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documentos(id),
        sha256 TEXT NOT NULL, fetched_at TEXT NOT NULL, published_at TEXT,
        fetched_url TEXT NOT NULL, content_type TEXT NOT NULL, byte_size INTEGER NOT NULL CHECK(byte_size >= 0),
        local_path TEXT NOT NULL, extraction_state TEXT NOT NULL DEFAULT 'nao_iniciada'
        CHECK(extraction_state IN ('nao_iniciada','em_andamento','parcial','concluida','falhou')),
        previous_version_id TEXT REFERENCES versoes_documento(id), error_code TEXT,
        UNIQUE(document_id,sha256))""",
    """CREATE TABLE tentativas_download (
        id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documentos(id),
        attempted_at TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('iniciado','concluido','falhou')),
        http_status INTEGER, error_code TEXT, final_url TEXT)""",
    """CREATE TABLE eventos_documentais (
        id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documentos(id),
        version_id TEXT REFERENCES versoes_documento(id),
        event_type TEXT NOT NULL CHECK(event_type IN ('descoberta','download','analise','falha','retificacao','revisao')),
        occurred_at TEXT NOT NULL, related_document_id TEXT REFERENCES documentos(id), note TEXT)""",
    """CREATE TABLE blocos_documento (
        id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES versoes_documento(id),
        page_number INTEGER CHECK(page_number > 0), locator TEXT,
        start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
        text TEXT NOT NULL, CHECK(start_offset >= 0 AND end_offset > start_offset))""",
    """CREATE TABLE evidencias (
        id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES versoes_documento(id),
        block_id TEXT NOT NULL REFERENCES blocos_documento(id), quote TEXT NOT NULL,
        page_number INTEGER, locator TEXT, start_offset INTEGER NOT NULL,
        end_offset INTEGER NOT NULL, captured_at TEXT NOT NULL,
        CHECK(start_offset >= 0 AND end_offset > start_offset))""",
    """CREATE TABLE propostas_campo (
        id TEXT PRIMARY KEY, contest_id TEXT NOT NULL REFERENCES concursos_identidade(id),
        role_id TEXT REFERENCES cargos_identidade(id), field_name TEXT NOT NULL,
        value_json TEXT NOT NULL, value_type TEXT NOT NULL,
        evidence_id TEXT NOT NULL REFERENCES evidencias(id), extraction_method TEXT NOT NULL,
        ambiguity_reason TEXT, extracted_at TEXT NOT NULL)""",
    """CREATE TABLE revisoes_campo (
        id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL REFERENCES propostas_campo(id),
        decision TEXT NOT NULL CHECK(decision IN ('validado','rejeitado')),
        reviewed_at TEXT NOT NULL, reviewer TEXT NOT NULL, reason TEXT NOT NULL)""",
    """CREATE TABLE valores_atuais (
        id TEXT PRIMARY KEY, contest_id TEXT NOT NULL REFERENCES concursos_identidade(id),
        role_id TEXT REFERENCES cargos_identidade(id), field_name TEXT NOT NULL,
        proposal_id TEXT NOT NULL REFERENCES propostas_campo(id), selected_at TEXT NOT NULL,
        selected_by TEXT NOT NULL, supersedes_id TEXT REFERENCES valores_atuais(id),
        reason TEXT NOT NULL)""",
    """CREATE TABLE auditorias_cobertura (
        id TEXT PRIMARY KEY, contest_id TEXT NOT NULL REFERENCES concursos_identidade(id),
        state TEXT NOT NULL CHECK(state IN ('parcial','auditada_ate')),
        checked_at TEXT NOT NULL, checked_urls_json TEXT NOT NULL,
        reviewer TEXT NOT NULL, note TEXT NOT NULL)""",
    "CREATE INDEX idx_observacoes_concurso_contest ON observacoes_concurso(contest_id)",
    "CREATE INDEX idx_cargos_contest ON cargos_identidade(contest_id)",
    "CREATE INDEX idx_observacoes_cargo_observation ON observacoes_cargo(observation_id)",
    "CREATE INDEX idx_documentos_contest ON documentos(contest_id)",
    "CREATE INDEX idx_versoes_documento ON versoes_documento(document_id)",
    "CREATE INDEX idx_eventos_documento ON eventos_documentais(document_id,occurred_at)",
    "CREATE INDEX idx_tentativas_documento ON tentativas_download(document_id,attempted_at)",
    "CREATE INDEX idx_blocos_versao ON blocos_documento(version_id)",
    "CREATE INDEX idx_evidencias_versao ON evidencias(version_id)",
    "CREATE INDEX idx_propostas_contest ON propostas_campo(contest_id,field_name)",
    "CREATE INDEX idx_revisoes_proposta ON revisoes_campo(proposal_id,reviewed_at)",
    "CREATE INDEX idx_valores_contest ON valores_atuais(contest_id,field_name,selected_at)",
    "CREATE INDEX idx_cobertura_contest ON auditorias_cobertura(contest_id,checked_at)",
)


_V3_TABLE = """CREATE TABLE reconciliacoes_cargo (
        id TEXT PRIMARY KEY, contest_id TEXT NOT NULL REFERENCES concursos_identidade(id),
        label TEXT NOT NULL, role_id TEXT NOT NULL REFERENCES cargos_identidade(id),
        reconciled_at TEXT NOT NULL, reviewer TEXT NOT NULL, reason TEXT NOT NULL)"""
_V3_RECON_INDEX = "CREATE INDEX idx_reconciliacoes_contest ON reconciliacoes_cargo(contest_id,label)"
_V3_ADD_COLUMN = "ALTER TABLE versoes_documento ADD COLUMN comparison_sha256 TEXT"
_V3_COMP_INDEX = "CREATE INDEX idx_versoes_comparison ON versoes_documento(document_id,comparison_sha256)"
_V3_DDL = (_V3_TABLE, _V3_RECON_INDEX, _V3_ADD_COLUMN, _V3_COMP_INDEX)

# v4: persistência dos ciclos de monitoramento (aditivo; nada existente muda).
_V4_CICLOS_TABLE = """CREATE TABLE ciclos_monitoramento (
        id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
        state TEXT NOT NULL CHECK(state IN ('em_andamento','concluido','parcial','falhou','interrompido')),
        documents_found INTEGER NOT NULL DEFAULT 0 CHECK(documents_found >= 0),
        documents_new INTEGER NOT NULL DEFAULT 0 CHECK(documents_new >= 0),
        versions_new INTEGER NOT NULL DEFAULT 0 CHECK(versions_new >= 0),
        changes_pending INTEGER NOT NULL DEFAULT 0 CHECK(changes_pending >= 0),
        last_success_at TEXT)"""
_V4_FONTES_TABLE = """CREATE TABLE ciclos_fontes (
        id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES ciclos_monitoramento(id),
        source_url TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('concluido','parcial','falhou','nao_verificada')),
        checked_at TEXT NOT NULL, last_success_at TEXT, http_status INTEGER, error_code TEXT,
        documents_found INTEGER NOT NULL DEFAULT 0 CHECK(documents_found >= 0),
        documents_new INTEGER NOT NULL DEFAULT 0 CHECK(documents_new >= 0),
        versions_new INTEGER NOT NULL DEFAULT 0 CHECK(versions_new >= 0),
        changes_pending INTEGER NOT NULL DEFAULT 0 CHECK(changes_pending >= 0),
        coverage_state TEXT NOT NULL, summary_json TEXT, UNIQUE(cycle_id, source_url))"""
_V4_INDEXES = (
    "CREATE INDEX idx_ciclos_started ON ciclos_monitoramento(started_at)",
    "CREATE INDEX idx_ciclos_fontes_cycle ON ciclos_fontes(cycle_id)",
)
_V4_DDL = (_V4_CICLOS_TABLE, _V4_FONTES_TABLE) + _V4_INDEXES

_V4_COLUMNS = {
    "ciclos_monitoramento": {"id", "started_at", "finished_at", "state", "documents_found",
                             "documents_new", "versions_new", "changes_pending", "last_success_at"},
    "ciclos_fontes": {"id", "cycle_id", "source_url", "state", "checked_at", "last_success_at",
                      "http_status", "error_code", "documents_found", "documents_new", "versions_new",
                      "changes_pending", "coverage_state", "summary_json"},
}

# v5: fila persistente de confirmação documental (aditivo; nada existente muda).
_V5_QUEUE_TABLE = """CREATE TABLE fila_confirmacao (
        observation_id TEXT PRIMARY KEY REFERENCES observacoes_concurso(id),
        source_id TEXT NOT NULL, competition_id TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('pendente','em_processamento','fonte_oficial_localizada',
            'documento_localizado','documento_registrado','documento_processado','revisao_pendente',
            'confirmacao_parcial','nao_localizado','inconclusivo','falhou','concluido')),
        attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
        last_attempt_at TEXT, next_attempt_at TEXT, last_success_at TEXT,
        official_url TEXT, official_source TEXT, document_id TEXT REFERENCES documentos(id),
        priority_score INTEGER NOT NULL DEFAULT 0,
        priority_reason TEXT, reason TEXT, ambiguity TEXT,
        result_json TEXT, history_json TEXT, updated_at TEXT NOT NULL)"""
_V5_INDEXES = (
    "CREATE INDEX idx_fila_state ON fila_confirmacao(state)",
    "CREATE INDEX idx_fila_priority ON fila_confirmacao(state, priority_score)",
)
_V5_DDL = (_V5_QUEUE_TABLE,) + _V5_INDEXES

_V5_COLUMNS = {
    "fila_confirmacao": {"observation_id", "source_id", "competition_id", "state", "attempts",
                         "last_attempt_at", "next_attempt_at", "last_success_at", "official_url",
                         "official_source", "document_id", "priority_score", "priority_reason",
                         "reason", "ambiguity", "result_json", "history_json", "updated_at"},
}

# v6: classificação documental fina (aditivo; coluna nova, sem tocar o `kind`).
_V6_ADD_COLUMN = "ALTER TABLE documentos ADD COLUMN tipo_documental TEXT"
_V6_COLUMNS = {"documentos": {"tipo_documental"}}

# v7: código oficial do cargo (identidade contextualizada por concurso; aditivo).
_V7_ADD_COLUMN = "ALTER TABLE cargos_identidade ADD COLUMN code TEXT"
_V7_INDEX = "CREATE INDEX idx_cargos_code ON cargos_identidade(contest_id,code)"
_V7_DDL = (_V7_ADD_COLUMN, _V7_INDEX)
_V7_COLUMNS = {"cargos_identidade": {"code"}}

# v8: alertas persistentes da operação autônoma (aditivo; tabela nova).
_V8_ALERTS_TABLE = """CREATE TABLE alertas (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        severity TEXT NOT NULL CHECK(severity IN ('info','atencao','critico')),
        contest_id TEXT, observation_id TEXT, source_id TEXT,
        dedup_key TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL, detail TEXT,
        event_at TEXT NOT NULL, created_at TEXT NOT NULL,
        seen_at TEXT, dismissed_at TEXT, payload_json TEXT)"""
_V8_INDEXES = (
    "CREATE INDEX idx_alertas_created ON alertas(created_at)",
    "CREATE INDEX idx_alertas_unseen ON alertas(seen_at)",
)
_V8_DDL = (_V8_ALERTS_TABLE,) + _V8_INDEXES
_V8_COLUMNS = {"alertas": {"id", "kind", "severity", "contest_id", "observation_id",
                           "source_id", "dedup_key", "title", "detail", "event_at",
                           "created_at", "seen_at", "dismissed_at", "payload_json"}}

# v9: estado de notificação/adiamento dos alertas + estado operacional (aditivo).
_V9_ADD_COLUMNS = (
    "ALTER TABLE alertas ADD COLUMN notified_at TEXT",
    "ALTER TABLE alertas ADD COLUMN notify_state TEXT",
    "ALTER TABLE alertas ADD COLUMN notify_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE alertas ADD COLUMN notify_error TEXT",
    "ALTER TABLE alertas ADD COLUMN snoozed_until TEXT",
)
_V9_STATE_TABLE = """CREATE TABLE ops_state (
        key TEXT PRIMARY KEY, value TEXT, updated_at TEXT NOT NULL)"""
_V9_DDL = _V9_ADD_COLUMNS + (_V9_STATE_TABLE,)
_V9_ALERT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_documentos_discovered ON documentos(discovered_at)",
    "CREATE INDEX IF NOT EXISTS idx_versoes_fetched ON versoes_documento(fetched_at)",
)
_V9_COLUMNS = {"alertas": {"notified_at", "notify_state", "notify_attempts",
                           "notify_error", "snoozed_until"},
               "ops_state": {"key", "value", "updated_at"}}

# v10: gestão de estudos (dados **pessoais**, separados do catálogo oficial). Nada aqui é
# exposto pelo contrato v1 nem enviado às fontes. O catálogo de tópicos é separado do
# progresso: `estudo_progresso.contest_id` isola o progresso por edital ('' = geral).
_V10_STUDY_TABLES = (
    """CREATE TABLE estudo_disciplinas (
        id TEXT PRIMARY KEY, nome TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE estudo_topicos (
        id TEXT PRIMARY KEY,
        disciplina_id TEXT NOT NULL REFERENCES estudo_disciplinas(id),
        parent_id TEXT REFERENCES estudo_topicos(id),
        nome TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE estudo_progresso (
        id TEXT PRIMARY KEY,
        contest_id TEXT NOT NULL DEFAULT '',
        topico_id TEXT NOT NULL REFERENCES estudo_topicos(id),
        state TEXT NOT NULL CHECK(state IN ('nao_iniciado','estudando','revisado','concluido')),
        data_conclusao TEXT, adiamentos INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(contest_id, topico_id))""",
    """CREATE TABLE estudo_sessoes (
        id TEXT PRIMARY KEY,
        disciplina_id TEXT REFERENCES estudo_disciplinas(id),
        topico_id TEXT REFERENCES estudo_topicos(id),
        contest_id TEXT NOT NULL DEFAULT '',
        inicio TEXT, fim TEXT,
        duracao_segundos INTEGER NOT NULL DEFAULT 0,
        estado TEXT NOT NULL CHECK(estado IN ('em_andamento','pausada','concluida','descartada')),
        modo TEXT NOT NULL DEFAULT 'livre' CHECK(modo IN ('livre','pomodoro')),
        notas TEXT, created_at TEXT NOT NULL)""",
    """CREATE TABLE estudo_revisoes (
        id TEXT PRIMARY KEY,
        progresso_id TEXT NOT NULL REFERENCES estudo_progresso(id),
        agendada_para TEXT NOT NULL, feita_em TEXT, resultado TEXT,
        created_at TEXT NOT NULL)""",
)
_V10_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_estudo_topicos_disc ON estudo_topicos(disciplina_id)",
    "CREATE INDEX IF NOT EXISTS idx_estudo_progresso_topico ON estudo_progresso(topico_id)",
    "CREATE INDEX IF NOT EXISTS idx_estudo_sessoes_estado ON estudo_sessoes(estado)",
    "CREATE INDEX IF NOT EXISTS idx_estudo_revisoes_agenda ON estudo_revisoes(agendada_para)",
    # Defesa em profundidade: no máximo UMA sessão aberta (em andamento/pausada).
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_estudo_sessao_unica ON estudo_sessoes((1)) "
    "WHERE estado IN ('em_andamento','pausada')",
)
_V10_DDL = _V10_STUDY_TABLES  # índices (IF NOT EXISTS) aplicados por `_apply_v10`
_V10_COLUMNS = {
    "estudo_disciplinas": {"id", "nome", "created_at"},
    "estudo_topicos": {"id", "disciplina_id", "parent_id", "nome", "created_at"},
    "estudo_progresso": {"id", "contest_id", "topico_id", "state", "data_conclusao",
                         "adiamentos", "created_at", "updated_at"},
    "estudo_sessoes": {"id", "disciplina_id", "topico_id", "contest_id", "inicio", "fim",
                       "duracao_segundos", "estado", "modo", "notas", "created_at"},
    "estudo_revisoes": {"id", "progresso_id", "agendada_para", "feita_em", "resultado", "created_at"},
}

# v11: perfil pessoal de conhecimentos (Fase 22). É **dado pessoal**, separado do conteúdo
# oficial do edital (que vive em `propostas_campo`/`evidencias`). Um conceito é identificado
# por uma chave normalizada (`conceito_key`). As dimensões são **separadas**:
#   - `nivel`  = familiaridade declarada (subjetiva).
#   - `revisar`= necessidade de revisão (decisão de planejamento), NÃO um nível de domínio.
#   - `origem` = de onde veio o valor (ex.: "usuario", "resultado"), para nunca confundir
#                declaração do usuário com desempenho observado.
_V11_PROFILE_TABLE = """CREATE TABLE estudo_perfil (
    id TEXT PRIMARY KEY,
    conceito_key TEXT NOT NULL UNIQUE,
    disciplina TEXT, rotulo TEXT NOT NULL,
    nivel TEXT NOT NULL CHECK(nivel IN ('nao_avaliado','nao_conheco','basico','intermediario','avancado')),
    revisar INTEGER NOT NULL DEFAULT 0,
    confianca TEXT CHECK(confianca IN ('baixa','media','alta')),
    observacoes TEXT, origem TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
_V11_DDL = (_V11_PROFILE_TABLE,)
_V11_COLUMNS = {"estudo_perfil": {"id", "conceito_key", "disciplina", "rotulo", "nivel",
                                  "revisar", "confianca", "observacoes", "origem",
                                  "created_at", "updated_at"}}

_V2_COLUMNS = {
    "concursos_identidade": {"id", "created_at"},
    "observacoes_concurso": {"id", "contest_id", "source_url", "competition_id", "observed_at"},
    "cargos_identidade": {"id", "contest_id", "name", "specialty", "created_at"},
    "observacoes_cargo": {"id", "role_id", "observation_id", "role", "observed_at"},
    "documentos": {"id", "contest_id", "observation_id", "role_id", "kind", "official_url", "final_url", "issuer", "published_at", "source_identifier", "title", "discovered_at", "last_checked_at", "discovery_url", "discovery_method"},
    "documento_urls": {"document_id", "url", "observed_at", "is_primary"},
    "versoes_documento": {"id", "document_id", "sha256", "fetched_at", "published_at", "fetched_url", "content_type", "byte_size", "local_path", "extraction_state", "previous_version_id", "error_code"},
    "tentativas_download": {"id", "document_id", "attempted_at", "state", "http_status", "error_code", "final_url"},
    "eventos_documentais": {"id", "document_id", "version_id", "event_type", "occurred_at", "related_document_id", "note"},
    "blocos_documento": {"id", "version_id", "page_number", "locator", "start_offset", "end_offset", "text"},
    "evidencias": {"id", "version_id", "block_id", "quote", "page_number", "locator", "start_offset", "end_offset", "captured_at"},
    "propostas_campo": {"id", "contest_id", "role_id", "field_name", "value_json", "value_type", "evidence_id", "extraction_method", "ambiguity_reason", "extracted_at"},
    "revisoes_campo": {"id", "proposal_id", "decision", "reviewed_at", "reviewer", "reason"},
    "valores_atuais": {"id", "contest_id", "role_id", "field_name", "proposal_id", "selected_at", "selected_by", "supersedes_id", "reason"},
    "auditorias_cobertura": {"id", "contest_id", "state", "checked_at", "checked_urls_json", "reviewer", "note"},
}

# Versão corrente do esquema documental (v2 base + reconciliação/hash + monitoramento + fila).
SCHEMA_VERSION = 11

# Versões que as rotas de leitura aceitam sem migrar (v2..v10).
_READABLE_VERSIONS = (2, 3, 4, 5, 6, 7, 8, 9, 10, SCHEMA_VERSION)


def _validate_schema(conn, statements, columns_by_table, version_label):
    present = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    expected = set()
    for statement in statements:
        match = re.match(r"CREATE (?:TABLE|INDEX) (\w+)", statement)
        if match:
            expected.add(match.group(1))
    if not expected.issubset(present):
        raise ValueError(f"esquema documental {version_label} incompleto")
    for table, columns in columns_by_table.items():
        actual = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if not columns.issubset(actual):
            raise ValueError(f"esquema documental {version_label} incompleto")


def _apply_v3(conn) -> None:
    """Adiciona componentes v3 ausentes, tolerando banco parcialmente atualizado."""
    present = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    columns = {row[1] for row in conn.execute("PRAGMA table_info(versoes_documento)")}
    if "reconciliacoes_cargo" not in present:
        conn.execute(_V3_TABLE)
    if "idx_reconciliacoes_contest" not in present:
        conn.execute(_V3_RECON_INDEX)
    if "comparison_sha256" not in columns:
        conn.execute(_V3_ADD_COLUMN)
    if "idx_versoes_comparison" not in present:
        conn.execute(_V3_COMP_INDEX)


def _apply_v4(conn) -> None:
    """Adiciona componentes v4 ausentes, tolerando banco parcialmente atualizado."""
    present = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    if "ciclos_monitoramento" not in present:
        conn.execute(_V4_CICLOS_TABLE)
    if "ciclos_fontes" not in present:
        conn.execute(_V4_FONTES_TABLE)
    for statement in _V4_INDEXES:
        match = re.match(r"CREATE INDEX (\w+)", statement)
        if match and match.group(1) not in present:
            conn.execute(statement)


def _apply_v5(conn) -> None:
    """Adiciona componentes v5 ausentes, tolerando banco parcialmente atualizado."""
    present = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    if "fila_confirmacao" not in present:
        conn.execute(_V5_QUEUE_TABLE)
    for statement in _V5_INDEXES:
        match = re.match(r"CREATE INDEX (\w+)", statement)
        if match and match.group(1) not in present:
            conn.execute(statement)


def _apply_v6(conn) -> None:
    """Adiciona a coluna de classificação fina, tolerando banco parcialmente atualizado."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(documentos)")}
    if "tipo_documental" not in columns:
        conn.execute(_V6_ADD_COLUMN)


def _apply_v7(conn) -> None:
    """Adiciona o código do cargo, tolerando banco parcialmente atualizado."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cargos_identidade)")}
    if "code" not in columns:
        conn.execute(_V7_ADD_COLUMN)
    present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    if "idx_cargos_code" not in present:
        conn.execute(_V7_INDEX)


def _apply_v8(conn) -> None:
    """Adiciona a tabela de alertas, tolerando banco parcialmente atualizado."""
    present = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    if "alertas" not in present:
        conn.execute(_V8_ALERTS_TABLE)
    for statement in _V8_INDEXES:
        name = re.match(r"CREATE INDEX (\w+)", statement).group(1)
        if name not in present:
            conn.execute(statement)


def _apply_v11(conn) -> None:
    """Cria a tabela do perfil pessoal (v11), tolerando banco parcialmente atualizado."""
    present = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    if "estudo_perfil" not in present:
        conn.execute(_V11_PROFILE_TABLE)


def _apply_v10(conn) -> None:
    """Cria as tabelas de estudo (v10), tolerando banco parcialmente atualizado."""
    present = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    for statement in _V10_STUDY_TABLES:
        name = re.match(r"CREATE TABLE (\w+)", statement).group(1)
        if name not in present:
            conn.execute(statement)
    for statement in _V10_INDEXES:
        conn.execute(statement)


def _apply_v9(conn) -> None:
    """Adiciona estado de notificação/adiamento e `ops_state`, tolerando banco parcial."""
    present = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    if "ops_state" not in present:
        conn.execute(_V9_STATE_TABLE)
    alert_cols = {row[1] for row in conn.execute("PRAGMA table_info(alertas)")}
    for statement in _V9_ADD_COLUMNS:
        column = statement.rsplit("ADD COLUMN ", 1)[1].split()[0]
        if column not in alert_cols:
            conn.execute(statement)


_ALERT_WATERMARKS = (
    ("documentos", "discovered_at", "alerts.watermark.documentos"),
    ("versoes_documento", "fetched_at", "alerts.watermark.versoes"),
)


def _seed_alert_watermarks(conn) -> None:
    """Semeia os watermarks de alertas com o cursor atual, quando ainda ausentes.

    Sem isso, a primeira geração de alertas após a migração para v9 reprocessaria **todo**
    o histórico de documentos/versões. Alertas cuja chave de dedup mudou (ex.:
    `documento_recuperado`) seriam então inseridos de novo, duplicando eventos - e, com as
    notificações ligadas, reemitindo toasts. O watermark também evita o full scan por ciclo.
    Só semeia quando há linhas e nenhum watermark prévio (idempotente).
    """
    for table, column, key in _ALERT_WATERMARKS:
        if conn.execute("SELECT 1 FROM ops_state WHERE key=?", (key,)).fetchone():
            continue
        row = conn.execute(
            f"SELECT {column}, id FROM {table} ORDER BY {column} DESC, id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO ops_state(key, value, updated_at) VALUES(?,?,?)",
            (key, json.dumps([row[0], row[1]]), _now()))


def _ensure_alert_indexes(conn) -> None:
    """Índices para a varredura por watermark dos alertas (idempotente)."""
    for statement in _V9_ALERT_INDEXES:
        conn.execute(statement)


def connect_documents(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=15)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def is_readable_schema(conn) -> bool:
    """``True`` quando a versão do esquema é legível (migração documental aplicada)."""
    return conn.execute("PRAGMA user_version").fetchone()[0] in _READABLE_VERSIONS

def migrate_document_schema(db_path) -> None:
    """Aplica migração aditiva até a versão corrente, atomicamente e sem tocar v1."""
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 2, 3, 4, 5, 6, 7, 8, 9, 10, SCHEMA_VERSION):
            raise ValueError(f"versão de esquema não suportada: {version}")
        _v3_extra = dict(
            versoes_documento=_V2_COLUMNS["versoes_documento"] | {"comparison_sha256"},
            reconciliacoes_cargo={"id", "contest_id", "label", "role_id", "reconciled_at", "reviewer", "reason"})
        _v6_extra = dict(_V6_COLUMNS, documentos=_V2_COLUMNS["documentos"] | {"tipo_documental"})
        _v7_extra = dict(_V6_COLUMNS, documentos=_V2_COLUMNS["documentos"] | {"tipo_documental"},
                         cargos_identidade=_V2_COLUMNS["cargos_identidade"] | {"code"})
        _v8_extra = dict(_v7_extra, **_V8_COLUMNS)
        _v9_extra = dict(_v8_extra)
        _v9_extra["alertas"] = _V8_COLUMNS["alertas"] | _V9_COLUMNS["alertas"]
        _v9_extra["ops_state"] = _V9_COLUMNS["ops_state"]
        _v10_extra = dict(_v9_extra, **_V10_COLUMNS)
        _v11_extra = dict(_v10_extra, **_V11_COLUMNS)
        if version == SCHEMA_VERSION:
            _validate_schema(conn, _DDL + _V3_DDL + _V4_DDL + _V5_DDL + _V8_DDL + _V9_DDL + _V10_DDL + _V11_DDL,
                             dict(_V2_COLUMNS, **_v3_extra, **_V4_COLUMNS, **_V5_COLUMNS, **_v11_extra),
                             f"v{SCHEMA_VERSION}")
            _seed_alert_watermarks(conn)
            _apply_v10(conn)  # garante índices v10 (ex.: sessão aberta única) em base já migrada
            _apply_v11(conn)
        else:
            if version == 2:
                _validate_schema(conn, _DDL, _V2_COLUMNS, "v2")
            elif version == 3:
                _validate_schema(conn, _DDL + _V3_DDL, dict(_V2_COLUMNS, **_v3_extra), "v3")
            elif version == 4:
                _validate_schema(conn, _DDL + _V3_DDL + _V4_DDL,
                                 dict(_V2_COLUMNS, **_v3_extra, **_V4_COLUMNS), "v4")
            elif version == 5:
                _validate_schema(conn, _DDL + _V3_DDL + _V4_DDL + _V5_DDL,
                                 dict(_V2_COLUMNS, **_v3_extra, **_V4_COLUMNS, **_V5_COLUMNS), "v5")
            elif version == 6:
                _validate_schema(conn, _DDL + _V3_DDL + _V4_DDL + _V5_DDL,
                                 dict(_V2_COLUMNS, **_v3_extra, **_V4_COLUMNS, **_V5_COLUMNS, **_v6_extra), "v6")
            elif version == 7:
                _validate_schema(conn, _DDL + _V3_DDL + _V4_DDL + _V5_DDL,
                                 dict(_V2_COLUMNS, **_v3_extra, **_V4_COLUMNS, **_V5_COLUMNS, **_v7_extra), "v7")
            elif version == 8:
                _validate_schema(conn, _DDL + _V3_DDL + _V4_DDL + _V5_DDL + _V8_DDL,
                                 dict(_V2_COLUMNS, **_v3_extra, **_V4_COLUMNS, **_V5_COLUMNS, **_v8_extra), "v8")
            elif version == 9:
                _validate_schema(conn, _DDL + _V3_DDL + _V4_DDL + _V5_DDL + _V8_DDL + _V9_DDL,
                                 dict(_V2_COLUMNS, **_v3_extra, **_V4_COLUMNS, **_V5_COLUMNS, **_v9_extra), "v9")
            elif version == 10:
                _validate_schema(conn, _DDL + _V3_DDL + _V4_DDL + _V5_DDL + _V8_DDL + _V9_DDL + _V10_DDL,
                                 dict(_V2_COLUMNS, **_v3_extra, **_V4_COLUMNS, **_V5_COLUMNS, **_v10_extra), "v10")
            else:
                for statement in _DDL:
                    conn.execute(statement)
            _apply_v3(conn)
            _apply_v4(conn)
            _apply_v5(conn)
            _apply_v6(conn)
            _apply_v7(conn)
            _apply_v8(conn)
            _apply_v9(conn)
            _apply_v10(conn)
            _apply_v11(conn)
            _seed_alert_watermarks(conn)
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        _ensure_alert_indexes(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_url(url: str) -> str:
    if not isinstance(url, str):
        raise ValueError("URL inválida")
    parts = urlsplit(url)
    if parts.scheme.lower() != "https" or not parts.hostname or parts.username or parts.password or parts.port:
        raise ValueError("URL HTTPS pública obrigatória")
    return urlunsplit(("https", parts.hostname.lower(), parts.path or "/", parts.query, ""))


# Marcadores estruturais de telemetria cujo conteúdo varia entre requisições sem
# alterar o documento. A normalização remove apenas o conteúdo desses scripts.
_TELEMETRY_MARKERS = ("bam.nr-data.net", "NREUM.info")
_SCRIPT_RE = re.compile(r"<script\b[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)


def comparison_fingerprint(content: bytes, content_type: str) -> str:
    """Impressão estável do conteúdo documental, normalizando só telemetria comprovada.

    O hash bruto (sha256) continua identificando os bytes armazenados; esta
    impressão reduz versões artificiais quando apenas a telemetria muda.
    """
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime != "text/html":
        return hashlib.sha256(content).hexdigest()

    def _neutralize(match: re.Match) -> str:
        inner = match.group(1)
        if any(marker in inner for marker in _TELEMETRY_MARKERS):
            return "<script></script>"
        return match.group(0)

    text = content.decode("utf-8", "replace")
    normalized = _SCRIPT_RE.sub(_neutralize, text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def register_document(db_path, candidate: dict) -> str:
    """Registra URL oficial no concurso identificado por observação, sem mesclas por título."""
    url = _canonical_url(candidate["official_url"])
    discovery_url = _canonical_url(candidate["discovery_url"])
    if candidate["kind"] not in {"edital", "retificacao", "outro"}:
        raise ValueError("tipo de documento inválido")
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        observation = conn.execute(
            "SELECT contest_id FROM observacoes_concurso WHERE id=?", (candidate["observation_id"],)
        ).fetchone()
        if observation is None:
            raise ValueError("observação inexistente")
        contest_id = observation[0]
        role_id = candidate.get("role_id")
        if role_id and not conn.execute(
            """SELECT 1 FROM cargos_identidade r JOIN observacoes_cargo o ON o.role_id=r.id
            WHERE r.id=? AND r.contest_id=? AND o.observation_id=?""",
            (role_id, contest_id, candidate["observation_id"])
        ).fetchone():
            raise ValueError("cargo sem vínculo com a observação")
        existing = conn.execute(
            "SELECT id FROM documentos WHERE observation_id=? AND official_url=?",
            (candidate["observation_id"], url),
        ).fetchone()
        if existing:
            conn.commit()
            return existing[0]
        # A mesma URL em outra observação da mesma identidade é ambígua sem revisão.
        if conn.execute(
            "SELECT id FROM documentos WHERE contest_id=? AND official_url=?", (contest_id, url)
        ).fetchone():
            raise ValueError("URL já atribuída a outra observação deste concurso")
        document_id = str(uuid4())
        document_type = candidate.get("document_type")
        if document_type is not None and not isinstance(document_type, str):
            raise ValueError("tipo documental inválido")
        conn.execute(
            """INSERT INTO documentos
            (id,contest_id,observation_id,role_id,kind,official_url,title,discovered_at,
            discovery_url,discovery_method,issuer,published_at,source_identifier,tipo_documental)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (document_id, contest_id, candidate["observation_id"], role_id, candidate["kind"],
             url, candidate["title"], candidate["discovered_at"], discovery_url,
             candidate["discovery_method"], candidate.get("issuer"), candidate.get("published_at"),
             candidate.get("source_identifier"), document_type),
        )
        conn.execute("INSERT INTO documento_urls VALUES (?,?,?,1)", (document_id, url, candidate["discovered_at"]))
        conn.execute(
            "INSERT INTO eventos_documentais (id,document_id,event_type,occurred_at) VALUES (?,?,'descoberta',?)",
            (str(uuid4()), document_id, candidate["discovered_at"]),
        )
        conn.commit()
        return document_id
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_version(db_path, document_id: str, content: bytes, metadata: dict) -> str:
    """Salva bytes íntegros por hash e publica a versão somente após escrita atômica."""
    if not isinstance(content, bytes) or not content:
        raise ValueError("conteúdo integral obrigatório")
    digest = hashlib.sha256(content).hexdigest()
    comparison = comparison_fingerprint(content, metadata["content_type"])
    artifact_dir = Path(db_path).resolve().parent / (Path(db_path).name + ".documents")
    conn = connect_documents(db_path)
    temp_name = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM documentos WHERE id=?", (document_id,)).fetchone():
            raise ValueError("documento inexistente")
        target = artifact_dir / digest
        if target.exists():
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError("artefato existente não corresponde ao hash")
        previous = conn.execute("SELECT id FROM versoes_documento WHERE document_id=? AND sha256=?", (document_id, digest)).fetchone()
        if previous:
            conn.commit()
            return previous[0]
        # Mesmo conteúdo documental com bytes brutos diferentes (telemetria) não cria versão nova.
        same_content = conn.execute(
            "SELECT id FROM versoes_documento WHERE document_id=? AND comparison_sha256=?",
            (document_id, comparison)).fetchone()
        if same_content:
            conn.commit()
            return same_content[0]
        artifact_dir.mkdir(exist_ok=True)
        if not target.exists():
            with tempfile.NamedTemporaryFile(dir=artifact_dir, delete=False) as stream:
                temp_name = stream.name
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, target)
            temp_name = None
        prior = conn.execute("SELECT id FROM versoes_documento WHERE document_id=? ORDER BY fetched_at DESC,id DESC LIMIT 1", (document_id,)).fetchone()
        version_id = str(uuid4())
        conn.execute(
            """INSERT INTO versoes_documento
            (id,document_id,sha256,comparison_sha256,fetched_at,published_at,fetched_url,content_type,byte_size,local_path,previous_version_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (version_id, document_id, digest, comparison, metadata["fetched_at"], metadata.get("published_at"),
             _canonical_url(metadata["fetched_url"]), metadata["content_type"], len(content),
             str(Path(artifact_dir.name) / digest), prior[0] if prior else None),
        )
        conn.execute("INSERT INTO eventos_documentais (id,document_id,version_id,event_type,occurred_at) VALUES (?,?,?,'download',?)",
                     (str(uuid4()), document_id, version_id, metadata["fetched_at"]))
        conn.commit()
        return version_id
    except BaseException:
        conn.rollback()
        raise
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        conn.close()


def link_amendment(db_path, amendment_document_id: str, original_document_id: str,
                   reviewer: str, reason: str) -> str:
    """Liga uma retificação ao documento original por decisão humana, sem mesclar identidades."""
    if not reviewer or not reviewer.strip() or not reason or not reason.strip():
        raise ValueError("revisor e justificativa são obrigatórios")
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        amendment = conn.execute("SELECT contest_id,kind FROM documentos WHERE id=?",
                                 (amendment_document_id,)).fetchone()
        original = conn.execute("SELECT contest_id FROM documentos WHERE id=?",
                                (original_document_id,)).fetchone()
        if amendment is None or original is None:
            raise ValueError("documento inexistente")
        if amendment_document_id == original_document_id:
            raise ValueError("documento não pode se relacionar a si mesmo")
        if amendment[1] != "retificacao":
            raise ValueError("apenas documento de retificação pode ser vinculado a um original")
        if amendment[0] != original[0]:
            raise ValueError("documentos de concursos diferentes")
        existing = conn.execute(
            """SELECT id FROM eventos_documentais WHERE document_id=? AND event_type='retificacao'
            AND related_document_id=?""", (amendment_document_id, original_document_id)).fetchone()
        if existing:
            conn.commit()
            return existing[0]
        event_id = str(uuid4())
        conn.execute(
            """INSERT INTO eventos_documentais
            (id,document_id,event_type,occurred_at,related_document_id,note)
            VALUES (?,?,'retificacao',?,?,?)""",
            (event_id, amendment_document_id, _now(), original_document_id,
             f"{reviewer.strip()}: {reason.strip()}"))
        conn.commit()
        return event_id
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


_FIELDS = {"education", "accepted_courses", "si_compatibility", "immediate_vacancies",
            "reserve_vacancies", "indigenous_vacancies", "indigenous_reserve_vacancies",
            "registration_start", "registration_end", "exam_date", "exam_location", "work_location",
            "exemption_start", "exemption_end", "exemption_result_preliminary",
            "exemption_appeal", "exemption_result_final",
            # Conteúdo programático (Fase 22): níveis hierárquicos da seção de programa.
            "conteudo_secao", "conteudo_disciplina", "conteudo_topico", "conteudo_subtopico"}
_COUNTS = {"immediate_vacancies", "reserve_vacancies", "indigenous_vacancies",
           "indigenous_reserve_vacancies"}
# Campos de conteúdo programático (multi-item; não entram na detecção de conflito escalar).
_CONTENT_FIELDS = {"conteudo_secao", "conteudo_disciplina", "conteudo_topico", "conteudo_subtopico"}
_DATES = {"registration_start", "registration_end", "exam_date", "exemption_start",
          "exemption_end", "exemption_result_preliminary", "exemption_appeal",
          "exemption_result_final"}


def record_analysis(db_path, version_id: str, blocks: list[dict], proposals: list[dict]) -> None:
    """Persiste blocos e propostas somente se todas as citações são verificáveis."""
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        version = conn.execute(
            "SELECT d.contest_id,d.id,d.observation_id,d.role_id FROM versoes_documento v JOIN documentos d ON d.id=v.document_id WHERE v.id=?",
            (version_id,),
        ).fetchone()
        if version is None:
            raise ValueError("versão inexistente")
        contest_id, document_id, observation_id, document_role_id = version
        if conn.execute("SELECT 1 FROM blocos_documento WHERE version_id=? LIMIT 1", (version_id,)).fetchone():
            raise ValueError("versão já analisada")
        block_ids = []
        for block in blocks:
            text = block["text"]
            start, end = block["start_offset"], block["end_offset"]
            if not isinstance(text, str) or not text or start < 0 or end <= start or end > len(text):
                raise ValueError("limites de bloco inválidos")
            block_id = str(uuid4())
            conn.execute(
                "INSERT INTO blocos_documento VALUES (?,?,?,?,?,?,?)",
                (block_id, version_id, block.get("page_number"), block.get("locator"), start, end, text),
            )
            block_ids.append(block_id)
        period_dates = {}
        for proposal in proposals:
            index = proposal["evidence"]["block_index"]
            if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(blocks):
                raise ValueError("bloco inexistente")
            evidence, block = proposal["evidence"], blocks[index]
            start, end = evidence["start_offset"], evidence["end_offset"]
            if not (isinstance(start, int) and isinstance(end, int) and
                    0 <= start < end <= len(block["text"]) and
                    block["text"][start:end] == evidence["quote"]):
                raise ValueError("citação não corresponde ao bloco")
            role_id = proposal.get("role_id")
            if proposal["contest_id"] != contest_id or proposal["field_name"] not in _FIELDS:
                raise ValueError("escopo ou campo inválido")
            if document_role_id is not None and role_id != document_role_id:
                raise ValueError("proposta fora do escopo do cargo documental")
            if role_id and (document_role_id not in (None, role_id) or not conn.execute(
                """SELECT 1 FROM cargos_identidade r JOIN observacoes_cargo o ON o.role_id=r.id
                WHERE r.id=? AND r.contest_id=? AND o.observation_id=?""",
                (role_id, contest_id, observation_id)).fetchone()):
                raise ValueError("cargo inválido")
            value = json.loads(proposal["value_json"])
            expected_type = "integer" if proposal["field_name"] in _COUNTS else "string"
            if proposal["value_type"] != expected_type:
                raise ValueError("tipo incompatível com campo")
            if proposal["value_type"] == "integer":
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError("quantidade inválida")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError("valor inválido")
            if proposal["field_name"] in _DATES:
                try:
                    parsed = date.fromisoformat(value)
                    if parsed.isoformat() != value:
                        raise ValueError("formato de data inválido")
                except ValueError as error:
                    raise ValueError("data impossível ou inválida") from error
                if proposal["field_name"] != "exam_date":
                    period_dates.setdefault(role_id, {})[proposal["field_name"]] = parsed
            evidence_id = str(uuid4())
            conn.execute(
                "INSERT INTO evidencias VALUES (?,?,?,?,?,?,?,?,?)",
                (evidence_id, version_id, block_ids[index], evidence["quote"], block.get("page_number"),
                 block.get("locator"), start, end, _now()),
            )
            conn.execute(
                "INSERT INTO propostas_campo VALUES (?,?,?,?,?,?,?,?,?,?)",
                (str(uuid4()), contest_id, role_id, proposal["field_name"], proposal["value_json"],
                 proposal["value_type"], evidence_id, proposal["extraction_method"],
                  proposal.get("ambiguity_reason"), _now()),
            )
        for period in period_dates.values():
            if period.get("registration_start", date.min) > period.get("registration_end", date.max):
                raise ValueError("datas de inscrição invertidas")
        conn.execute("UPDATE versoes_documento SET extraction_state=? WHERE id=?",
                     ("parcial" if blocks else "falhou", version_id))
        conn.execute("INSERT INTO eventos_documentais (id,document_id,version_id,event_type,occurred_at) VALUES (?,?,?,'analise',?)",
                     (str(uuid4()), document_id, version_id, _now()))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def sync_v1_identifiers(db_path) -> None:
    """Cria identidades somente quando invocado, sem tocar nos dados v1."""
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("PRAGMA user_version").fetchone()[0] not in _READABLE_VERSIONS:
            raise ValueError("migração documental pendente")
        present = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='concursos'").fetchone()
        rows = conn.execute(
            "SELECT source_url, competition_id, role FROM concursos ORDER BY source_url, competition_id, role"
        ).fetchall() if present else []
        for source_url, competition_id, role in rows:
            observation = conn.execute(
                "SELECT id, contest_id FROM observacoes_concurso WHERE source_url=? AND competition_id=?",
                (source_url, competition_id),
            ).fetchone()
            if observation is None:
                contest_id, observation_id = str(uuid4()), str(uuid4())
                conn.execute("INSERT INTO concursos_identidade VALUES (?,?)", (contest_id, _now()))
                conn.execute(
                    "INSERT INTO observacoes_concurso VALUES (?,?,?,?,?)",
                    (observation_id, contest_id, source_url, competition_id, _now()),
                )
            else:
                observation_id, contest_id = observation
            existing = conn.execute(
                "SELECT id FROM observacoes_cargo WHERE observation_id=? AND role=?",
                (observation_id, role),
            ).fetchone()
            if existing is None:
                role_id = str(uuid4())
                conn.execute(
                    "INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at) VALUES (?,?,?,?,?)",
                    (role_id, contest_id, role, None, _now()),
                )
                conn.execute(
                    "INSERT INTO observacoes_cargo VALUES (?,?,?,?,?)",
                    (str(uuid4()), role_id, observation_id, role, _now()),
                )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_observation(db_path, source_url: str, competition_id: str) -> str:
    """Garante identidade de concurso + observação para uma fonte, de forma idempotente.

    Aditivo e genérico: usado por fontes que não derivam de ``concursos`` v1
    (por exemplo, uma segunda fonte oficial). Não altera dados v1 nem mescla
    identidades existentes; devolve o ``observation_id`` estável.
    """
    source_url = _canonical_url(source_url)
    if not isinstance(competition_id, str) or not competition_id.strip():
        raise ValueError("competition_id obrigatório")
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("PRAGMA user_version").fetchone()[0] not in _READABLE_VERSIONS:
            raise ValueError("migração documental pendente")
        existing = conn.execute(
            "SELECT id FROM observacoes_concurso WHERE source_url=? AND competition_id=?",
            (source_url, competition_id),
        ).fetchone()
        if existing:
            conn.commit()
            return existing[0]
        contest_id, observation_id = str(uuid4()), str(uuid4())
        conn.execute("INSERT INTO concursos_identidade VALUES (?,?)", (contest_id, _now()))
        conn.execute(
            "INSERT INTO observacoes_concurso VALUES (?,?,?,?,?)",
            (observation_id, contest_id, source_url, competition_id, _now()),
        )
        conn.commit()
        return observation_id
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def normalize_role(text) -> str:
    """Normaliza um rótulo de cargo para comparação exata (sem similaridade textual)."""
    import unicodedata
    if not isinstance(text, str):
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", ascii_text.lower()).split())


def role_names_compatible(a, b) -> bool:
    """Compatibilidade tolerante a variação de formatação (mesmo cargo, mesmo código).

    Verdadeiro quando os nomes compartilham ao menos um token significativo; nomes sem
    tokens (vazios) não são tratados como conflito. Não é usada para **fundir** cargos —
    apenas para verificar consistência quando o código já identifica o cargo.
    """
    ta = {t for t in normalize_role(a).split() if len(t) >= 3}
    tb = {t for t in normalize_role(b).split() if len(t) >= 3}
    if not ta or not tb:
        return True
    return bool(ta & tb)


def ensure_role(db_path, contest_id: str, observation_id: str, name: str,
                specialty: str | None = None, code: str | None = None) -> str:
    """Garante identidade de cargo para um concurso, de forma idempotente.

    A identidade é **contextualizada pelo concurso**. Quando o cargo tem um **código
    oficial** (ex.: Quadrix), a chave é ``(contest_id, code)``; sem código, é
    ``(contest_id, name, specialty)``. Nunca se funde por similaridade textual.

    Cria ``cargos_identidade`` + ``observacoes_cargo`` a partir do rótulo do próprio
    documento. Reexecutar com a mesma identidade devolve o id existente. Se o código
    já estiver associado a um nome materialmente diferente no mesmo concurso, levanta
    ``ValueError`` (associação ambígua não é feita em silêncio).
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("nome do cargo obrigatório")
    specialty = specialty.strip() if isinstance(specialty, str) and specialty.strip() else None
    code = code.strip() if isinstance(code, str) and code.strip() else None
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("PRAGMA user_version").fetchone()[0] not in _READABLE_VERSIONS:
            raise ValueError("migração documental pendente")
        if not conn.execute("SELECT 1 FROM concursos_identidade WHERE id=?", (contest_id,)).fetchone():
            raise ValueError("concurso inexistente")
        if not conn.execute("SELECT 1 FROM observacoes_concurso WHERE id=? AND contest_id=?",
                            (observation_id, contest_id)).fetchone():
            raise ValueError("observação inexistente para o concurso")
        existing = None
        if code:
            by_code = conn.execute(
                "SELECT id,name FROM cargos_identidade WHERE contest_id=? AND code=?",
                (contest_id, code)).fetchone()
            if by_code:
                if not role_names_compatible(by_code[1], name.strip()):
                    raise ValueError("código de cargo já associado a outro nome neste concurso")
                existing = by_code[0]
            else:
                # Adota um cargo homônimo ainda sem código (mesmo concurso).
                by_name = conn.execute(
                    "SELECT id FROM cargos_identidade WHERE contest_id=? AND name=? AND specialty IS ? AND code IS NULL",
                    (contest_id, name.strip(), specialty)).fetchone()
                if by_name:
                    conn.execute("UPDATE cargos_identidade SET code=? WHERE id=?", (code, by_name[0]))
                    existing = by_name[0]
        else:
            by_name = conn.execute(
                "SELECT id FROM cargos_identidade WHERE contest_id=? AND name=? AND specialty IS ?",
                (contest_id, name.strip(), specialty)).fetchone()
            if by_name:
                existing = by_name[0]
        if existing:
            role_id = existing
        else:
            role_id = str(uuid4())
            conn.execute(
                "INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at,code) "
                "VALUES (?,?,?,?,?,?)",
                (role_id, contest_id, name.strip(), specialty, _now(), code))
        if not conn.execute("SELECT 1 FROM observacoes_cargo WHERE observation_id=? AND role=?",
                            (observation_id, name.strip())).fetchone():
            conn.execute("INSERT INTO observacoes_cargo VALUES (?,?,?,?,?)",
                         (str(uuid4()), role_id, observation_id, name.strip(), _now()))
        conn.commit()
        return role_id
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_competition_identities(db_path) -> list[dict]:
    if not Path(db_path).exists():
        raise ValueError("migração documental pendente")
    conn = connect_documents(db_path)
    try:
        if conn.execute("PRAGMA user_version").fetchone()[0] not in _READABLE_VERSIONS:
            raise ValueError("migração documental pendente")
        rows = conn.execute(
            "SELECT id FROM concursos_identidade ORDER BY created_at,id"
        ).fetchall()
        return [
            {"id": contest_id, "observations": [
                {"source_url": url, "competition_id": number}
                for url, number in conn.execute(
                    "SELECT source_url,competition_id FROM observacoes_concurso WHERE contest_id=? ORDER BY source_url,competition_id",
                    (contest_id,),
                )
            ]}
            for (contest_id,) in rows
        ]
    finally:
        conn.close()


def monitoring_status(db_path) -> dict:
    """Estado do monitoramento por ciclos persistidos (somente leitura)."""
    if not Path(db_path).exists():
        raise ValueError("migração documental pendente")
    conn = connect_documents(db_path)
    try:
        if conn.execute("PRAGMA user_version").fetchone()[0] not in _READABLE_VERSIONS:
            raise ValueError("migração documental pendente")
        present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "ciclos_monitoramento" not in present:
            raise ValueError("migração documental pendente")
        last = conn.execute(
            """SELECT id,started_at,finished_at,state,documents_found,documents_new,versions_new,
            changes_pending,last_success_at FROM ciclos_monitoramento
            ORDER BY started_at DESC,id DESC LIMIT 1""").fetchone()
        last_cycle = None
        sources = []
        if last:
            (cycle_id, started_at, finished_at, state, found, new, versions, pending, success) = last
            last_cycle = dict(id=cycle_id, state=state, started_at=started_at, finished_at=finished_at,
                              documents_found=found, documents_new=new, versions_new=versions,
                              changes_pending=pending, last_success_at=success)
            for row in conn.execute(
                """SELECT id,source_url,state,checked_at,last_success_at,http_status,error_code,
                documents_found,documents_new,versions_new,changes_pending,coverage_state,summary_json
                FROM ciclos_fontes WHERE cycle_id=? ORDER BY source_url""", (cycle_id,)):
                source = dict(zip(("id", "source_url", "state", "checked_at", "last_success_at",
                                   "http_status", "error_code", "documents_found", "documents_new",
                                   "versions_new", "changes_pending", "coverage_state", "summary_json"), row))
                source["summary"] = json.loads(source.pop("summary_json")) if source["summary_json"] else {}
                sources.append(source)
        pending = conn.execute(
            "SELECT count(*) FROM versoes_documento WHERE extraction_state='nao_iniciada'").fetchone()[0]
        audit = conn.execute(
            "SELECT state FROM auditorias_cobertura ORDER BY checked_at DESC,id DESC LIMIT 1").fetchone()
        return {"last_cycle": last_cycle, "sources": sources,
                "pending_analysis": pending, "coverage_state": audit[0] if audit else "nao_auditada"}
    finally:
        conn.close()


def get_competition_details(db_path, contest_id: str) -> dict | None:
    if not Path(db_path).exists():
        raise ValueError("migração documental pendente")
    conn = connect_documents(db_path)
    try:
        if conn.execute("PRAGMA user_version").fetchone()[0] not in _READABLE_VERSIONS:
            raise ValueError("migração documental pendente")
        exists = conn.execute("SELECT 1 FROM concursos_identidade WHERE id=?", (contest_id,)).fetchone()
        if not exists:
            return None
        observations = [
            {"source_url": url, "competition_id": number}
            for url, number in conn.execute(
                "SELECT source_url,competition_id FROM observacoes_concurso WHERE contest_id=? ORDER BY source_url,competition_id",
                (contest_id,),
            )
        ]
        roles = []
        role_columns = {row[1] for row in conn.execute("PRAGMA table_info(cargos_identidade)")}
        code_expr = "code" if "code" in role_columns else "NULL"
        for role_id, name, specialty, role_code in conn.execute(
            f"SELECT id,name,specialty,{code_expr} FROM cargos_identidade WHERE contest_id=? ORDER BY name,id",
            (contest_id,),
        ):
            role_observations = [
                {"role": role} for (role,) in conn.execute(
                    "SELECT role FROM observacoes_cargo WHERE role_id=? ORDER BY observed_at,id", (role_id,)
                )
            ]
            roles.append({"id": role_id, "name": name, "specialty": specialty,
                          "code": role_code, "observations": role_observations})
        documents = []
        # Bancos v2..v5 (não migrados) não têm a coluna; a leitura degrada para NULL.
        doc_columns = {row[1] for row in conn.execute("PRAGMA table_info(documentos)")}
        type_expr = "tipo_documental" if "tipo_documental" in doc_columns else "NULL"
        for row in conn.execute(
            f"""SELECT id,kind,official_url,final_url,issuer,published_at,title,discovery_url,
            discovery_method,discovered_at,last_checked_at,{type_expr} FROM documentos
            WHERE contest_id=? ORDER BY discovered_at,id""", (contest_id,)
        ):
            (doc_id, kind, official_url, final_url, issuer, published_at, title,
             discovery_url, discovery_method, discovered_at, last_checked_at, tipo_documental) = row
            versions = [
                dict(zip(("id","sha256","comparison_sha256","fetched_at","published_at","fetched_url",
                          "content_type","byte_size","extraction_state","error_code"), version))
                for version in conn.execute(
                    """SELECT id,sha256,comparison_sha256,fetched_at,published_at,fetched_url,content_type,
                    byte_size,extraction_state,error_code FROM versoes_documento
                    WHERE document_id=? ORDER BY fetched_at,id""", (doc_id,))
            ]
            events = [
                dict(zip(("id","event_type","occurred_at","version_id","related_document_id","note"), event))
                for event in conn.execute(
                    """SELECT id,event_type,occurred_at,version_id,related_document_id,note
                    FROM eventos_documentais WHERE document_id=? ORDER BY occurred_at,id""", (doc_id,))
            ]
            attempts = [
                dict(zip(("id","attempted_at","state","http_status","error_code","final_url"), attempt))
                for attempt in conn.execute(
                    """SELECT id,attempted_at,state,http_status,error_code,final_url
                    FROM tentativas_download WHERE document_id=? ORDER BY attempted_at,id""", (doc_id,))
            ]
            documents.append(dict(id=doc_id, kind=kind, document_type=tipo_documental,
                                  official_url=official_url, final_url=final_url,
                                  issuer=issuer, published_at=published_at, title=title,
                                  discovery_url=discovery_url, discovery_method=discovery_method,
                                  discovered_at=discovered_at, last_checked_at=last_checked_at,
                                  state="baixado" if versions else "localizado", versions=versions,
                                  download_attempts=attempts, events=events,
                                  related_document_ids=[event["related_document_id"] for event in events
                                                        if event["related_document_id"]]))
        proposals = []
        for proposal in conn.execute(
            """SELECT id,role_id,field_name,value_json,value_type,evidence_id,
            extraction_method,ambiguity_reason,extracted_at
            FROM propostas_campo WHERE contest_id=? ORDER BY extracted_at,id""", (contest_id,)
        ):
            (proposal_id, role_id, field_name, value_json, value_type, evidence_id,
             extraction_method, ambiguity_reason, extracted_at) = proposal
            e = conn.execute(
                """SELECT e.id,e.version_id,e.page_number,e.locator,e.quote,e.start_offset,e.end_offset,
                v.document_id FROM evidencias e JOIN versoes_documento v ON v.id=e.version_id WHERE e.id=?""",
                (evidence_id,)
            ).fetchone()
            evidence = dict(zip(("id","version_id","page_number","locator","quote",
                                 "start_offset","end_offset","document_id"), e))
            reviews = [dict(zip(("decision","reviewed_at","reviewer","reason"), review))
                       for review in conn.execute("""SELECT decision,reviewed_at,reviewer,reason
                       FROM revisoes_campo WHERE proposal_id=? ORDER BY reviewed_at,id""", (proposal_id,))]
            state = reviews[-1]["decision"] if reviews else ("ambiguo" if ambiguity_reason else "extraido")
            proposals.append(dict(id=proposal_id, role_id=role_id, field_name=field_name,
                                  value=json.loads(value_json), value_type=value_type,
                                  extraction_method=extraction_method, ambiguity_reason=ambiguity_reason,
                                  state=state, extracted_at=extracted_at, evidence=evidence, reviews=reviews))
        reconciliations = {}
        if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reconciliacoes_cargo'").fetchone():
            for label, role_id, at, reviewer, reason in conn.execute(
                """SELECT label,role_id,reconciled_at,reviewer,reason FROM reconciliacoes_cargo
                WHERE contest_id=? ORDER BY reconciled_at,id""", (contest_id,)
            ):
                reconciliations[label] = {"label": label, "role_id": role_id,
                                          "reconciled_at": at, "reviewer": reviewer, "reason": reason}
        for item in proposals:
            label = label_from_ambiguity(item["ambiguity_reason"])
            item["reconciled_role_id"] = reconciliations[label]["role_id"] if label in reconciliations else None

        def _scope(item):
            label = label_from_ambiguity(item["ambiguity_reason"])
            if item["role_id"] is not None:
                return ("role", item["role_id"], None)
            if label is not None:
                reconciled = reconciliations.get(label)
                if reconciled:
                    return ("role", reconciled["role_id"], None)
                return ("label", None, label)
            return ("contest", None, None)

        grouped = {}
        for item in proposals:
            # O conteúdo programático é multi-item por natureza (vários tópicos por seção);
            # não é "conflito" de campo e é lido por `knowledge_store.resolve_program`.
            if item["field_name"] in _CONTENT_FIELDS:
                continue
            grouped.setdefault(_scope(item) + (item["field_name"],), []).append(item)
        conflicts = []
        for (scope_type, scope_ref, scope_label, field_name), items in grouped.items():
            distinct = {}
            for item in items:
                distinct.setdefault(json.dumps(item["value"], sort_keys=True, ensure_ascii=False), item)
            if len(distinct) > 1:
                conflicts.append({
                    "field_name": field_name, "scope_type": scope_type,
                    "role_id": scope_ref if scope_type == "role" else None,
                    "scope_label": scope_label,
                    "values": [{"proposal_id": item["id"], "value": item["value"],
                                "version_id": item["evidence"]["version_id"],
                                "document_id": item["evidence"]["document_id"]}
                               for item in sorted(distinct.values(), key=lambda x: x["id"])],
                })
        conflicts.sort(key=lambda c: (c["field_name"], c["scope_type"], c["scope_label"] or ""))

        evidence_by_proposal = {item["id"]: item["evidence"] for item in proposals}
        state_by_proposal = {item["id"]: item["state"] for item in proposals}
        current_values = []
        for selection in conn.execute(
            """SELECT id,role_id,field_name,proposal_id,selected_at,selected_by,supersedes_id,reason
            FROM valores_atuais WHERE contest_id=? ORDER BY selected_at,id""", (contest_id,)
        ):
            entry = dict(zip(("id", "role_id", "field_name", "proposal_id", "selected_at", "selected_by",
                              "supersedes_id", "reason"), selection))
            entry["evidence"] = evidence_by_proposal[entry["proposal_id"]]
            current_values.append(entry)
        latest_by_scope = {}
        for entry in current_values:
            if state_by_proposal[entry["proposal_id"]] == "validado":
                latest_by_scope[(entry["role_id"], entry["field_name"])] = entry["id"]
        for entry in current_values:
            entry["active"] = (latest_by_scope.get((entry["role_id"], entry["field_name"])) == entry["id"]
                               and state_by_proposal[entry["proposal_id"]] == "validado")
        audit = conn.execute("""SELECT state,checked_at,checked_urls_json,reviewer,note
            FROM auditorias_cobertura WHERE contest_id=? ORDER BY checked_at DESC,id DESC LIMIT 1""",
            (contest_id,)).fetchone()
        coverage = {"state": "nao_auditada", "checked_at": None, "checked_urls": [], "reviewer": None}
        if audit:
            state, checked_at, urls_json, reviewer, note = audit
            urls = json.loads(urls_json)
            if state == "auditada_ate" and any(d["official_url"] not in urls for d in documents):
                state = "parcial"
            coverage = {"state": state, "checked_at": checked_at, "checked_urls": urls,
                        "reviewer": reviewer, "note": note}
        return {
            "contest": {"id": contest_id, "observations": observations},
            "roles": roles,
            "coverage": coverage,
            "documents": documents, "proposals": proposals, "current_values": current_values,
            "role_reconciliations": list(reconciliations.values()),
            "conflicts": conflicts,
        }
    finally:
        conn.close()
