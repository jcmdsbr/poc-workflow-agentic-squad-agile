from crewai import Agent, Task, LLM
from tools import AzureDevOpsTool


def create_givaldo_agent(llm: LLM, tool: AzureDevOpsTool) -> Agent:
    return Agent(
        role="Givaldo — Tech Lead",
        goal=(
            "Decompor cada Feature em User Stories que descrevam comportamentos de negócio "
            "extraídos da especificação funcional, incluindo contratos de API e mensageria."
        ),
        backstory=(
            "Você é o Givaldo, um líder técnico com 10+ anos de experiência e certificação CSM. "
            "Seu papel é ser a PONTE entre negócio e desenvolvimento.\n\n"
            "PRINCÍPIO CENTRAL: Você NÃO INVENTA requisitos de negócio. Cada requisito funcional, "
            "regra de negócio e critério de aceite DEVE estar contido na especificação funcional. "
            "Se algo está implícito ou subentendido, você EXPLICITA na User Story.\n\n"
            "CONTRATOS: Você é responsável por DEFINIR os contratos técnicos de cada US:\n"
            "- Se a US expõe uma API: inclua o contrato OpenAPI (endpoint, método, request/response)\n"
            "- Se a US publica/consome eventos: inclua o contrato do evento (nome, payload)\n"
            "- Se a US consome API externa: inclua o contrato esperado\n"
            "Os contratos servem como especificação técnica para o desenvolvedor.\n\n"
            "IDIOMA DO CÓDIGO: Todo código, contrato, nome de classe, propriedade e endpoint "
            "DEVE ser escrito em INGLÊS. Textos descritivos continuam em português.\n\n"
            "TÍTULOS: Frase curta que sintetize o conteúdo. Não use 'Como X, quero Y' no título.\n\n"
            "Você NUNCA usa 'Como um usuário' genérico. Identifica a PERSONA REAL.\n\n"
            "REGRAS:\n"
            "1) Mínimo 1, máximo 5 User Stories por Feature.\n"
            "2) NENHUMA regra ou requisito de negócio inventado.\n"
            "3) Subentendidos da spec devem ser explicitados na US.\n"
            "4) Inclua contratos de API/mensageria quando aplicável.\n"
            "5) Código e contratos SEMPRE em inglês.\n"
            "6) HTML simples (<b>, <br>, <ul>, <li>, <p>, <pre>, <code>). NUNCA Markdown.\n"
            "7) Use criterios_aceite separado da descrição.\n"
            "8) Use o parent_id EXATO da Feature."
        ),
        verbose=False,
        allow_delegation=False,
        tools=[tool],
        llm=llm,
        max_iter=25,
    )


def create_stories_task(agent: Agent, features_task: Task) -> Task:
    return Task(
        description=(
            "Você recebeu uma lista de Features já criadas no Azure DevOps com seus IDs REAIS.\n"
            "**ATENÇÃO CRÍTICA**: O parent_id de cada User Story DEVE ser o ID EXATO da Feature "
            "correspondente conforme listado no contexto recebido. NÃO invente IDs.\n\n"
            "## O que você deve fazer\n"
            "1. Releia a especificação funcional completa que está no contexto.\n"
            "2. Decomponha cada Feature em até 5 User Stories baseadas EXCLUSIVAMENTE na spec.\n"
            "3. Se algo está implícito/subentendido na spec, EXPLICITE na descrição da US.\n"
            "4. NÃO invente requisitos, regras ou cenários que não existam na especificação.\n\n"
            "## Regras para User Stories\n"
            "- Máximo **5 User Stories por Feature**.\n"
            "- Use **personas reais do negócio** (nunca 'Como um usuário').\n"
            "  Exemplos: Atendente de SAC, Gerente Financeiro, Cliente, "
            "Operador de Backoffice, Analista de Fraude.\n\n"
            "## TÍTULO da User Story\n"
            "O título deve ser uma frase curta que SINTETIZE o conteúdo da descrição.\n"
            "NÃO use o formato 'Como X, quero Y' no título.\n"
            "Exemplos de bons títulos:\n"
            "- 'Solicitar estorno de cobrança indevida'\n"
            "- 'Aprovar ou rejeitar solicitação de estorno'\n"
            "- 'Consultar histórico de estornos realizados'\n\n"
            "## Formato da descrição (campo `descricao`)\n"
            "A descrição DEVE ser HTML simples. Conteúdo:\n"
            "- A User Story no formato 'Como [Persona], quero [ação] para [valor]'\n"
            "- Regras de negócio EXTRAÍDAS da especificação (nunca inventadas)\n"
            "- Requisitos implícitos/subentendidos EXPLICITADOS com clareza\n"
            "- Contrato de API ou Evento (quando aplicável) em INGLÊS\n\n"
            "```\n"
            "<p><b>User Story</b><br>\n"
            "Como <b>Persona do Negócio</b>, quero <b>ação funcional</b> para <b>valor de negócio</b>.</p>\n\n"
            "<p><b>Regras de Negócio</b></p>\n"
            "<ul>\n"
            "<li>RN01: regra EXTRAÍDA da especificação</li>\n"
            "</ul>\n\n"
            "<p><b>Contrato da API</b></p>\n"
            "<pre><code>\n"
            "POST /api/v1/refunds\n"
            "Request: { \"orderId\": \"string\", \"reason\": \"string\", \"amount\": 0.00 }\n"
            "Response 201: { \"refundId\": \"string\", \"status\": \"Pending\" }\n"
            "Response 422: { \"error\": \"string\" }\n"
            "</code></pre>\n\n"
            "<p><b>Evento Publicado</b> (se aplicável)</p>\n"
            "<pre><code>\n"
            "Event: RefundRequested\n"
            "Payload: { \"refundId\": \"string\", \"orderId\": \"string\", \"amount\": 0.00, \"requestedAt\": \"datetime\" }\n"
            "</code></pre>\n"
            "```\n\n"
            "## Formato dos critérios de aceite (campo `criterios_aceite`)\n"
            "Os critérios vão no campo SEPARADO `criterios_aceite` (não na descrição).\n"
            "Use HTML com cenários Dado/Quando/Então:\n\n"
            "```\n"
            "<p><b>Cenário 1: nome do cenário de negócio</b></p>\n"
            "<ul>\n"
            "<li><b>Dado que</b> situação de negócio</li>\n"
            "<li><b>Quando</b> ação do usuário</li>\n"
            "<li><b>Então</b> resultado esperado</li>\n"
            "</ul>\n\n"
            "<p><b>Cenário 2: cenário alternativo</b></p>\n"
            "<ul>\n"
            "<li><b>Dado que</b> situação</li>\n"
            "<li><b>Quando</b> ação</li>\n"
            "<li><b>Então</b> resultado</li>\n"
            "</ul>\n"
            "```\n\n"
            "## Como usar a ferramenta\n"
            "Para cada User Story, use `criar_work_item_azure` com:\n"
            "- **titulo**: frase curta que sintetize a US (ex: 'Solicitar estorno de cobrança indevida')\n"
            "- **descricao**: texto HTML conforme template acima (SEM Markdown)\n"
            "- **tipo_item**: `User Story`\n"
            "- **parent_id**: ID EXATO da Feature (copiado do contexto)\n"
            "- **criterios_aceite**: HTML com cenários Dado/Quando/Então (campo separado)\n\n"
            "APÓS CRIAR, anote o ID retornado. Retorne a lista EXATA no formato:\n"
            "US 1: Título=<titulo>, ID=<id retornado>, parent_id=<id da Feature>\n"
        ),
        expected_output=(
            "Lista EXATA de User Stories criadas. Cada uma com Título, ID REAL retornado pela ferramenta, "
            "e parent_id REAL da Feature. Formato: 'US N: Título=..., ID=..., parent_id=...'"
        ),
        agent=agent,
        context=[features_task],
    )
