# POC Agent — Pipeline de Agentes para Azure DevOps

Pipeline de agentes de IA que lê uma **especificação funcional** e cria automaticamente **Features**, **User Stories** e **Tasks** no Azure DevOps, usando LLM local (Ollama + Llama 3.1) e o framework [CrewAI](https://docs.crewai.com/).

## Como funciona

O pipeline executa 4 agentes em sequência, onde cada um recebe o resultado do anterior:

```
Especificação (.md)
       │
       ▼
┌─────────────────┐
│   Arquiteto      │  Lê a spec e gera documento de arquitetura técnica
└────────┬────────┘
         │ (documento .md)
         ▼
┌─────────────────┐
│  Product Owner   │  Lê a arquitetura e cria Features no Azure DevOps
└────────┬────────┘
         │ (IDs das Features)
         ▼
┌─────────────────┐
│   Tech Lead      │  Decompõe Features em User Stories (vinculadas via parent_id)
└────────┬────────┘
         │ (IDs das User Stories)
         ▼
┌─────────────────┐
│  Desenvolvedor   │  Decompõe User Stories em Tasks técnicas (vinculadas via parent_id)
└─────────────────┘
```

### Conceitos-chave de Agentes usados

| Conceito | Onde está | Para que serve |
|---|---|---|
| **Agent** | `workflow.py` → `create_agents()` | Cada agente tem um `role`, `goal` e `backstory` que definem seu comportamento. O LLM usa essas informações para "interpretar" o papel. |
| **Tool** | `tools.py` → `AzureDevOpsTool` | Ferramentas são funções que o agente pode invocar. Aqui, a tool chama a API REST do Azure DevOps. O schema Pydantic garante que o LLM passe os parâmetros corretos. |
| **Task** | `workflow.py` → `create_tasks()` | Cada task descreve **o que** o agente deve fazer. O `expected_output` ajuda o LLM a saber quando terminou. |
| **context** | `context=[task_anterior]` nas Tasks | **Encadeia a saída de uma task como entrada da próxima.** Sem isso, o agente não recebe os IDs criados pelo agente anterior. |
| **Crew** | `workflow.py` → `main()` | Orquestra agentes + tasks. `Process.sequential` executa na ordem definida. |

## Estrutura do projeto

```
├── workflow.py          # Orquestração: agentes, tasks e execução
├── tools.py             # Ferramenta de integração com Azure DevOps
├── requirements.txt     # Dependências Python
├── Dockerfile           # Container para execução
├── .env.example         # Template de variáveis de ambiente
└── specs/
    └── exemplo_estorno.md   # Exemplo de especificação funcional
```

## Pré-requisitos

1. **Ollama** rodando localmente com o modelo Llama 3.1:
   ```bash
   ollama pull llama3.1
   ollama serve   # roda na porta 11434 por padrão
   ```

2. **Azure DevOps** com um Personal Access Token (PAT) que tenha permissão de **Work Items (Read & Write)**.

## Setup

```bash
# 1. Clone e entre no diretório
git clone <repo-url> && cd poc-agent

# 2. Crie o ambiente virtual e instale dependências
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com seus dados do Azure DevOps
```

## Uso

```bash
# Passar arquivo de especificação como argumento
python workflow.py specs/exemplo_estorno.md

# Ou via stdin
cat specs/exemplo_estorno.md | python workflow.py
```

## Usando com Docker

```bash
docker build -t poc-agent .
docker run --env-file .env -v $(pwd)/specs:/app/specs poc-agent python workflow.py specs/exemplo_estorno.md
```

> **Nota:** O container precisa acessar o Ollama. Se o Ollama roda na máquina host, use `--network host` ou configure `LLM_BASE_URL=http://host.docker.internal:11434/v1` no `.env`.

## O que foi corrigido em relação ao código original

### 1. Removida dependência desnecessária (`langchain-community`)
O `requirements.txt` original incluía `langchain-community` que **não era importada em nenhum lugar**. O projeto usa apenas CrewAI — são frameworks diferentes. Removida para evitar confusão.

### 2. Ativado `python-dotenv` (estava no requirements mas não era usado)
A dependência `python-dotenv` estava instalada mas `load_dotenv()` nunca era chamado. Agora o `workflow.py` carrega o `.env` automaticamente na inicialização.

### 3. Especificação agora é input dinâmico (antes era hardcoded)
A especificação funcional estava escrita direto no código-fonte. Agora é lida de um arquivo `.md` passado como argumento, seguindo a boa prática de separar dados de lógica.

### 4. Tasks encadeadas com `context=[]`
**Este era o bug mais crítico.** As tasks originais não tinham o parâmetro `context`, então:
- A Product Owner não recebia o documento de arquitetura do Arquiteto
- O Tech Lead não recebia os IDs das Features criadas pela PO
- O Desenvolvedor não recebia os IDs das User Stories do Tech Lead

Agora cada task referencia a anterior via `context=[task_anterior]`, garantindo que os IDs fluam corretamente pelo pipeline.

### 5. Removidos "prompt injections" dos backstories
Os backstories originais tinham frases como `"REGRA CRÍTICA DE SISTEMA: NUNCA diga que é apenas uma IA"`. Isso é uma técnica frágil chamada **prompt injection defensivo** — tenta forçar comportamento que deveria vir da arquitetura do sistema (tools + task descriptions), não de hacks no prompt. Agora os backstories descrevem apenas o papel do agente.

### 6. Validação de configuração na inicialização
Se `AZURE_ORG`, `AZURE_PROJECT` ou `AZURE_PAT` não estiverem definidos, o programa agora **falha imediatamente** com mensagem clara, em vez de só dar erro na hora da chamada API.

### 7. Timeout nas chamadas HTTP
A tool original não tinha `timeout` na chamada `requests.post()`. Se a API do Azure DevOps ficasse lenta, o agente ficaria preso para sempre. Agora tem timeout de 30 segundos.

### 8. Validação do tipo de Work Item
A tool agora valida se `tipo_item` é um dos valores aceitos (`Feature`, `User Story`, `Task`) antes de fazer a chamada HTTP. Antes, qualquer string era enviada direto para a API.

### 9. Dockerfile apontava para arquivo errado
O `CMD` referenciava `workflow_agentes.py` que não existia. Corrigido para `workflow.py`.

### 10. Logging ao invés de prints
Substituídos `print()` com emojis por `logging` padrão do Python, que permite controlar o nível de verbosidade e integrar com ferramentas de observabilidade.
