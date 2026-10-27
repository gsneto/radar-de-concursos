"""Interface comum de conectores e normalização de resultados.

O conector declara o que faz; a **política** decide o que pode ser gravado. Nenhum conector
escreve conteúdo diretamente: ele devolve resultados normalizados e quem persiste consulta
``radar.source_policy``.

Capacidades são explícitas e não equivalentes:
``descobrir`` (pista), ``metadados``, ``edital`` (documento oficial), ``documento``,
``retificacao``, ``questao``, ``prova``, ``importacao_manual``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from radar import source_catalog as catalog
from radar import source_policy

CONNECTOR_VERSION = "connector_v1"

CAPABILITIES = ("descobrir", "metadados", "edital", "documento", "retificacao", "questao",
                "prova", "importacao_manual")


class ConnectorError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Connector:
    """Descritor de conector. Implementações sobrescrevem os métodos que suportam."""

    id: str
    category: str
    capabilities: tuple = ()
    config_requirements: tuple = ()
    content_types: tuple = ()
    pagination: dict = field(default_factory=lambda: {"tipo": "nenhuma"})
    notes: str = ""

    def storage_policy(self) -> dict:
        return {ctype: source_policy.decision(self.id, ctype)
                for ctype in self.content_types}

    def availability(self) -> dict:
        """Disponibilidade declarada, sem rede por padrão."""
        source = catalog.get_source(self.id)
        return {"available": source["status"] == "habilitada",
                "status": source["status"],
                "requires_credential": bool(source.get("credential_env")),
                "credential_env": source.get("credential_env")}

    def discover(self, **kwargs) -> list:
        raise ConnectorError("nao_suportado", f"{self.id} não implementa descoberta")

    def details(self, item, **kwargs) -> dict:
        raise ConnectorError("nao_suportado", f"{self.id} não implementa detalhes")

    def costs(self) -> dict:
        return catalog.get_source(self.id).get("cost") or {}

    def describe(self) -> dict:
        source = catalog.get_source(self.id)
        return {
            "version": CONNECTOR_VERSION,
            "id": self.id,
            "name": source["name"],
            "category": self.category,
            "nature": source["nature"],
            "access": source["access"],
            "capabilities": list(self.capabilities),
            "config_requirements": list(self.config_requirements),
            "content_types": list(self.content_types),
            "storage_policy": self.storage_policy(),
            "availability": self.availability(),
            "pagination": self.pagination,
            "costs": self.costs(),
            "domains": source["domains"],
            "status": source["status"],
            "notes": self.notes or source["notes"],
        }


def normalize(item: dict, *, source_id: str, content_type: str, official: bool,
              collected_at: str | None = None, uncertainty: str | None = None,
              evidence: dict | None = None) -> dict:
    """Formato interno comum, preservando identidade e procedência originais.

    Nunca descarta o identificador original, a URL, a fonte, a data de publicação, a data de
    consulta, a oficialidade nem a incerteza — é disso que a revisão humana depende.
    """
    if not isinstance(item, dict):
        raise ConnectorError("resultado_invalido", "resultado de conector deve ser objeto")
    catalog.get_source(source_id)
    normalized = {
        "source_id": source_id,
        "content_type": content_type,
        "original_id": item.get("original_id") or item.get("id") or item.get("competition_id"),
        "title": item.get("title"),
        "url": item.get("url") or item.get("official_url"),
        "published_at": item.get("published_at"),
        "collected_at": collected_at or datetime.now(timezone.utc).isoformat(),
        "official": bool(official),
        "uncertainty": uncertainty,
        "evidence": evidence or {},
        "raw": None,  # dados brutos só entram se a política permitir; nunca por padrão
        "persistence": source_policy.decision(source_id, content_type),
    }
    if not normalized["url"]:
        raise ConnectorError("resultado_invalido", "resultado sem URL de origem")
    return normalized


def guard_persistence(results, *, purpose: str = "coleta") -> list:
    """Filtra resultados cujo tipo de conteúdo não pode ser persistido.

    Devolve apenas o que a política autoriza; o restante é descartado com motivo. Conteúdo
    transitório nunca chega ao banco nem a relatórios persistidos.
    """
    allowed, blocked = [], []
    for result in results:
        decision = source_policy.decision(result["source_id"], result["content_type"])
        if decision["allowed"]:
            allowed.append(result)
        else:
            blocked.append({"source_id": result["source_id"],
                            "content_type": result["content_type"],
                            "permission": decision["permission"],
                            "reason": decision["reason"]})
    return allowed, blocked


# --- registro ------------------------------------------------------------------

class _ExistingSourceConnector(Connector):
    """Adapta um descritor de ``monitoring.default_sources`` sem duplicar sua lógica."""

    def __init__(self, source_id: str, descriptor: dict, capabilities: tuple,
                 content_types: tuple, pagination: dict | None = None):
        super().__init__(id=source_id, category="concursos", capabilities=capabilities,
                         content_types=content_types,
                         pagination=pagination or {"tipo": "fonte"})
        self._descriptor = descriptor

    def discover(self, **kwargs):
        """Executa a descoberta real do descritor, respeitando a assinatura de cada fonte."""
        descriptor = self._descriptor
        if "discover" not in descriptor or "fetch" not in descriptor:
            raise ConnectorError("nao_suportado", f"{self.id} sem descoberta")
        # Valida os parâmetros antes de qualquer acesso de rede: chamada malformada
        # não deve gerar tráfego para a fonte.
        if descriptor.get("multi_contest"):
            db_path = kwargs.get("db_path")
            if not db_path:
                raise ConnectorError("configuracao_necessaria",
                                     f"{self.id} exige db_path para descoberta")
            return descriptor["discover"](db_path, descriptor["fetch"]())
        observation_id = kwargs.get("observation_id")
        if not observation_id:
            raise ConnectorError("configuracao_necessaria",
                                 f"{self.id} exige observation_id para descoberta")
        return descriptor["discover"](descriptor["fetch"](), observation_id)


def connectors() -> list[Connector]:
    """Conectores registrados: os existentes (sem duplicar lógica) + os novos."""
    from radar.ibge_source import IBGEConnector
    from radar.monitoring import default_sources
    capabilities_by_id = {
        "guajara": ("descobrir", "metadados", "edital", "documento"),
        "dou-secao-3": ("descobrir", "metadados", "edital", "documento", "retificacao"),
        "fgv-conhecimento": ("descobrir", "metadados", "edital", "documento", "retificacao"),
        "quadrix": ("descobrir", "metadados", "edital", "documento", "retificacao"),
        "ibfc": ("descobrir", "metadados", "edital", "documento", "retificacao"),
        "pci": ("descobrir", "metadados"),
    }
    content_by_id = {
        "guajara": ("metadados", "documento", "noticia"),
        "dou-secao-3": ("metadados", "documento"),
        "fgv-conhecimento": ("metadados", "documento"),
        "quadrix": ("metadados", "documento"),
        "ibfc": ("metadados", "documento"),
        "pci": ("metadados", "url", "noticia"),
    }
    registry = []
    for descriptor in default_sources():
        source_id = descriptor.get("id") or "guajara"
        if source_id not in capabilities_by_id:
            continue
        registry.append(_ExistingSourceConnector(
            source_id, descriptor, capabilities_by_id[source_id],
            content_by_id[source_id]))
    registry.append(IBGEConnector())
    return registry


def get_connector(source_id: str) -> Connector:
    for connector in connectors():
        if connector.id == source_id:
            return connector
    raise ConnectorError("conector_inexistente", f"conector não registrado: {source_id}")


def registry_report() -> dict:
    return {"version": CONNECTOR_VERSION,
            "conectores": [connector.describe() for connector in connectors()],
            "catalogo": catalog.summary()}
