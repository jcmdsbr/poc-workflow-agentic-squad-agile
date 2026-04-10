from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_jaiminho_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Jaiminho — Desenvolvedor .NET Sênior",
        goal="Criar exatamente 4 Tasks por User Story nos temas fixos: análise, desenvolvimento, integração e testes, testes de unidade.",
        backstory=(
            "Dev .NET sênior. Para cada US cria sempre exatamente 4 Tasks nessa ordem:\n"
            "1. Análise da User Story — levantamento técnico, impactos, decisões de design\n"
            "2. Desenvolvimento — implementação completa (domínio, aplicação, infraestrutura, API)\n"
            "3. Integração e Testes — testes de integração, contratos de API, smoke tests\n"
            "4. Testes de Unidade — cobertura unitária xUnit/NSubstitute para domínio e aplicação\n"
            "Título e descrição refletem o contexto específico da US. "
            "Texto em português; classes/interfaces em inglês em HTML. Nunca Markdown. "
            "parent_id = ID exato da User Story."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=120,
    )


def create_tasks_task(agent: Agent, stories_task: Task) -> Task:
    return Task(
        description=(
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
            "Task N: Título=<titulo>, ID=<id>, parent_id=<id da US>"
        ),
        expected_output="Lista de Tasks (4 por US): 'Task N: Título=..., ID=..., parent_id=...' com IDs reais.",
        agent=agent,
        context=[stories_task],
    )
