from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_mimi_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Mimi — Product Owner",
        goal="Agrupar a especificação em 2 a 3 grandes Features e criá-las no Azure DevOps.",
        backstory=(
            "Você é a Mimi, uma Product Owner técnica. A partir da documentação de arquitetura, "
            "você agrupa os requisitos em 2 a 3 Features de alto nível (grandes blocos funcionais) "
            "e cria cada uma no Azure DevOps usando a ferramenta disponível. "
            "REGRA: crie no mínimo 2 e no máximo 3 Features."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=8,
    )


def create_features_task(agent: Agent, architecture_task: Task) -> Task:
    return Task(
        description=(
            "Com base na arquitetura técnica recebida, agrupe os requisitos em 2 a 3 grandes Features.\n"
            "REGRA: crie no MÍNIMO 2 e no MÁXIMO 3 Features.\n"
            "Para cada Feature, use a ferramenta 'criar_work_item_azure' com:\n"
            "- titulo: nome descritivo da feature\n"
            "- descricao: descrição de negócio\n"
            "- tipo_item: 'Feature'\n\n"
            "APÓS CRIAR, anote o ID retornado pela ferramenta. "
            "Retorne a lista EXATA de Features criadas no formato:\n"
            "Feature 1: Título=<titulo>, ID=<id retornado>\n"
            "Feature 2: Título=<titulo>, ID=<id retornado>\n"
        ),
        expected_output=(
            "Lista EXATA de Features criadas, cada uma com Título e ID REAL retornado pela ferramenta. "
            "Formato: 'Feature N: Título=..., ID=...'. Apenas IDs que a ferramenta retornou."
        ),
        agent=agent,
        context=[architecture_task],
    )
