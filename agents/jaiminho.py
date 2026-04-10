from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_jaiminho_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Jaiminho — Desenvolvedor .NET Sênior",
        goal="Criar exatamente 5 Tasks técnicas por User Story cobrindo todas as camadas da aplicação .NET.",
        backstory=(
            "Dev .NET sênior. Decompõe cada US em 5 Tasks pelas camadas:\n"
            "1. Infrastructure: migrations EF Core, repositórios, DbContext\n"
            "2. Domain/Application: entidades, Value Objects, Handlers MediatR, DTOs, AutoMapper\n"
            "3. Presentation: endpoints FastEndpoints/Controller, JWT, Swagger\n"
            "4. Quality: testes unitários xUnit/NSubstitute + testes de integração\n"
            "5. Observabilidade: OpenTelemetry, health check, logging estruturado, PR review\n"
            "Texto em português; classes/interfaces em inglês. HTML simples. Nunca Markdown. "
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
            "Para cada User Story, crie EXATAMENTE 5 Tasks (uma por camada):\n"
            "1. Infrastructure — migrations EF Core, repositório, DbContext\n"
            "2. Domain/Application — entidades, Handlers MediatR, DTOs, AutoMapper\n"
            "3. Presentation/API — endpoint, JWT, Swagger\n"
            "4. Quality — testes unitários xUnit + testes de integração\n"
            "5. Observabilidade — OpenTelemetry, health check, logging, PR review\n\n"
            "Para cada Task:\n"
            "- titulo: nome técnico em português\n"
            "- descricao (HTML): objetivo, itens a implementar, classes/interfaces em inglês em <pre><code>, camada, DoD\n"
            "- tipo_item: Task\n"
            "- parent_id: ID exato da User Story\n\n"
            "Formato de saída:\n"
            "Task N: Título=<titulo>, ID=<id>, parent_id=<id da US>"
        ),
        expected_output="Lista de Tasks (5 por US): 'Task N: Título=..., ID=..., parent_id=...' com IDs reais.",
        agent=agent,
        context=[stories_task],
    )
