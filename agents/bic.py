from crewai import Agent, Task, LLM


def create_bic_agent(llm: LLM) -> Agent:
    return Agent(
        role="Bic — Arquiteto .NET",
        goal="Complementar a especificação com requisitos técnicos e produzir documento de arquitetura para PO e Tech Lead.",
        backstory=(
            "Arquiteto .NET sênior. Lê a spec e adiciona o que está faltando: "
            "observabilidade (OpenTelemetry, health checks, logs estruturados), "
            "resiliência (Polly — retries, circuit breaker), segurança (JWT, rate limiting), "
            "performance (caching, paginação) e mensageria. Saída: Markdown, máx 500 palavras, sem código."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        max_iter=3,
    )


def create_architecture_task(agent: Agent, specification: str) -> Task:
    return Task(
        description=(
            "Produza um Documento de Arquitetura em Markdown (máx 500 palavras, sem código) com:\n"
            "1. Visão Geral (2 frases)\n"
            "2. Componentes (1 linha cada + responsabilidade)\n"
            "3. Decisões e Trade-offs\n"
            "4. Stack (frameworks e libs)\n"
            "5. Requisitos Técnicos Complementares (o que a spec não menciona: "
            "observabilidade, resiliência, segurança, performance, mensageria)\n\n"
            f"ESPECIFICAÇÃO:\n\n{specification}"
        ),
        expected_output=(
            "Documento Markdown (máx 500 palavras): Visão Geral, Componentes, Decisões, Stack, Requisitos Complementares."
        ),
        agent=agent,
    )
