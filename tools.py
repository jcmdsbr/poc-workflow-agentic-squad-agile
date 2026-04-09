import os
import logging
import requests
from requests.auth import HTTPBasicAuth
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, model_validator
from typing import Any, Optional

logger = logging.getLogger(__name__)

VALID_WORK_ITEM_TYPES = {"Feature", "User Story", "Task"}


class WorkItemInput(BaseModel):
    titulo: str = Field(description="Título do Work Item.")
    descricao: str = Field(description="Descrição detalhada do Work Item.")
    tipo_item: str = Field(description="Tipo do item: 'Feature', 'User Story' ou 'Task'.")
    parent_id: Optional[int] = Field(default=None, description="ID do item pai para vínculo hierárquico.")

    @model_validator(mode="before")
    @classmethod
    def unwrap_properties(cls, data: Any) -> Any:
        """LLMs locais (ex: Llama) às vezes envolvem args em {"properties": {...}}.
        Detecta e desembrulha automaticamente."""
        if isinstance(data, dict) and "properties" in data and "titulo" not in data:
            logger.warning("Detectado wrapper 'properties' nos argumentos — desembrulhando automaticamente.")
            return data["properties"]
        return data


class AzureDevOpsTool(BaseTool):
    name: str = "criar_work_item_azure"
    description: str = (
        "Cria um Work Item no Azure DevOps. "
        "Tipos válidos: 'Feature', 'User Story', 'Task'. "
        "Use parent_id para vincular ao item pai. "
        "Passe os argumentos como JSON plano: {\"titulo\": ..., \"descricao\": ..., \"tipo_item\": ..., \"parent_id\": ...}"
    )
    args_schema: type[BaseModel] = WorkItemInput

    def _run(self, titulo: str, descricao: str, tipo_item: str, parent_id: Optional[int] = None) -> str:
        org = os.environ["AZURE_ORG"]
        project = os.environ["AZURE_PROJECT"]
        pat = os.environ["AZURE_PAT"]

        if tipo_item not in VALID_WORK_ITEM_TYPES:
            return f"Erro: tipo_item '{tipo_item}' inválido. Use um de: {VALID_WORK_ITEM_TYPES}"

        project_encoded = requests.utils.quote(project)
        url = f"https://dev.azure.com/{org}/{project_encoded}/_apis/wit/workitems/${tipo_item}?api-version=7.1"

        payload = [
            {"op": "add", "path": "/fields/System.Title", "value": titulo},
            {"op": "add", "path": "/fields/System.Description", "value": descricao},
        ]

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
        logger.debug("[TOOL] URL: %s", url)
        logger.debug("[TOOL] Payload: %s", payload)

        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json-patch+json"},
            auth=HTTPBasicAuth("", pat),
            timeout=30,
        )

        if response.status_code in (200, 201):
            item_id = response.json().get("id")
            logger.info("[TOOL] Criado com sucesso — ID: %s, Tipo: %s, Título: %s", item_id, tipo_item, titulo)
            return f"Work Item criado. ID: {item_id}, Tipo: {tipo_item}, Título: {titulo}"

        logger.error("[TOOL] Falha HTTP %s: %s", response.status_code, response.text[:500])
        return f"Erro ao criar Work Item (HTTP {response.status_code}): {response.text[:300]}"