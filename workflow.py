import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from crewai import LLM
from tools import AzureDevOpsTool

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("workflow")

# ==========================================
# CONFIGURAÇÃO
# ==========================================

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "ollama/llama3.1")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "32768"))


def validate_config():
    required = ["AZURE_ORG", "AZURE_PROJECT", "AZURE_PAT"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        sys.exit(
            f"Variáveis de ambiente obrigatórias não definidas: {', '.join(missing)}\n"
            f"Copie .env.example para .env e preencha os valores."
        )


def load_specification(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    sys.exit(
        "Uso: python workflow.py <arquivo_especificacao.md>\n"
        " ou: cat spec.md | python workflow.py"
    )


# ==========================================
# AGENTES
# ==========================================

def create_llm():
    return LLM(
        model=LLM_MODEL,
        base_url=OLLAMA_BASE,
        extra_body={"num_ctx": LLM_NUM_CTX},
    )


def create_agents(llm: LLM, tool: AzureDevOpsTool):
    architect = Agent(
        role="Bic — Arquiteto de Software",
        goal="Analisar a especificação funcional e produzir um documento de arquitetura técnica conciso e prescritivo, sem exemplos de código.",
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

    po = Agent(
        role="Mimi — Product Owner",
        goal="Agrupar a especificação em 2 a 3 grandes Features e criá-las no Azure DevOps.",
        backstory=(
            "Você é a Mimi, uma Product Owner técnica. A partir da documentação de arquitetura, "
            "você agrupa os requisitos em 2 a 3 Features de alto nível (grandes blocos funcionais) "
            "e cria cada uma no Azure DevOps usando a ferramenta disponível. "
            "REGRA: crie no mínimo 2 e no máximo 3 Features."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=8,
    )

    tech_lead = Agent(
        role="Givaldo — Tech Lead",
        goal="Fatiar Features em User Stories no Azure DevOps.",
        backstory=(
            "Você é o Givaldo, um Tech Lead .NET. Você recebe Features e as decompõe em "
            "User Stories técnicas, criando cada uma no Azure DevOps vinculada no máximo 5 User Stories por Feature. "
            "Cada User Story deve ser vinculada à Feature correspondente usando o parent_id."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=25,
    )

    developer = Agent(
        role="Jaiminho — Desenvolvedor Sênior",
        goal="Criar exatamente 5 Tasks básicas de desenvolvimento para cada User Story no Azure DevOps.",
        backstory=(
            "Você é o Jaiminho, um desenvolvedor .NET sênior. Para cada User Story, você cria exatamente 5 Tasks, "
            "cada uma deve ser criada no Azure DevOps e vinculada à User Story correspondente usando parent_id. "
            "focadas no básico do desenvolvimento: implementação, testes unidade, configuração, "
            "integração e documentação/review. "
            "Cada Task deve ser vinculada à User Story correspondente usando parent_id."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=90,
    )

    return architect, po, tech_lead, developer


# ==========================================
# TAREFAS (com encadeamento via context)
# ==========================================

def create_tasks(agents, specification: str):
    architect, po, tech_lead, developer = agents

    architecture_task = Task(
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
        agent=architect,
    )

    features_task = Task(
        description=(
            "Com base na arquitetura técnica recebida, agrupe os requisitos em 2 a 3 grandes Features.\n"
            "REGRA: crie no MÍNIMO 2 e no MÁXIMO 3 Features.\n"
            "Para cada Feature, use a ferramenta 'criar_work_item_azure' com:\n"
            "- titulo: nome descritivo da feature\n"
            "- descricao: descrição de negócio\n"
            "- tipo_item: 'Feature'\n\n"
            "Retorne a lista de Features criadas com seus IDs."
        ),
        expected_output="Lista com título e ID de cada Feature criada (2 a 3 Features).",
        agent=po,
        context=[architecture_task],
    )

    stories_task = Task(
        description=(
            "Decomponha cada Feature em User Stories técnicas no Azure DevOps.\n"
            "Para cada User Story, use a ferramenta 'criar_work_item_azure' com:\n"
            "- titulo: nome descritivo\n"
            "- descricao: critérios de aceite e detalhes técnicos\n"
            "- tipo_item: 'User Story'\n"
            "- parent_id: ID da Feature correspondente\n\n"
            "Retorne a lista de User Stories com seus IDs e parent_ids."
        ),
        expected_output="Lista com título, ID e parent_id de cada User Story criada.",
        agent=tech_lead,
        context=[features_task],
    )

    tasks_task = Task(
        description=(
            "Para CADA User Story, crie exatamente 5 Tasks básicas de desenvolvimento no Azure DevOps.\n"
            "As 5 Tasks por User Story devem cobrir:\n"
            "1. Implementação principal (endpoint, serviço ou job)\n"
            "2. Testes unitários\n"
            "3. Configuração (appsettings, variáveis, infra)\n"
            "4. Integração (mensageria, APIs externas, banco)\n"
            "5. Code review e documentação\n\n"
            "Para cada Task, use a ferramenta 'criar_work_item_azure' com:\n"
            "- titulo: nome técnico da tarefa\n"
            "- descricao: detalhes de implementação\n"
            "- tipo_item: 'Task'\n"
            "- parent_id: ID da User Story correspondente\n\n"
            "Retorne a lista completa de Tasks com seus IDs e parent_ids."
        ),
        expected_output="Lista com título, ID e parent_id de cada Task criada (5 por User Story).",
        agent=developer,
        context=[stories_task],
    )

    return [architecture_task, features_task, stories_task, tasks_task]


# ==========================================
# EXECUÇÃO
# ==========================================

def main():
    validate_config()

    spec_path = sys.argv[1] if len(sys.argv) > 1 else None
    specification = load_specification(spec_path)

    logger.info("=" * 60)
    logger.info("PIPELINE DE AGENTES — INÍCIO")
    logger.info("=" * 60)
    logger.info("Modelo LLM: %s (ctx=%d)", LLM_MODEL, LLM_NUM_CTX)
    logger.info("Ollama: %s", OLLAMA_BASE)
    logger.info("Especificação: %s (%d caracteres)", spec_path or "stdin", len(specification))
    logger.info("Azure DevOps: org=%s, project=%s", os.getenv("AZURE_ORG"), os.getenv("AZURE_PROJECT"))
    logger.info("-" * 60)

    llm = create_llm()
    tool = AzureDevOpsTool()
    agents = create_agents(llm, tool)
    tasks = create_tasks(agents, specification)

    agent_names = [a.role for a in agents]
    for i, (task, name) in enumerate(zip(tasks, agent_names), 1):
        logger.info("Etapa %d: [%s] → %s", i, name, task.expected_output)

    logger.info("-" * 60)

    crew = Crew(
        agents=list(agents),
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )

    start = datetime.now(timezone.utc)
    result = crew.kickoff()
    elapsed = datetime.now(timezone.utc) - start

    logger.info("=" * 60)
    logger.info("PIPELINE CONCLUÍDO em %s", str(elapsed).split(".")[0])
    logger.info("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
