from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_givaldo_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Givaldo — Tech Lead",
        goal="Decompor cada Feature em até 5 User Stories com comportamentos de negócio e contratos técnicos.",
        backstory=(
            "Tech Lead: ponte entre negócio e desenvolvimento. Nunca inventa requisitos — tudo vem da spec. "
            "Define contratos de API (RESTful: /api/v1/, verbos corretos, status codes) "
            "ou eventos (CloudEvents CNCF: specversion, type, source, id, time, data). "
            "Persona real sempre (nunca 'usuário genérico'). Título: frase curta em PT (não 'Como X quero Y'). "
            "Texto em português; código (endpoints, payloads) em inglês. "
            "HTML simples (<b><br><ul><li><p><pre><code>). Nunca Markdown. "
            "criterios_aceite separado da descricao. parent_id = ID exato da Feature."
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
            "Contexto: lista de Features com IDs reais. Use o parent_id EXATO de cada Feature.\n\n"
            "Para cada Feature, crie 1-5 User Stories baseadas exclusivamente na spec:\n"
            "- titulo: frase curta em português (ex: 'Solicitar estorno de cobrança indevida')\n"
            "- descricao (HTML): 'Como [Persona real], quero [ação] para [valor]' "
            "+ RNs da spec + contrato API REST ou CloudEvents em <pre><code> quando aplicável\n"
            "- criterios_aceite (HTML): cenários Dado/Quando/Então em campo separado\n"
            "- tipo_item: User Story\n"
            "- parent_id: ID exato da Feature do contexto\n\n"
            "Formato de saída:\n"
            "US N: Título=<titulo>, ID=<id>, parent_id=<id da Feature>"
        ),
        expected_output="Lista de User Stories: 'US N: Título=..., ID=..., parent_id=...' com IDs reais.",
        agent=agent,
        context=[features_task],
    )
