from agents._base import Agent, make_tool_agent
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
    return make_tool_agent("Mimi — Product Owner", llm, tool, _SYSTEM, max_iterations=15)


def create_features(agent: Agent, architecture_output: str) -> str:
    return agent.invoke({"input": _TASK_TEMPLATE.format(context=architecture_output)})

