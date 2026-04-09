from crewai import Agent, Task, LLM


def create_bic_agent(llm: LLM) -> Agent:
    return Agent(
        role="Bic — Arquiteto de Software",
        goal=(
            "Analisar a especificação funcional e produzir um documento de "
            "arquitetura técnica conciso e prescritivo, sem exemplos de código."
        ),
        backstory=(
            "Você é o Bic, um arquiteto de sistemas pragmático especializado em .NET. "
            "Você orienta boas práticas como CQRS, FastEndpoints, Polly, OpenTelemetry e Kubernetes. "
            "REGRAS: "
            "1) Seja direto — máximo 400 palavras. "
            "2) Liste componentes, responsabilidades e tecnologias em bullet points. "
            "3) NÃO inclua exemplos de código, snippets ou trechos de configuração. "
            "4) Foque em decisões arquiteturais e padrões recomendados."
        ),
        verbose=False,
        allow_delegation=False,
        llm=llm,
        max_iter=3,
    )


def create_architecture_task(agent: Agent, specification: str) -> Task:
    return Task(
        description=(
            "Analise a especificação funcional abaixo e gere um documento de arquitetura técnica "
            "CONCISO em Markdown seguindo estas regras:\n"
            "- Máximo 400 palavras\n"
            "- Liste componentes, responsabilidades e tecnologias em bullet points\n"
            "- Indique padrões e boas práticas recomendadas (CQRS, Polly, OpenTelemetry, etc)\n"
            "- NÃO inclua exemplos de código, snippets ou trechos de configuração\n"
            "- Foque em decisões arquiteturais e justificativas\n\n"
            f"ESPECIFICAÇÃO:\n{specification}"
        ),
        expected_output=(
            "Documento Markdown conciso (máximo 400 palavras) com bullet points: "
            "componentes, tecnologias, padrões recomendados e responsabilidades. Sem código."
        ),
        agent=agent,
    )
