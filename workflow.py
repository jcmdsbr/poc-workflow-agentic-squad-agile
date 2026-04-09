import os
from crewai import Agent, Task, Crew, Process
from tools import FerramentaAzureDevOps

# 1. Configuração Nativa do CrewAI apontando para o Ollama local com Llama 3.1
os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"
os.environ["OPENAI_API_KEY"] = "ollama-dummy-key" 
modelo_string = "openai/llama3.1"

ferramenta_azure = FerramentaAzureDevOps()

# ==========================================
# 2. DEFINIÇÃO DOS AGENTES BLINDADOS
# ==========================================

alan_arquiteto = Agent(
    role='Arquiteto de Software .NET Senior',
    goal='Desenhar arquiteturas distribuídas e resilientes com base na especificação funcional.',
    backstory='''Você é Alan, um arquiteto de sistemas pragmático.
    Regras estritas: 
    1. Padrão CQRS e FastEndpoints para APIs.
    2. Uso de Polly para resiliência.
    3. OpenTelemetry para observabilidade.
    4. Kubernetes para infra (LoadBalancer para APIs, CronJobs nativos, Google Pub/Sub para mensageria).''',
    verbose=True,
    allow_delegation=False,
    llm=modelo_string
)

paula_po = Agent(
    role='Product Owner Técnica',
    goal='Analisar a arquitetura e criar Features no Azure DevOps.',
    backstory='''Você é Paula. Você lê a especificação técnica e cria de 1 a 5 Features.
    
    REGRA CRÍTICA DE SISTEMA: Você TEM acesso ao Azure DevOps. NUNCA diga que é apenas uma IA.
    Você DEVE OBRIGATORIAMENTE invocar a ferramenta 'criar_work_item_azure'.
    O JSON dos argumentos deve ser PLANO. NUNCA envolva os dados em uma chave "properties".''',
    verbose=True,
    max_iter=5,
    allow_delegation=False,
    tools=[ferramenta_azure],
    llm=modelo_string
)

linus_tech_lead = Agent(
    role='Tech Lead .NET e Scrum Master',
    goal='Fatiar Features em User Stories no Azure DevOps.',
    backstory='''Você é Linus. Você quebra as Features de negócio em User Stories técnicas.
    
    REGRA CRÍTICA DE SISTEMA: Você TEM acesso ao Azure DevOps. NUNCA diga que é apenas uma IA.
    Você DEVE OBRIGATORIAMENTE invocar a ferramenta 'criar_work_item_azure'.
    Lembre-se de passar o 'parent_id' correto. O JSON dos argumentos deve ser PLANO. NUNCA envolva os dados em uma chave "properties".''',
    verbose=True,
    max_iter=10,
    allow_delegation=False,
    tools=[ferramenta_azure],
    llm=modelo_string
)

dennis_dev = Agent(
    role='Desenvolvedor .NET Sênior',
    goal='Quebrar User Stories em Tasks técnicas detalhadas no Azure DevOps.',
    backstory='''Você é Dennis. Você pega a User Story e cria de 2 a 10 Tasks técnicas no nível de código (FastEndpoints, Polly, K8s).
    
    REGRA CRÍTICA DE SISTEMA: Você TEM acesso ao Azure DevOps. NUNCA diga que é apenas uma IA.
    Você DEVE OBRIGATORIAMENTE invocar a ferramenta 'criar_work_item_azure'.
    O JSON dos argumentos deve ser PLANO. NUNCA envolva os dados em uma chave "properties".''',
    verbose=True,
    max_iter=15,
    allow_delegation=False,
    tools=[ferramenta_azure],
    llm=modelo_string
)

# ==========================================
# 3. DEFINIÇÃO DAS TAREFAS
# ==========================================

especificacao_input = """
Especificação Funcional: Processamento de Estorno de Pagamentos.
Todos os dias, à meia-noite, o sistema deve buscar no banco de dados pedidos cancelados.
Para cada pedido, o sistema deve colocar uma mensagem em uma fila para o microsserviço financeiro processar o estorno no gateway de pagamento.
O microsserviço financeiro deve consumir essa fila, processar e atualizar o status via uma API de callback nossa.
"""

tarefa_arquitetura = Task(
    description=f'Gere a documentação técnica (Markdown) com a arquitetura baseada nesta especificação: {especificacao_input}',
    expected_output='Documento Markdown com a arquitetura completa.',
    agent=alan_arquiteto
)

tarefa_po = Task(
    description='''Crie a(s) Feature(s) do projeto.
    Para cada Feature, chame a ferramenta 'criar_work_item_azure' com:
    - titulo
    - descricao
    - tipo_item: "Feature"
    ''',
    expected_output='Lista com os Títulos e IDs das Features criadas.',
    agent=paula_po
)

tarefa_tech_lead = Task(
    description='''Leia as Features geradas e crie User Stories.
    Para cada User Story, chame a ferramenta 'criar_work_item_azure' com:
    - titulo
    - descricao
    - tipo_item: "User Story"
    - parent_id: (ID da Feature correspondente)
    ''',
    expected_output='Lista com os Títulos e IDs das User Stories criadas.',
    agent=linus_tech_lead
)

tarefa_dev = Task(
    description='''Leia as User Stories geradas e crie as Tasks de código.
    Para cada Task, chame a ferramenta 'criar_work_item_azure' com:
    - titulo
    - descricao (detalhes técnicos de FastEndpoints, Polly, K8s, etc)
    - tipo_item: "Task"
    - parent_id: (ID da User Story correspondente)
    ''',
    expected_output='Lista com todos os IDs das Tasks técnicas criadas.',
    agent=dennis_dev
)

# ==========================================
# 4. ORQUESTRAÇÃO
# ==========================================

equipe_dev = Crew(
    agents=[alan_arquiteto, paula_po, linus_tech_lead, dennis_dev],
    tasks=[tarefa_arquitetura, tarefa_po, tarefa_tech_lead, tarefa_dev],
    process=Process.sequential
)

print("🚀 Iniciando o Pipeline de Agentes Locais (.NET Enterprise Edition com Llama 3.1)...")
try:
    resultado_final = equipe_dev.kickoff()
    print("\n\n✅ FLUXO CONCLUÍDO COM SUCESSO!")
    print("========================================")
    print(resultado_final)
except Exception as e:
    print(f"\n❌ ERRO NA EXECUÇÃO DO WORKFLOW: {str(e)}")