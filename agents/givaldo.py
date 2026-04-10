from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor

from agents._base import Agent
from tools import AzureDevOpsTool

_SYSTEM = (
    "Você é Givaldo — Tech Lead: ponte entre negócio e desenvolvimento. "
    "Nunca inventa requisitos — tudo vem da spec. "
    "Define contratos de API (RESTful: /api/v1/, verbos corretos, status codes) "
    "ou eventos (CloudEvents CNCF: specversion, type, source, id, time, data). "
    "Persona real sempre (nunca 'usuário genérico'). Título: frase curta em PT (não 'Como X quero Y'). "
    "Texto em português; código (endpoints, payloads) em inglês. "
    "HTML simples (<b><br><ul><li><p><pre><code>). Nunca Markdown. "
    "criterios_aceite separado da descricao. parent_id = ID exato da Feature."
)

_TASK_TEMPLATE = (
    "Contexto: lista de Features com IDs reais. Use o parent_id EXATO de cada Feature.\n\n"
    "Para cada Feature, crie 1-5 User Stories baseadas EXCLUSIVAMENTE na especificação abaixo:\n"
    "- titulo: frase curta em português (ex: 'Solicitar estorno de cobrança indevida')\n"
    "- descricao (HTML): 'Como [Persona real], quero [ação] para [valor]' "
    "+ RNs da spec + contrato API REST ou CloudEvents em <pre><code> quando aplicável\n"
    "- criterios_aceite (HTML): cenários Dado/Quando/Então em campo separado\n"
    "- tipo_item: User Story\n"
    "- parent_id: ID exato da Feature do contexto\n\n"
    "Formato de saída:\n"
    "US N: Título=<titulo>, ID=<id>, parent_id=<id da Feature>\n\n"
    "FEATURES CRIADAS:\n{features}\n\n"
    "ESPECIFICAÇÃO:\n{specification}"
)


def create_givaldo_agent(llm, tool: AzureDevOpsTool) -> Agent:
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
        max_iterations=25,
        handle_parsing_errors=True,
    )
    return Agent(role="Givaldo — Tech Lead", runner=executor)


def run_stories_task(agent: Agent, features_output: str, specification: str) -> str:
    result = agent.invoke({"input": _TASK_TEMPLATE.format(
        features=features_output,
        specification=specification,
    )})
    return result.get("output", str(result)) if isinstance(result, dict) else str(result)

