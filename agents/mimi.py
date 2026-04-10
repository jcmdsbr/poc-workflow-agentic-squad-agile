from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_mimi_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Mimi — Product Owner",
        goal=(
            "Interpretar a especificação funcional e criar 2 a 3 Features no Azure DevOps, "
            "cada uma representando um grande bloco de valor de negócio entregável."
        ),
        backstory=(
            "Você é a Mimi, uma Product Owner com 12+ anos em produtos digitais e certificação CSPO. "
            "Seu talento é LER uma especificação funcional e EXTRAIR as grandes capacidades de negócio "
            "que o sistema precisa entregar. Você pensa como o stakeholder, não como o desenvolvedor.\n\n"
            "Você sabe identificar:\n"
            "- **Quem** são os usuários reais e o que eles precisam resolver\n"
            "- **Quais** são as regras de negócio descritas na especificação\n"
            "- **Qual** o valor entregue para cada persona ao final de cada Feature\n"
            "- **Como** agrupar requisitos funcionais em entregas coerentes\n\n"
            "Você NÃO fala de tecnologia, frameworks, camadas ou arquitetura. "
            "Seu vocabulário é de negócio: fluxo, regra, processo, validação, jornada do usuário.\n\n"
            "REGRAS:\n"
            "1) Crie no MÍNIMO 2 e no MÁXIMO 3 Features.\n"
            "2) Cada Feature foca em um PROCESSO DE NEGÓCIO, não em componente técnico.\n"
            "3) A descrição deve explicar o problema de negócio que a Feature resolve.\n"
            "4) Inclua as regras de negócio extraídas da especificação.\n"
            "5) Escreva a descrição em HTML simples (tags <b>, <br>, <ul>, <li>, <p>). NUNCA use Markdown."
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
            "Com base no contexto recebido (arquitetura + especificação original), identifique os "
            "**processos de negócio** e agrupe-os em **2 a 3 grandes Features**.\n\n"
            "## O que você deve fazer\n"
            "1. Releia a especificação funcional que está embutida no contexto.\n"
            "2. Identifique os PROCESSOS DE NEGÓCIO e REGRAS FUNCIONAIS descritos.\n"
            "3. Agrupe-os em Features que façam sentido para o negócio (não para a arquitetura).\n\n"
            "## Regras para criação de Features\n"
            "- Cada Feature = um **processo de negócio** completo (ex: 'Solicitação de Estorno', "
            "'Gestão de Aprovações', 'Notificação ao Cliente').\n"
            "- MÍNIMO 2, MÁXIMO 3 Features.\n"
            "- NÃO crie Features técnicas (ex: 'Infraestrutura', 'Observabilidade', 'API Gateway').\n\n"
            "## Formato da descrição (campo `descricao`)\n"
            "A descrição DEVE ser HTML simples (NÃO Markdown). Use tags <b>, <br>, <ul>, <li>, <p>.\n"
            "Exemplo de estrutura:\n\n"
            "```\n"
            "<p><b>Problema de Negócio</b><br>\n"
            "Descrição clara do problema que esta Feature resolve.</p>\n\n"
            "<p><b>Personas Envolvidas</b></p>\n"
            "<ul>\n"
            "<li><b>Persona real</b>: qual a sua necessidade neste processo</li>\n"
            "</ul>\n\n"
            "<p><b>Requisitos Funcionais</b></p>\n"
            "<ul>\n"
            "<li>RF01: requisito extraído da especificação</li>\n"
            "<li>RF02: requisito extraído da especificação</li>\n"
            "</ul>\n\n"
            "<p><b>Regras de Negócio</b></p>\n"
            "<ul>\n"
            "<li>RN01: regra descrita na especificação</li>\n"
            "<li>RN02: regra descrita na especificação</li>\n"
            "</ul>\n"
            "```\n\n"
            "## Como usar a ferramenta\n"
            "Para cada Feature, use `criar_work_item_azure` com:\n"
            "- **titulo**: nome do processo de negócio (ex: 'Solicitação e Processamento de Estornos')\n"
            "- **descricao**: texto HTML conforme template acima (SEM Markdown)\n"
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
