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
        num_ctx=LLM_NUM_CTX,
    )


def create_agents(llm: LLM, tool: AzureDevOpsTool):
    architect = Agent(
        role="Arquiteto de Software",
        goal="Analisar a especificação funcional e produzir um documento de arquitetura técnica conciso e prescritivo, sem exemplos de código.",
        backstory=(
            "Você é um arquiteto de sistemas pragmático especializado em .NET. "
            "Você orienta boas práticas como CQRS, FastEndpoints, Polly, OpenTelemetry e Kubernetes. "
            "REGRAS: "
            "1) Seja direto — máximo 400 palavras. "
            "2) Liste componentes, responsabilidades e tecnologias em bullet points. "
            "3) NÃO inclua exemplos de código, snippets ou trechos de configuração. "
            "4) Foque em decisões arquiteturais e padrões recomendados."
        ),
        verbose=True,
        allow_delegation=False,
        llm=llm,
        max_iter=3,
    )

    po = Agent(
        role="Product Owner",
        goal="Criar Features no Azure DevOps com base na arquitetura técnica.",
        backstory=(
            "Você é uma Product Owner técnica. A partir da documentação de arquitetura, "
            "você identifica de 1 a 5 Features de alto nível e cria cada uma no Azure DevOps "
            "usando a ferramenta disponível."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=5,
    )

    tech_lead = Agent(
        role="Tech Lead",
        goal="Fatiar Features em User Stories no Azure DevOps.",
        backstory=(
            "Você é um Tech Lead .NET. Você recebe Features e as decompõe em "
            "User Stories técnicas, criando cada uma no Azure DevOps vinculada "
            "à Feature correspondente usando o parent_id."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=10,
    )

    developer = Agent(
        role="Desenvolvedor Sênior",
        goal="Criar Tasks técnicas detalhadas a partir das User Stories no Azure DevOps.",
        backstory=(
            "Você é um desenvolvedor .NET sênior. Você decompõe User Stories em "
            "Tasks de implementação com detalhes técnicos (endpoints, configs, testes), "
            "criando cada Task no Azure DevOps vinculada à User Story correspondente."
        ),
        verbose=True,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=15,
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
            "Com base na arquitetura técnica recebida, identifique e crie Features no Azure DevOps.\n"
            "Para cada Feature, use a ferramenta 'criar_work_item_azure' com:\n"
            "- titulo: nome descritivo da feature\n"
            "- descricao: descrição de negócio\n"
            "- tipo_item: 'Feature'\n\n"
            "Retorne a lista de Features criadas com seus IDs."
        ),
        expected_output="Lista com título e ID de cada Feature criada.",
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
            "Decomponha cada User Story em Tasks de implementação no Azure DevOps.\n"
            "Para cada Task, use a ferramenta 'criar_work_item_azure' com:\n"
            "- titulo: nome técnico da tarefa\n"
            "- descricao: detalhes de implementação (endpoints, configs, testes)\n"
            "- tipo_item: 'Task'\n"
            "- parent_id: ID da User Story correspondente\n\n"
            "Retorne a lista completa de Tasks com seus IDs e parent_ids."
        ),
        expected_output="Lista com título, ID e parent_id de cada Task criada.",
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
        verbose=True,
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
