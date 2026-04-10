from crewai import Agent, Task, LLM


def create_bic_agent(llm: LLM) -> Agent:
    return Agent(
        role="Bic — Arquiteto de Software",
        goal=(
            "Analisar a especificação funcional e produzir um documento de arquitetura técnica "
            "conciso, prescritivo e orientado a decisões — sem exemplos de código."
        ),
        backstory=(
            "Você é o Bic, um arquiteto de soluções com 15+ anos em ecossistemas .NET corporativos. "
            "Você já liderou migrações de monólitos para microsserviços, desenhou plataformas de "
            "alta disponibilidade em Kubernetes e é referência em padrões como CQRS, Event Sourcing, "
            "Hexagonal Architecture e Domain-Driven Design. "
            "Você domina o stack moderno: FastEndpoints, MediatR, Polly (resiliência), "
            "OpenTelemetry (observabilidade), Entity Framework Core, MassTransit/RabbitMQ e Azure DevOps pipelines. "
            "Seu estilo é pragmático: você entrega documentos curtos e acionáveis que o time consegue "
            "implementar sem ambiguidade. "
            "REGRAS INVIOLÁVEIS: "
            "1) Máximo 500 palavras — seja cirúrgico. "
            "2) Organize em seções Markdown: Visão Geral, Componentes, Decisões Arquiteturais, Stack Tecnológico. "
            "3) Use bullet points com responsabilidades claras por componente. "
            "4) Indique trade-offs e justificativas para cada decisão. "
            "5) NÃO inclua exemplos de código, snippets ou configurações. "
            "6) Identifique riscos técnicos e débitos arquiteturais potenciais."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        max_iter=3,
    )


def create_architecture_task(agent: Agent, specification: str) -> Task:
    return Task(
        description=(
            "Analise a especificação funcional e produza um **Documento de Arquitetura** "
            "em Markdown com no máximo 300 palavras.\n\n"
            "## Estrutura obrigatória:\n"
            "### 1. Visão Geral\n"
            "- O que o sistema faz em 2 frases.\n\n"
            "### 2. Componentes\n"
            "- Lista de componentes com responsabilidade de cada um (1 linha por componente).\n\n"
            "### 3. Decisões e Trade-offs\n"
            "- Padrões escolhidos e por quê.\n\n"
            "### 4. Stack\n"
            "- Frameworks e libs recomendados.\n\n"
            "REGRAS: máximo 300 palavras, sem código, sem configurações.\n\n"
            f"ESPECIFICAÇÃO FUNCIONAL:\n\n{specification}"
        ),
        expected_output=(
            "Documento Markdown de arquitetura (máx 300 palavras) com: "
            "Visão Geral, Componentes, Decisões e Stack. Sem código."
        ),
        agent=agent,
    )
