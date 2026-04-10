from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor

from agents._base import Agent
from tools import AzureDevOpsTool

_SYSTEM = (
    "Você é Jaiminho — Desenvolvedor .NET Sênior. Para cada US cria sempre exatamente 4 Tasks nessa ordem:\n"
    "1. Análise da User Story — levantamento técnico, impactos, decisões de design\n"
    "2. Desenvolvimento — implementação completa (domínio, aplicação, infraestrutura, API)\n"
    "3. Integração e Testes — testes de integração, contratos de API, smoke tests\n"
    "4. Testes de Unidade — cobertura unitária xUnit/NSubstitute para domínio e aplicação\n"
    "Título e descrição refletem o contexto específico da US. "
    "Texto em português; classes/interfaces em inglês em HTML. Nunca Markdown. "
    "parent_id = ID exato da User Story."
)

_TASK_TEMPLATE = (
    "Contexto: lista de User Stories com IDs reais. Use o parent_id EXATO de cada US.\n\n"
    "Para cada User Story, crie EXATAMENTE 4 Tasks nessa ordem e com esses temas:\n"
    "1. Análise da User Story — levantamento técnico do que a US exige: "
    "impactos no domínio, decisões de design, dependências, pontos de atenção\n"
    "2. Desenvolvimento — implementação completa da US: entidades, handlers, "
    "repositórios, endpoint, migrations e qualquer lógica de negócio necessária\n"
    "3. Integração e Testes — testes de integração end-to-end, validação de contrato "
    "de API, smoke tests e testes de cenários com dependências reais\n"
    "4. Testes de Unidade — cobertura unitária xUnit/NSubstitute para domínio e "
    "camada de aplicação (mocks de repositórios e dependências externas)\n\n"
    "Título e descrição de cada Task devem refletir o contexto específico da US (não ser genéricos).\n"
    "Para cada Task:\n"
    "- titulo: tema fixo + contexto da US (ex: 'Desenvolvimento — endpoint de solicitação de estorno')\n"
    "- descricao (HTML): objetivo, o que fazer, classes/interfaces relevantes em <pre><code>\n"
    "- tipo_item: Task\n"
    "- parent_id: ID exato da User Story\n\n"
    "Formato de saída:\n"
    "Task N: Título=<titulo>, ID=<id>, parent_id=<id da US>\n\n"
    "USER STORIES CRIADAS:\n{context}"
)


def create_jaiminho_agent(llm, tool: AzureDevOpsTool) -> Agent:
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    lc_agent = create_tool_calling_agent(llm, [tool], prompt)
    executor = AgentExecutor(
        agent=lc_agent,
        tools=[tool],
        verbose=False,
        max_iterations=120,
        handle_parsing_errors=True,
    )
    return Agent(role="Jaiminho — Desenvolvedor .NET Sênior", runner=executor)


def run_tasks_task(agent: Agent, stories_output: str) -> str:
    result = agent.invoke({"input": _TASK_TEMPLATE.format(context=stories_output)})
    return result.get("output", str(result)) if isinstance(result, dict) else str(result)

