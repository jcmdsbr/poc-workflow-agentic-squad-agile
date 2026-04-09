from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_mimi_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Mimi — Product Owner",
        goal=(
            "Traduzir a arquitetura técnica em 2 a 3 Features de alto nível no Azure DevOps, "
            "cada uma representando um grande bloco de valor entregável ao negócio."
        ),
        backstory=(
            "Você é a Mimi, uma Product Owner com 12+ anos de experiência em times .NET corporativos "
            "e certificação CSPO (Certified Scrum Product Owner). "
            "Você domina a arte de traduzir documentação técnica em itens de backlog orientados a valor. "
            "Seu diferencial é a capacidade de negociação: você sabe agrupar requisitos em Features "
            "que representem incrementos de valor entregáveis e mensuráveis, evitando Epics disfarçados. "
            "Você entende o ecossistema .NET e sabe diferenciar Features de infraestrutura "
            "(ex: observabilidade, resiliência) de Features de negócio (ex: fluxo de pagamento). "
            "Cada Feature que você cria tem uma descrição rica em Markdown com: "
            "objetivo de negócio, personas impactadas, métricas de sucesso e dependências técnicas. "
            "REGRAS INVIOLÁVEIS: "
            "1) Crie no MÍNIMO 2 e no MÁXIMO 3 Features. "
            "2) A descrição de cada Feature deve estar em Markdown formatado. "
            "3) Foque em valor entregável, não em tarefas técnicas."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=8,
    )


def create_features_task(agent: Agent, architecture_task: Task) -> Task:
    return Task(
        description=(
            "Com base na arquitetura técnica recebida, agrupe os requisitos em **2 a 3 grandes Features**.\n\n"
            "## Regras para criação de Features\n"
            "- Cada Feature deve representar um **bloco de valor entregável** ao negócio.\n"
            "- MÍNIMO 2, MÁXIMO 3 Features.\n\n"
            "## Formato da descrição (campo `descricao`)\n"
            "A descrição de cada Feature DEVE ser em Markdown com esta estrutura:\n\n"
            "```\n"
            "## Objetivo\n"
            "Descrição clara do valor de negócio que esta Feature entrega.\n\n"
            "## Personas Impactadas\n"
            "- **Persona 1**: como é impactada\n"
            "- **Persona 2**: como é impactada\n\n"
            "## Escopo Funcional\n"
            "- Capacidade 1\n"
            "- Capacidade 2\n\n"
            "## Dependências Técnicas\n"
            "- Dependência relevante\n"
            "```\n\n"
            "## Como usar a ferramenta\n"
            "Para cada Feature, use `criar_work_item_azure` com:\n"
            "- **titulo**: nome descritivo e orientado a valor (ex: 'Plataforma de Processamento de Pagamentos')\n"
            "- **descricao**: texto Markdown completo conforme template acima\n"
            "- **tipo_item**: `Feature`\n\n"
            "APÓS CRIAR, anote o ID retornado. Retorne a lista EXATA no formato:\n"
            "Feature 1: Título=<titulo>, ID=<id retornado>\n"
            "Feature 2: Título=<titulo>, ID=<id retornado>\n"
        ),
        expected_output=(
            "Lista EXATA de Features criadas, cada uma com Título e ID REAL retornado pela ferramenta. "
            "Formato: 'Feature N: Título=..., ID=...'. Apenas IDs que a ferramenta retornou."
        ),
        agent=agent,
        context=[architecture_task],
    )
