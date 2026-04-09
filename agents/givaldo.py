from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_givaldo_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Givaldo — Tech Lead",
        goal="Fatiar Features em User Stories no Azure DevOps.",
        backstory=(
            "Você é o Givaldo, um Tech Lead .NET. Você recebe Features e as decompõe em "
            "User Stories técnicas, criando cada uma no Azure DevOps vinculada no máximo 5 User Stories por Feature. "
            "Cada User Story deve ser vinculada à Feature correspondente usando o parent_id."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=25,
    )


def create_stories_task(agent: Agent, features_task: Task) -> Task:
    return Task(
        description=(
            "Você recebeu uma lista de Features já criadas no Azure DevOps com seus IDs REAIS.\n"
            "ATENÇÃO CRÍTICA: O parent_id de cada User Story DEVE ser o ID EXATO da Feature correspondente "
            "conforme listado no contexto recebido. NÃO invente IDs.\n\n"
            "Para cada Feature, crie no máximo 5 User Stories usando 'criar_work_item_azure' com:\n"
            "- titulo: nome descritivo\n"
            "- descricao: critérios de aceite e detalhes técnicos\n"
            "- tipo_item: 'User Story'\n"
            "- parent_id: ID EXATO da Feature (copiado do contexto)\n\n"
            "APÓS CRIAR, anote o ID retornado pela ferramenta. "
            "Retorne a lista EXATA no formato:\n"
            "US 1: Título=<titulo>, ID=<id retornado>, parent_id=<id da Feature>\n"
        ),
        expected_output=(
            "Lista EXATA de User Stories criadas. Cada uma com Título, ID REAL retornado pela ferramenta, "
            "e parent_id REAL da Feature. Formato: 'US N: Título=..., ID=..., parent_id=...'"
        ),
        agent=agent,
        context=[features_task],
    )
