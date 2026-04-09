from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_jaiminho_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Jaiminho — Desenvolvedor Sênior",
        goal="Criar exatamente 5 Tasks básicas de desenvolvimento para cada User Story no Azure DevOps.",
        backstory=(
            "Você é o Jaiminho, um desenvolvedor .NET sênior. Para cada User Story, você cria exatamente 5 Tasks, "
            "cada uma deve ser criada no Azure DevOps e vinculada à User Story correspondente usando parent_id. "
            "focadas no básico do desenvolvimento: implementação, testes unidade, configuração, "
            "integração e documentação/review. "
            "Cada Task deve ser vinculada à User Story correspondente usando parent_id."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=90,
    )


def create_tasks_task(agent: Agent, stories_task: Task) -> Task:
    return Task(
        description=(
            "Você recebeu uma lista de User Stories já criadas no Azure DevOps com seus IDs REAIS.\n"
            "ATENÇÃO CRÍTICA: O parent_id de cada Task DEVE ser o ID EXATO da User Story correspondente "
            "conforme listado no contexto recebido. NÃO invente IDs.\n\n"
            "Para CADA User Story, crie exatamente 5 Tasks usando 'criar_work_item_azure' com:\n"
            "1. Implementação principal\n"
            "2. Testes unitários\n"
            "3. Configuração (appsettings, variáveis, infra)\n"
            "4. Integração (mensageria, APIs externas, banco)\n"
            "5. Code review e documentação\n\n"
            "Parâmetros da ferramenta:\n"
            "- titulo: nome técnico da tarefa\n"
            "- descricao: detalhes de implementação\n"
            "- tipo_item: 'Task'\n"
            "- parent_id: ID EXATO da User Story (copiado do contexto)\n\n"
            "Retorne a lista EXATA no formato:\n"
            "Task 1: Título=<titulo>, ID=<id retornado>, parent_id=<id da US>\n"
        ),
        expected_output=(
            "Lista EXATA de Tasks criadas (5 por User Story). Cada uma com Título, ID REAL retornado, "
            "e parent_id REAL da User Story. Formato: 'Task N: Título=..., ID=..., parent_id=...'"
        ),
        agent=agent,
        context=[stories_task],
    )
