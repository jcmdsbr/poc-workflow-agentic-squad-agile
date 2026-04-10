from crewai import Agent, Task, LLM


def create_bic_agent(llm: LLM) -> Agent:
    return Agent(
        role="Bic — Arquiteto de Software",
        goal=(
            "Analisar a especificação funcional, complementá-la com requisitos técnicos "
            "(observabilidade, resiliência, segurança) e produzir um documento de arquitetura "
            "conciso que sirva de base para PO e Tech Lead."
        ),
        backstory=(
            "Você é o Bic, arquiteto .NET sênior. Seu papel é ser o PRIMEIRO a ler a especificação "
            "e COMPLEMENTÁ-LA com tudo que está faltando do ponto de vista técnico antes que "
            "o PO e o Tech Lead comecem a trabalhar.\n\n"
            "Você identifica na especificação o que está explícito E o que está faltando:\n"
            "- Observabilidade (logs, traces, métricas, health checks)\n"
            "- Resiliência (retries, circuit breaker, fallback, timeout)\n"
            "- Performance (caching, paginação, lazy loading)\n"
            "- Integrações (APIs externas, mensageria, eventos)\n\n"
            "Esses complementos técnicos entram no seu documento de arquitetura para que os "
            "agentes seguintes saibam o que implementar.\n\n"
            "REGRAS: máximo 500 palavras, Markdown, sem código, sem snippets."
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
            "em Markdown com no máximo 500 palavras.\n\n"
            "Seu documento COMPLEMENTA a especificação com requisitos técnicos que estão "
            "faltando ou implícitos. O PO e Tech Lead vão usar este documento.\n\n"
            "## Estrutura obrigatória:\n"
            "### 1. Visão Geral\n"
            "- O que o sistema faz em 2 frases.\n\n"
            "### 2. Componentes\n"
            "- Lista de componentes com responsabilidade de cada um (1 linha por componente).\n\n"
            "### 3. Decisões e Trade-offs\n"
            "- Padrões escolhidos e por quê.\n\n"
            "### 4. Stack\n"
            "- Frameworks e libs recomendados.\n\n"
            "### 5. Requisitos Técnicos Complementares\n"
            "Liste aqui tudo o que a especificação NÃO menciona mas que é necessário:\n"
            "- Observabilidade (OpenTelemetry, health checks, logging estruturado)\n"
            "- Resiliência (Polly — retries, circuit breaker, fallback)\n"
            "- Segurança (JWT, validação de input, rate limiting)\n"
            "- Performance (caching, paginação)\n"
            "- Comunicação assíncrona (eventos, mensageria)\n\n"
            "REGRAS: máximo 500 palavras, sem código, sem configurações.\n\n"
            f"ESPECIFICAÇÃO FUNCIONAL:\n\n{specification}"
        ),
        expected_output=(
            "Documento Markdown de arquitetura (máx 500 palavras) com: "
            "Visão Geral, Componentes, Decisões, Stack e Requisitos Técnicos Complementares. Sem código."
        ),
        agent=agent,
    )
