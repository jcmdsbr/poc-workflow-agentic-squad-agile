# poc-agent — Pipeline Multi-Agente para Azure DevOps

Pipeline automatizado que lê uma **especificação funcional** e cria, no Azure DevOps, a hierarquia completa de **Features → User Stories → Tasks** usando agentes de IA especializados ([CrewAI](https://docs.crewai.com/)).

Suporta múltiplos providers de LLM (Ollama, Gemini, OpenAI) com troca por variável de ambiente.

## Visão Geral da Arquitetura

```
Especificação (.md)
        │
        ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Bic          │     │  Mimi         │     │  Givaldo      │     │  Jaiminho     │
│  Arquiteto    │────▶│  Product Owner│────▶│  Tech Lead    │────▶│  Desenvolvedor│
│  Análise Arq. │     │  Features     │     │  User Stories │     │  Tasks        │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                            │                    │                    │
                            ▼                    ▼                    ▼
                     ┌─────────────────────────────────────────────────────┐
                     │              Azure DevOps (REST API)                │
                     │    Features ← User Stories ← Tasks (hierárquico)   │
                     └─────────────────────────────────────────────────────┘
```

### Agentes

| Agente | Papel | Saída |
|--------|-------|-------|
| **Bic** | Arquiteto de Software (.NET, 15+ anos) | Documento de arquitetura Markdown (CQRS, DDD, Hexagonal) |
| **Mimi** | Product Owner (CSPO, 12+ anos) | 2-3 Features no Azure DevOps com descrição estruturada |
| **Givaldo** | Tech Lead (CSM, 10+ anos) | Até 5 User Stories por Feature (INVEST + Gherkin BDD) |
| **Jaiminho** | Desenvolvedor Sênior (.NET, 10+ anos) | 5 Tasks por User Story cobrindo todas as camadas |

O pipeline é **sequencial**: cada agente recebe o output do anterior via `context`, garantindo rastreabilidade hierárquica.

## Estrutura do Projeto

```
├── config.py          # Configuração: LLM factory, provider auto-detection, rate limiter
├── tools.py           # Ferramenta Azure DevOps + validação de hierarquia (WorkItemRegistry)
├── workflow.py        # Orquestrador principal (Crew + Process.sequential)
├── agents/
│   ├── __init__.py    # Re-exporta todas as factories
│   ├── bic.py         # Agente Arquiteto
│   ├── mimi.py        # Agente Product Owner
│   ├── givaldo.py     # Agente Tech Lead
│   └── jaiminho.py    # Agente Desenvolvedor
├── .env.example       # Template de variáveis de ambiente
├── requirements.txt   # Dependências Python
└── Dockerfile         # Imagem para execução containerizada
```

## Pré-requisitos

- Python 3.11+
- Azure DevOps com Personal Access Token (PAT) com permissão de escrita em Work Items
- Um provedor de LLM: **Ollama** (local), **Gemini**, ou **OpenAI**

## Configuração

1. Clone o repositório:

```bash
git clone <url-do-repositório>
cd poc-agent
```

2. Crie o ambiente virtual e instale as dependências:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Copie e preencha o arquivo de configuração:

```bash
cp .env.example .env
```

4. Edite o `.env` com suas credenciais:

```env
# Azure DevOps (obrigatório)
AZURE_ORG=sua-organizacao
AZURE_PROJECT=seu-projeto
AZURE_PAT=seu-personal-access-token

# LLM — troque apenas esta linha para mudar de provider
LLM_MODEL=ollama/llama3.1          # Ollama local (padrão)
# LLM_MODEL=gemini/gemini-2.5-flash  # Google Gemini
# LLM_MODEL=openai/gpt-4o           # OpenAI

# Key do provider hospedado (descomente conforme necessário)
# GEMINI_API_KEY=sua-chave
# OPENAI_API_KEY=sua-chave
```

### Troca de Provider

O provider é **auto-detectado** pelo prefixo do modelo:

| Prefixo | Provider | Key obrigatória |
|---------|----------|-----------------|
| `ollama/` | Ollama local | Nenhuma |
| `gemini/` | Google Gemini | `GEMINI_API_KEY` |
| `openai/` | OpenAI | `OPENAI_API_KEY` |
| `anthropic/` | Anthropic | `ANTHROPIC_API_KEY` |

Basta alterar `LLM_MODEL` no `.env` — nenhuma mudança de código necessária.

### Rate Limiting

O rate limiter (janela deslizante de 60s) é ativado automaticamente para providers hospedados:

| Provider | RPM padrão |
|----------|-----------|
| Ollama | 0 (sem limite) |
| Gemini | 10 |
| OpenAI | 30 |

Para ajustar, defina `LLM_RPM` no `.env`.

## Execução

```bash
# Passando a especificação como arquivo
python workflow.py especificacao.md

# Ou via stdin
cat especificacao.md | python workflow.py
```

### Docker

```bash
docker build -t poc-agent .
docker run --env-file .env -v ./especificacao.md:/app/especificacao.md poc-agent python workflow.py especificacao.md
```

> **Nota:** Se usar Ollama local com Docker, adicione `--network host` ou configure `OLLAMA_BASE_URL=http://host.docker.internal:11434` no `.env`.

## Como Funciona

### 1. Validação (`config.py`)

Ao iniciar, `validate_config()` verifica se todas as variáveis obrigatórias estão definidas (Azure DevOps + key do provider). Se faltar algo, o processo encerra com mensagem clara.

### 2. Pipeline Sequencial (`workflow.py`)

O `Crew` executa 4 etapas em sequência:

1. **Bic** lê a especificação e gera um documento de arquitetura (não cria nada no Azure DevOps)
2. **Mimi** lê a arquitetura e cria 2-3 **Features** no Azure DevOps
3. **Givaldo** lê as Features e cria até 5 **User Stories** por Feature (padrão INVEST, critérios Gherkin)
4. **Jaiminho** lê as User Stories e cria 5 **Tasks** por User Story (cobrindo Infrastructure, Domain, Application, Presentation, Quality)

Cada etapa recebe o resultado da anterior via o parâmetro `context` do CrewAI.

### 3. Validação de Hierarquia (`tools.py`)

O `WorkItemRegistry` impede que o LLM invente IDs (hallucination):

- Registra todo Work Item criado com sucesso
- Quando um agente tenta criar um item filho, valida se o `parent_id` é um ID real do tipo pai esperado
- Se inválido, retorna erro com a lista de IDs válidos para o agente corrigir

```
Feature       → sem pai
User Story    → pai deve ser Feature
Task          → pai deve ser User Story
```

### 4. Normalização de Input (`WorkItemInput`)

O LLM pode enviar campos em diferentes formatos (PascalCase, camelCase, envoltos em `properties`). O `model_validator` normaliza tudo automaticamente antes de chamar a API.

## Capacidade do Pipeline

| Agente | max_iter | Quantidade máxima de itens |
|--------|----------|---------------------------|
| Bic | 3 | 1 documento de arquitetura |
| Mimi | 8 | 2-3 Features |
| Givaldo | 25 | até 15 User Stories |
| Jaiminho | 90 | até 75 Tasks |

Total: até **126 chamadas ao LLM** por execução.

## Configurações Avançadas

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `LLM_NUM_CTX` | 32768 | Tamanho do contexto (só Ollama) |
| `LLM_RPM` | auto | Requests por minuto (override manual) |
| `CREWAI_TRACING_ENABLED` | false | Envia traces para app.crewai.com (dados sensíveis!) |
| `LOG_LEVEL` | INFO | Nível de log (`DEBUG` para ver payloads) |

## Licença

MIT
