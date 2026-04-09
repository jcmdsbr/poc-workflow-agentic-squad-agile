import os
import requests
from requests.auth import HTTPBasicAuth
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional

# 1. O Schema fortemente tipado
class AzureWorkItemSchema(BaseModel):
    titulo: str = Field(..., description="O título exato do Work Item.")
    descricao: str = Field(..., description="A descrição detalhada da tarefa ou negócio.")
    tipo_item: str = Field(..., description="Use EXATAMENTE um destes: 'Feature', 'User Story' ou 'Task'.")
    parent_id: Optional[int] = Field(None, description="ID numérico do item pai. Deixe nulo se não houver.")

# 2. A Ferramenta Blindada
class FerramentaAzureDevOps(BaseTool):
    name: str = "criar_work_item_azure"
    description: str = """
    Cria Work Items no board do Azure DevOps.
    
    REGRA DE FORMATAÇÃO JSON OBRIGATÓRIA:
    Você DEVE passar os argumentos como um JSON plano (flat). 
    NUNCA envolva os argumentos dentro de uma chave chamada "properties".
    
    Exemplo CORRETO de chamada:
    {"titulo": "Criar Banco", "descricao": "Detalhes...", "tipo_item": "Task", "parent_id": 123}
    
    Exemplo ERRADO (NÃO FAÇA ISSO):
    {"properties": {"titulo": "Criar Banco", ...}}
    """
    args_schema: type[BaseModel] = AzureWorkItemSchema

    def _run(self, titulo: str, descricao: str, tipo_item: str, parent_id: int = None) -> str:
        org = os.getenv("AZURE_ORG")
        project = os.getenv("AZURE_PROJECT")
        pat = os.getenv("AZURE_PAT")
        
        project_encoded = requests.utils.quote(project)
        url = f"https://dev.azure.com/{org}/{project_encoded}/_apis/wit/workitems/${tipo_item}?api-version=7.1"
        
        payload = [
            {"op": "add", "path": "/fields/System.Title", "value": titulo},
            {"op": "add", "path": "/fields/System.Description", "value": descricao}
        ]
        
        if parent_id:
            url_parent = f"https://dev.azure.com/{org}/_apis/wit/workItems/{parent_id}"
            payload.append({
                "op": "add", "path": "/relations/-",
                "value": {
                    "rel": "System.LinkTypes.Hierarchy-Reverse",
                    "url": url_parent,
                    "attributes": {"comment": "Vinculado automaticamente"}
                }
            })
            
        headers = {"Content-Type": "application/json-patch+json"}
        auth = HTTPBasicAuth('', pat)
        
        try:
            print(f"\n[📡 SYSTEM LOG] Criando {tipo_item}: '{titulo[:30]}...'")
            response = requests.post(url, json=payload, headers=headers, auth=auth)
            
            if response.status_code in (200, 201):
                dados = response.json()
                sucesso_msg = f"SUCESSO! ID gerado: {dados.get('id')}"
                print(f"[✅ SYSTEM LOG] {sucesso_msg}")
                return sucesso_msg
            else:
                erro_msg = f"API retornou status {response.status_code}: {response.text}"
                print(f"[❌ SYSTEM LOG] {erro_msg}")
                raise Exception(f"FALHA NA INTEGRAÇÃO. O JSON ESTAVA INCORRETO: {erro_msg}")
                
        except Exception as e:
            raise Exception(f"ERRO DE EXECUÇÃO DA FERRAMENTA: {str(e)}")