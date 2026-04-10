# poc-agent — Pipeline Multi-Agente para Azure DevOps

Pipeline automatizado que lê uma **especificação funcional** e cria, no Azure DevOps, a hierarquia completa de **Features → User Stories → Tasks** usando agentes de IA especializados com [LangChain](https://python.langchain.com/).

## Como Funciona

A ideia é simples: você escreve uma spec funcional (Markdown) e o pipeline a transforma numa hierarquia de trabalho pronta no Azure DevOps, sem intervenção manual.

Quatro agentes executam em sequência, cada um recebendo o resultado do anterior:

```
Especificação (.md)
        │
        ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│     Bic       │     │     Mimi      │     │   Givaldo     │     │   Jaiminho    │
│  Arquiteto    │────▶│ Product Owner │────▶│  Tech Lead    │────▶│ Desenvolvedor │
│  (análise)    │     │  (Features)   │     │(User Stories) │     │   (Tasks)     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                            │                    │                    │
                            ▼                    ▼                    ▼
                     ┌─────────────────────────────────────────────────────┐
                     │              Azure DevOps (REST API)                │
                     │    Features ← User Stories ← Tasks (hierárquico)   │
                     └─────────────────────────────────────────────────────┘
```

### Os Agentes

| Agente | Papel | O que produz |
|--------|-------|--------------|
| **Bic** | Arquiteto .NET Sênior | Documento de arquitetura em Markdown — complementa a spec com observabilidade, resiliência, segurança e mensageria |
| **Mimi** | Product Owner | 2-3 Features no Azure DevOps representando processos de negócio (nunca componentes técnicos) |
| **Givaldo** | Tech Lead | Até 5 User Stories por Feature, com contrato de API REST ou CloudEvents e critérios de aceite Gherkin |
| **Jaiminho** | Desenvolvedor .NET Sênior | Exatamente 4 Tasks por User Story: Análise, Desenvolvimento, Integração/Testes e Testes de Unidade |

---

## Decisão Técnica: Por que LangChain?

Esta POC foi construída em três iterações, cada uma com um framework diferente. O resumo:

### Iteração 1 — CrewAI

O projeto começou com [CrewAI](https://docs.crewai.com/), que oferece uma abstração de alto nível (Crew, Agent, Task) com orquestração declarativa.

**Problemas encontrados:**

- O CrewAI injeta cabeçalhos proprietários nas chamadas ao LLM, o que **aumentou significativamente a taxa de erros 503 / RESOURCE_EXHAUSTED** no Gemini (o provider usado nesta POC)

- Pouco controle sobre o loop interno do agente — difícil ajustar o comportamento quando o modelo começa a alucinar `parent_id`
- Abstração pesada: ao depurar, era difícil saber exatamente qual chamada estava falhando
- Dependência de `CREWAI_TRACING_ENABLED=false` para não vazar dados para servidores externos

### Iteração 2 — LangGraph

[LangGraph](https://langchain-ai.github.io/langgraph/) modela o workflow como um **grafo de estados** (`StateGraph`), com nós, arestas e checkpoints.

**Por que não foi adotado:**

- Para um pipeline **puramente sequencial** (sem ciclos, sem branches condicionais), o grafo é over-engineering — exige definir `TypedDict` de estado, registrar cada nó e conectá-los com `add_edge`
- O valor do LangGraph aparece em cenários mais complexos: retry de nó individual, paralelismo, loops de reflexão. Esse pipeline não tem nenhum desses requisitos
- Mais código boilerplate para o mesmo resultado

> LangGraph seria a escolha certa se o pipeline precisasse de: retomar do ponto de falha sem reiniciar tudo, paralelizar criação de Features/Stories/Tasks, ou adicionar um agente de revisão com retorno condicional.

### Iteração 3 — LangChain (escolha final)

LangChain puro (sem o grafo) resolveu os problemas anteriores:

| Critério | Resultado |
|----------|-----------|
| **Erros 503** | Reduzidos — sem cabeçalhos extras, as chamadas chegam mais "limpas" ao Gemini |
| **Controle do loop** | `AgentExecutor` com `max_iterations` explícito por agente |
| **Legibilidade** | Agentes simples usam LCEL (`prompt \| llm \| parser`); agentes com tools usam `create_tool_calling_agent` |
| **Código** | Cada agente tem ~30 linhas: system prompt, task template, factory de 1 linha |
| **Sem lock-in** | Trocar o LLM é mudar uma variável de ambiente |

O pipeline sequencial é orquestrado diretamente em Python, em [workflow.py](workflow.py) — sem framework de orquestração. O que você vê é o que acontece.

---

## Estrutura do Projeto

```
├── config.py          # LLM factory com rate limiter, retry e fallback
├── tools.py           # Tool Azure DevOps + WorkItemRegistry (anti-hallucination de IDs)
├── workflow.py        # Orquestrador: chama os agentes em sequência
├── agents/
│   ├── _base.py       # Classe Agent + helper make_tool_agent (elimina boilerplate)
│   ├── bic.py         # Agente Arquiteto (LCEL puro, sem tools)
│   ├── mimi.py        # Agente Product Owner (tool-calling)
│   ├── givaldo.py     # Agente Tech Lead (tool-calling)
│   └── jaiminho.py    # Agente Desenvolvedor (tool-calling)
├── specs/
│   └── exemplo_estorno.md  # Exemplo de especificação funcional
├── .env.example       # Template de variáveis de ambiente
├── requirements.txt   # Dependências Python
└── Dockerfile         # Imagem para execução containerizada
```

---

## Pré-requisitos

- Python 3.11+
- Azure DevOps com Personal Access Token (PAT) com permissão de escrita em Work Items
- Chave de API do **Google Gemini** (ou adapte `config.py` para outro provider)

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

# LLM (obrigatório)
GEMINI_API_KEY=sua-chave
LLM_MODEL=gemini-2.5-flash

# Opcional: modelo de fallback caso o primário retorne 503 repetidamente
# LLM_FALLBACK_MODEL=gemini-2.0-flash
```

## Execução

```bash
# Passando a especificação como arquivo
python workflow.py specs/exemplo_estorno.md

# Ou via stdin
cat especificacao.md | python workflow.py
```

### Docker

```bash
docker build -t poc-agent .
docker run --env-file .env -v ./especificacao.md:/app/especificacao.md poc-agent python workflow.py especificacao.md
```

---

## Detalhes de Implementação

### Pipeline Sequencial (`workflow.py`)

Quatro chamadas encadeadas em Python puro:

```python
arch_output     = generate_architecture(bic, specification)   # Bic: análise técnica
features_output = create_features(mimi, arch_output)          # Mimi: Features no DevOps
stories_output  = create_stories(givaldo, features_output, specification)  # Givaldo: User Stories
tasks_output    = create_tasks(jaiminho, stories_output, specification)    # Jaiminho: Tasks
```

Cada função recebe o output da etapa anterior — sem framework de orquestração, sem magia.

### Dois padrões de agente (`agents/`)

**Agente simples (Bic)** — usa LCEL, sem tools, sem loop:
```python
chain = prompt | llm | StrOutputParser()
```

**Agente com tool-calling (Mimi, Givaldo, Jaiminho)** — usa `AgentExecutor` com loop ReAct:
```python
# make_tool_agent em _base.py centraliza esse padrão para os 3 agentes
return make_tool_agent("Mimi — Product Owner", llm, tool, _SYSTEM, max_iterations=15)
```

### Anti-hallucination de IDs (`tools.py`)

O LLM tende a inventar `parent_id`. O `WorkItemRegistry` resolve isso:

- Registra cada Work Item criado com seu ID real
- Quando um agente tenta criar um filho, valida se o `parent_id` existe e é do tipo correto
- Se inválido, retorna a lista de IDs válidos para o agente se corrigir na próxima iteração

```
Feature       → sem pai
User Story    → pai deve ser Feature
Task          → pai deve ser User Story
```

### Rate limiting e retry (`config.py`)

O `_ThrottledLLM` é um wrapper sobre o LLM que:
- Controla requisições por minuto (janela deslizante de 60s)
- Retry com backoff exponencial para erros 503/429
- Fallback automático para um modelo alternativo após N tentativas falhas

### Normalização de Input (`WorkItemInput`)

O LLM pode enviar campos em diferentes formatos (`titulo`, `Titulo`, `title`, `Title`...). O `model_validator` no Pydantic normaliza tudo antes de chamar a API do Azure DevOps.

---

## Configurações Avançadas

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `LLM_MODEL` | `gemini-2.5-flash` | Modelo principal |
| `LLM_FALLBACK_MODEL` | _(vazio)_ | Modelo alternativo ativado após `LLM_FALLBACK_AFTER` erros 503 |
| `LLM_FALLBACK_AFTER` | `3` | Tentativas antes de acionar o fallback |
| `LLM_RPM` | `10` | Requests por minuto |
| `LLM_MAX_RETRIES` | `8` | Tentativas totais por chamada |
| `LLM_RETRY_BASE_DELAY` | `15` | Delay base em segundos (backoff exponencial) |
| `LLM_RETRY_MAX_DELAY` | `120` | Teto do backoff em segundos |
| `LOG_LEVEL` | `INFO` | Nível de log (`DEBUG` para ver payloads completos) |

---

## Licença

MIT
