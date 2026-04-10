from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_mimi_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Mimi — Product Owner",
        goal="Criar 2-3 Features no Azure DevOps representando os processos de negócio da especificação.",
        backstory=(
            "PO focada em negócio, nunca em tecnologia. Extrai processos e regras funcionais da spec. "
            "Feature = processo de negócio completo (ex: 'Solicitação de Estorno'). "
            "Nunca cria Features técnicas (infra, observabilidade, API Gateway). "
            "Descrições em HTML simples (<b><br><ul><li><p>). Nunca Markdown."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=15,
    )


def create_features_task(agent: Agent, architecture_task: Task) -> Task:
    return Task(
        description=(
            "Com base no contexto (arquitetura + especificação), crie 2-3 Features no Azure DevOps.\n"
            "- Feature = processo de negócio (nunca componente técnico)\n"
            "- tipo_item: Feature (sem parent_id)\n"
            "- descricao em HTML (<b><ul><li><p>): problema de negócio, personas, RFs e RNs da spec\n\n"
            "Anote o ID retornado. Formato de saída:\n"
            "Feature N: Título=<titulo>, ID=<id>"
        ),
        expected_output="Lista de Features: 'Feature N: Título=..., ID=...' com IDs reais retornados pela ferramenta.",
        agent=agent,
        context=[architecture_task],
    )
