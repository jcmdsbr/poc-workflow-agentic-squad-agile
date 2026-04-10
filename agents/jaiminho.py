from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_jaiminho_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Jaiminho — Desenvolvedor Sênior",
        goal=(
            "Criar exatamente 5 Tasks técnicas de engenharia .NET para cada User Story, "
            "cobrindo todas as camadas da aplicação com foco em testabilidade e qualidade."
        ),
        backstory=(
            "Você é o Jaiminho, um desenvolvedor .NET sênior com 10+ anos de experiência em "
            "times ágeis corporativos. Você entende profundamente a Definition of Done e sabe "
            "que uma task não está pronta se não for testável.\n\n"
            "Sua especialidade é decompor User Stories no 'Como' técnico, atacando cada camada "
            "da arquitetura .NET:\n"
            "- **Infrastructure**: Migrations (EF Core), repositórios, configurações\n"
            "- **Domain**: Entidades, Value Objects, regras de negócio\n"
            "- **Application**: Services, Handlers (MediatR/CQRS), DTOs, AutoMapper\n"
            "- **Presentation**: Endpoints (FastEndpoints/Controllers), validações, Swagger\n"
            "- **Quality**: Testes unitários (xUnit), testes de integração, code review\n\n"
            "IDIOMA: Títulos, descrições e textos explicativos são SEMPRE em PORTUGUÊS. "
            "Apenas TRECHOS DE CÓDIGO (classes, interfaces, métodos, endpoints, payloads) "
            "são em inglês.\n\n"
            "Quando a US inclui contratos de API ou eventos, use-os como base para definir "
            "as classes, interfaces e DTOs nas tasks.\n\n"
            "REGRAS:\n"
            "1) Exatamente 5 Tasks por User Story.\n"
            "2) Cada Task ataca uma camada/responsabilidade específica.\n"
            "3) Inclua exemplos de classes/interfaces a criar (em inglês).\n"
            "4) HTML simples (<b>, <br>, <ul>, <li>, <p>, <pre>, <code>). NUNCA Markdown.\n"
            "5) Use o parent_id EXATO da User Story correspondente."
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
            "Você recebeu uma lista de User Stories já criadas no Azure DevOps com seus IDs REAIS.\n"
            "**ATENÇÃO CRÍTICA**: O parent_id de cada Task DEVE ser o ID EXATO da User Story "
            "correspondente conforme listado no contexto recebido. NÃO invente IDs.\n\n"
            "## Regras para Tasks\n"
            "Para CADA User Story, crie exatamente **5 Tasks** cobrindo:\n\n"
            "1. **Infraestrutura e Persistência**\n"
            "   - Criar/atualizar migrations (EF Core), repositórios, configurações de banco\n"
            "   - Mapear entidades e configurar DbContext\n\n"
            "2. **Lógica de Domínio e Application Layer**\n"
            "   - Implementar Services/Handlers (MediatR), DTOs, mapeamentos (AutoMapper)\n"
            "   - Regras de negócio e validações de domínio\n\n"
            "3. **Endpoint/API e Segurança**\n"
            "   - Expor endpoint (FastEndpoints ou Controller)\n"
            "   - Configurar autenticação/autorização (JWT), documentar no Swagger/OpenAPI\n\n"
            "4. **Testes e Qualidade**\n"
            "   - Testes unitários (xUnit/NSubstitute) para services e domain\n"
            "   - Testes de integração para repositórios e endpoints\n\n"
            "5. **Observabilidade e Code Review**\n"
            "   - Instrumentação com OpenTelemetry (traces, métricas)\n"
            "   - Health checks, logging estruturado, PR review\n\n"
            "## Formato da descrição (campo `descricao`)\n"
            "A descrição DEVE ser HTML simples (NÃO Markdown).\n"
            "Inclua exemplos de classes/interfaces a criar, SEMPRE EM INGLÊS:\n\n"
            "```\n"
            "<p><b>Objetivo</b><br>\n"
            "Descrição clara do que esta task entrega.</p>\n\n"
            "<p><b>O que implementar</b></p>\n"
            "<ul>\n"
            "<li>Item 1</li>\n"
            "<li>Item 2</li>\n"
            "</ul>\n\n"
            "<p><b>Classes/Interfaces</b></p>\n"
            "<pre><code>\n"
            "public class RefundRequest { ... }\n"
            "public interface IRefundRepository { ... }\n"
            "</code></pre>\n\n"
            "<p><b>Camada</b>: Infrastructure | Domain | Application | Presentation | Quality</p>\n\n"
            "<p><b>Definition of Done</b></p>\n"
            "<ul>\n"
            "<li>Código implementado e compilando</li>\n"
            "<li>Testes passando</li>\n"
            "<li>PR aprovado</li>\n"
            "</ul>\n"
            "```\n\n"
            "## Como usar a ferramenta\n"
            "Para cada Task, use `criar_work_item_azure` com:\n"
            "- **titulo**: nome técnico claro (ex: 'Criar migration e repositório para tabela Orders')\n"
            "- **descricao**: texto HTML conforme template acima (SEM Markdown)\n"
            "- **tipo_item**: `Task`\n"
            "- **parent_id**: ID EXATO da User Story (copiado do contexto)\n\n"
            "Retorne a lista EXATA no formato:\n"
            "Task 1: Título=<titulo>, ID=<id retornado>, parent_id=<id da US>\n"
        ),
        expected_output=(
            "Lista EXATA de Tasks criadas (5 por User Story). Cada uma com Título, ID REAL retornado, "
            "e parent_id REAL da User Story. Formato: 'Task N: Título=..., ID=..., parent_id=...'"
        ),
        agent=agent,
        context=[stories_task],
    )
