import os
import logging
import requests
from requests.auth import HTTPBasicAuth
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

VALID_WORK_ITEM_TYPES = {"Feature", "User Story", "Task"}


class WorkItemInput(BaseModel):
    titulo: str = Field(description="Título do Work Item.")
    descricao: str = Field(description="Descrição detalhada do Work Item.")
    tipo_item: str = Field(description="Tipo do item: 'Feature', 'User Story' ou 'Task'.")
    parent_id: Optional[int] = Field(default=None, description="ID do item pai para vínculo hierárquico.")


class AzureDevOpsTool(BaseTool):
    name: str = "criar_work_item_azure"
    description: str = (
        "Cria um Work Item no Azure DevOps. "
        "Tipos válidos: 'Feature', 'User Story', 'Task'. "
        "Use parent_id para vincular ao item pai."
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

        logger.info("Criando %s: '%s'", tipo_item, titulo)
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json-patch+json"},
            auth=HTTPBasicAuth("", pat),
            timeout=30,
        )

        if response.status_code in (200, 201):
            item_id = response.json().get("id")
            logger.info("Criado com sucesso — ID: %s", item_id)
            return f"Work Item criado. ID: {item_id}, Tipo: {tipo_item}, Título: {titulo}"

        logger.error("Falha HTTP %s: %s", response.status_code, response.text)
        return f"Erro ao criar Work Item (HTTP {response.status_code}): {response.text}"