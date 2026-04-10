from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor

from agents._base import Agent
from tools import AzureDevOpsTool

_SYSTEM = (
    "Você é Mimi — Product Owner focada em negócio, nunca em tecnologia. "
    "Extrai processos e regras funcionais da spec. "
    "Feature = processo de negócio completo (ex: 'Solicitação de Estorno'). "
    "Nunca cria Features técnicas (infra, observabilidade, API Gateway). "
    "Descrições em HTML simples (<b><br><ul><li><p>). Nunca Markdown."
)

_TASK_TEMPLATE = (
    "Com base no contexto abaixo (arquitetura + especificação), crie 2-3 Features no Azure DevOps.\n"
    "- Feature = processo de negócio (nunca componente técnico)\n"
    "- tipo_item: Feature (sem parent_id)\n"
    "- descricao em HTML (<b><ul><li><p>): problema de negócio, personas, RFs e RNs da spec\n\n"
    "Anote o ID retornado. Formato de saída:\n"
    "Feature N: Título=<titulo>, ID=<id>\n\n"
    "CONTEXTO:\n{context}"
)


def create_mimi_agent(llm, tool: AzureDevOpsTool) -> Agent:
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
        max_iterations=15,
        handle_parsing_errors=True,
    )
    return Agent(role="Mimi — Product Owner", runner=executor)


def run_features_task(agent: Agent, architecture_output: str) -> str:
    result = agent.invoke({"input": _TASK_TEMPLATE.format(context=architecture_output)})
    return result.get("output", str(result)) if isinstance(result, dict) else str(result)

