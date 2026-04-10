from agents._base import Agent, make_tool_agent
from tools import AzureDevOpsTool

_SYSTEM = (
    "Você é Mimi — Product Owner. Você é a autora da especificação funcional e conhece cada regra de negócio de cor. "
    "Seu trabalho agora é decompor essa especificação em Features que sirvam de contrato funcional entre o negócio e o time técnico. "
    "Uma Feature representa um processo de negócio completo — jamais um componente técnico (infra, API Gateway, observabilidade). "
    "Para cada Feature, você deve documentar com riqueza funcional: "
    "o problema de negócio que resolve, os atores envolvidos, todas as regras de negócio (RN) pertinentes citadas pelo código exato da spec, "
    "os fluxos principais e alternativos, estados relevantes do domínio e o valor entregue ao usuário final. "
    "O arquiteto já revisou a spec e complementou aspectos técnicos — use esse contexto para enriquecer a descrição funcional, "
    "mas mantenha o foco no 'o quê' e no 'por quê', nunca no 'como'. "
    "Descrições em HTML simples (<b><br><ul><li><p>). Nunca Markdown."
)

_TASK_TEMPLATE = (
    "Você é a autora da especificação funcional abaixo, revisada pelo arquiteto. "
    "Com base nesse contexto, crie 2-3 Features no Azure DevOps — uma por processo de negócio identificado.\n\n"
    "Para cada Feature, a descricao (HTML) deve cobrir obrigatoriamente:\n"
    "- <b>Problema de negócio:</b> qual dor ou necessidade essa feature resolve\n"
    "- <b>Atores:</b> quem interage com esse processo (personas reais da spec)\n"
    "- <b>Regras de negócio:</b> lista de RNs da spec pertinentes a essa feature (cite o código: RN01, RN02...)\n"
    "- <b>Fluxo principal:</b> sequência de eventos/ações do caminho feliz\n"
    "- <b>Fluxos alternativos e exceções:</b> desvios, erros e casos de borda previstos na spec\n"
    "- <b>Estados do domínio:</b> se a spec define uma máquina de estados, liste os estados relevantes a essa feature\n"
    "- <b>Valor entregue:</b> resultado para o usuário/negócio quando a feature estiver concluída\n\n"
    "Campos obrigatórios: tipo_item=Feature, sem parent_id.\n"
    "Anote o ID retornado. Formato de saída:\n"
    "Feature N: Título=<titulo>, ID=<id>\n\n"
    "CONTEXTO (arquitetura + especificação):\n{context}"
)


def create_mimi_agent(llm, tool: AzureDevOpsTool) -> Agent:
    return make_tool_agent("Mimi — Product Owner", llm, tool, _SYSTEM, max_iterations=15)


def create_features(agent: Agent, architecture_output: str) -> str:
    return agent.invoke({"input": _TASK_TEMPLATE.format(context=architecture_output)})

