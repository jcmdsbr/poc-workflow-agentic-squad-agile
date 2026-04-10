import os
import logging
import requests
from requests.auth import HTTPBasicAuth
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, model_validator
from typing import Any, Optional

logger = logging.getLogger(__name__)

VALID_WORK_ITEM_TYPES = {"Feature", "User Story", "Task"}

# Hierarquia válida: qual tipo de pai cada tipo aceita
PARENT_TYPE_MAP = {
    "Feature": None,          # Feature não tem pai
    "User Story": "Feature",  # US só aceita Feature como pai
    "Task": "User Story",     # Task só aceita US como pai
}


class WorkItemRegistry:
    """Registro global de IDs criados — fonte de verdade para parent_id."""

    def __init__(self):
        self._items: dict[str, list[dict]] = {
            "Feature": [],
            "User Story": [],
            "Task": [],
        }

    def register(self, tipo_item: str, item_id: int, titulo: str, parent_id: int | None = None):
        self._items[tipo_item].append({
            "id": item_id,
            "titulo": titulo,
            "parent_id": parent_id,
        })

    def get_ids(self, tipo_item: str) -> list[int]:
        return [item["id"] for item in self._items[tipo_item]]

    def get_items(self, tipo_item: str) -> list[dict]:
        return self._items[tipo_item]

    def id_exists(self, tipo_item: str, item_id: int) -> bool:
        return item_id in self.get_ids(tipo_item)

    def format_valid_ids(self, tipo_item: str) -> str:
        items = self._items[tipo_item]
        if not items:
            return f"Nenhum {tipo_item} criado ainda."
        lines = [f"  - ID={it['id']}: {it['titulo']}" for it in items]
        return f"IDs válidos de {tipo_item}:\n" + "\n".join(lines)


# Instância global — compartilhada entre todos os agentes
registry = WorkItemRegistry()


class WorkItemInput(BaseModel):
    titulo: str = Field(description="Título do Work Item.")
    descricao: str = Field(description="Descrição detalhada do Work Item em HTML simples.")
    tipo_item: str = Field(description="Tipo do item: 'Feature', 'User Story' ou 'Task'.")
    parent_id: Optional[int] = Field(default=None, description="ID do item pai para vínculo hierárquico.")
    criterios_aceite: Optional[str] = Field(default=None, description="Critérios de aceite em HTML (usado apenas para User Story).")

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if "properties" in data and "titulo" not in data:
            logger.warning("Detectado wrapper 'properties' — desembrulhando.")
            data = data["properties"]

        key_map = {
            "titulo": "titulo", "Titulo": "titulo", "title": "titulo", "Title": "titulo",
            "descricao": "descricao", "Descricao": "descricao", "Descrição": "descricao",
            "description": "descricao", "Description": "descricao",
            "tipo_item": "tipo_item", "TipoItem": "tipo_item", "tipoItem": "tipo_item",
            "tipo": "tipo_item", "Tipo": "tipo_item", "type": "tipo_item", "Type": "tipo_item",
            "parent_id": "parent_id", "ParentId": "parent_id", "parentId": "parent_id",
            "parent": "parent_id", "Parent": "parent_id",
            "criterios_aceite": "criterios_aceite", "CriteriosAceite": "criterios_aceite",
            "criteriosAceite": "criterios_aceite", "acceptance_criteria": "criterios_aceite",
            "AcceptanceCriteria": "criterios_aceite", "acceptanceCriteria": "criterios_aceite",
        }
        normalized = {}
        for key, value in data.items():
            mapped = key_map.get(key)
            if mapped:
                normalized[mapped] = value
            else:
                logger.warning("Campo desconhecido ignorado: '%s'", key)
        return normalized


class AzureDevOpsTool(BaseTool):
    name: str = "criar_work_item_azure"
    description: str = (
        "Cria um Work Item no Azure DevOps. "
        "Tipos válidos: 'Feature', 'User Story', 'Task'. "
        "Use parent_id para vincular ao item pai. "
        "Para User Story, use criterios_aceite para os critérios de aceite. "
        "IMPORTANTE: descricao e criterios_aceite devem ser HTML simples (use <b>, <br>, <ul>, <li>, <p>). "
        "NÃO use Markdown (##, **, ```). "
        "Passe os argumentos como JSON plano: {\"titulo\": ..., \"descricao\": ..., \"tipo_item\": ..., \"parent_id\": ..., \"criterios_aceite\": ...}"
    )
    args_schema: type[BaseModel] = WorkItemInput

    def _run(self, titulo: str, descricao: str, tipo_item: str, parent_id: Optional[int] = None, criterios_aceite: Optional[str] = None) -> str:
        org = os.environ["AZURE_ORG"]
        project = os.environ["AZURE_PROJECT"]
        pat = os.environ["AZURE_PAT"]

        if tipo_item not in VALID_WORK_ITEM_TYPES:
            return f"Erro: tipo_item '{tipo_item}' inválido. Use um de: {VALID_WORK_ITEM_TYPES}"

        # ── Validação de hierarquia ──
        expected_parent_type = PARENT_TYPE_MAP[tipo_item]

        if expected_parent_type is None and parent_id is not None:
            logger.warning("[TOOL] Feature não aceita parent_id. Ignorando parent_id=%s.", parent_id)
            parent_id = None

        if expected_parent_type is not None:
            valid_ids = registry.get_ids(expected_parent_type)

            if not valid_ids:
                return (
                    f"ERRO: Não é possível criar {tipo_item} — nenhum {expected_parent_type} foi criado ainda. "
                    f"Crie primeiro os itens do tipo '{expected_parent_type}'."
                )

            if parent_id is None or parent_id not in valid_ids:
                logger.warning(
                    "[TOOL] parent_id=%s inválido para %s. IDs válidos de %s: %s",
                    parent_id, tipo_item, expected_parent_type, valid_ids,
                )
                return (
                    f"ERRO: parent_id={parent_id} não é um {expected_parent_type} válido.\n"
                    f"{registry.format_valid_ids(expected_parent_type)}\n"
                    f"Escolha um desses IDs e tente novamente."
                )

        # ── Criação do Work Item ──
        project_encoded = requests.utils.quote(project)
        url = f"https://dev.azure.com/{org}/{project_encoded}/_apis/wit/workitems/${tipo_item}?api-version=7.1"

        payload = [
            {"op": "add", "path": "/fields/System.Title", "value": titulo},
            {"op": "add", "path": "/fields/System.Description", "value": descricao},
        ]

        if criterios_aceite and tipo_item == "User Story":
            payload.append(
                {"op": "add", "path": "/fields/Microsoft.VSTS.Common.AcceptanceCriteria", "value": criterios_aceite}
            )

        if parent_id:
            payload.append({
                "op": "add",
                "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": f"https://dev.azure.com/{org}/_apis/wit/workItems/{parent_id}",
                    "attributes": {"comment": "Vinculado por agente"},
                },
            })

        parent_info = f" (parent_id={parent_id})" if parent_id else ""
        logger.info("[TOOL] Criando %s: '%s'%s", tipo_item, titulo, parent_info)

        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json-patch+json"},
            auth=HTTPBasicAuth("", pat),
            timeout=30,
        )

        if response.status_code in (200, 201):
            item_id = response.json().get("id")
            registry.register(tipo_item, item_id, titulo, parent_id)
            logger.info("[TOOL] Criado — ID=%s, Tipo=%s, parent_id=%s", item_id, tipo_item, parent_id)
            return (
                f"SUCESSO: {tipo_item} criado com ID={item_id} (parent_id={parent_id}).\n"
                f"Título: {titulo}\n"
                f">>> Para criar itens filhos, use parent_id={item_id} <<<"
            )

        logger.error("[TOOL] Falha HTTP %s: %s", response.status_code, response.text[:500])
        return f"Erro ao criar Work Item (HTTP {response.status_code}): {response.text[:300]}"