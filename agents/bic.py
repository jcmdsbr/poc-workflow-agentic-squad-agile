from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from agents._base import Agent

_SYSTEM = (
    "Você é Bic — Arquiteto .NET sênior. Lê a spec e adiciona o que está faltando: "
    "observabilidade (OpenTelemetry, health checks, logs estruturados), "
    "resiliência (Polly — retries, circuit breaker), segurança (JWT, rate limiting), "
    "performance (caching, paginação) e mensageria. Saída: Markdown, máx 500 palavras, sem código."
)

_TASK_TEMPLATE = (
    "Produza um Documento de Arquitetura em Markdown (máx 500 palavras, sem código) com:\n"
    "1. Visão Geral (2 frases)\n"
    "2. Componentes (1 linha cada + responsabilidade)\n"
    "3. Decisões e Trade-offs\n"
    "4. Stack (frameworks e libs)\n"
    "5. Requisitos Técnicos Complementares (o que a spec não menciona: "
    "observabilidade, resiliência, segurança, performance, mensageria)\n\n"
    "ESPECIFICAÇÃO:\n\n{specification}"
)


def create_bic_agent(llm) -> Agent:
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", "{input}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return Agent(role="Bic — Arquiteto .NET", runner=chain)


def generate_architecture(agent: Agent, specification: str) -> str:
    return agent.invoke({"input": _TASK_TEMPLATE.format(specification=specification)})

