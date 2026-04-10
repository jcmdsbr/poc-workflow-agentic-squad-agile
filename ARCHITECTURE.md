# Arquitetura do Projeto: Pipeline Multi-Agente com LangChain

Este documento descreve a estrutura, os padrões e as decisões de design deste projeto. O objetivo é servir como **template de referência** para criar pipelines multi-agente semelhantes com LangChain, independente do domínio.

---

## Conceito Central

O projeto resolve um problema de **automação sequencial com LLM**: recebe uma entrada (especificação funcional em Markdown) e produz saídas concretas em um sistema externo (Azure DevOps), passando por N agentes especializados em sequência.

Cada agente tem um **papel bem definido** e recebe como entrada o output do agente anterior. Não há framework de orquestração — o fluxo é Python puro.

---

## Estrutura de Arquivos

```
├── config.py          # LLM factory: rate limiter, retry com backoff, fallback de modelo
├── tools.py           # Ferramenta externa (BaseTool) + validação de estado global (Registry)
├── workflow.py        # Ponto de entrada: instancia agentes e executa o pipeline
├── agents/
│   ├── __init__.py    # Re-exporta factories e funções de execução
│   ├── _base.py       # Classe Agent + helper make_tool_agent (elimina boilerplate)
│   ├── bic.py         # Agente 1: análise — sem tools, usa LCEL
│   ├── mimi.py        # Agente 2: decomposição — com tool-calling
│   ├── givaldo.py     # Agente 3: tradução técnica — com tool-calling
│   └── jaiminho.py    # Agente 4: implementação — com tool-calling
├── specs/
│   └── exemplo_estorno.md   # Exemplo de input do pipeline
├── .env.example       # Template de variáveis de ambiente
├── requirements.txt   # Dependências mínimas
└── Dockerfile         # Imagem sem root para execução containerizada
```

---

## Passo a Passo: Como Replicar Este Padrão

### Passo 1 — Defina o Pipeline

Antes de escrever uma linha de código, responda:

1. **Qual é a entrada do pipeline?** (arquivo, stdin, webhook, etc.)
2. **Quais são as etapas sequenciais?** Cada etapa = um agente com um papel único
3. **Qual é a saída de cada etapa?** O output de uma etapa vira o input da próxima
4. **Alguma etapa precisa interagir com um sistema externo?** (API, banco, arquivo) → essa etapa precisa de tool-calling
5. **Há estado que precisa ser validado entre etapas?** → implemente um Registry

Para este projeto:
```
Entrada: spec funcional (.md)
  → Etapa 1 (Bic):     análise arquitetural          → Markdown (sem tools)
  → Etapa 2 (Mimi):    criação de Features            → IDs reais no Azure DevOps
  → Etapa 3 (Givaldo): criação de User Stories        → IDs reais no Azure DevOps
  → Etapa 4 (Jaiminho): criação de Tasks              → IDs reais no Azure DevOps
Saída: hierarquia completa criada no Azure DevOps
```

---

### Passo 2 — Implemente `config.py`

Responsabilidades:
- Carregar `.env` com `python-dotenv`
- Validar variáveis obrigatórias na inicialização (`validate_config`)
- Expor `create_llm()` que retorna o LLM pronto para uso

**Padrão recomendado** — o `_ThrottledLLM` envolve o LLM real e adiciona:

```python
class _ThrottledLLM(Runnable):
    """Wrapper sobre o LLM com rate limiting, retry e fallback."""

    def __init__(self, primary, fallback=None): ...

    def invoke(self, input, config=None, **kwargs):
        _rate_limiter.wait_if_needed()          # respeita RPM
        for attempt in range(1, _MAX_RETRIES):
            try:
                return llm.invoke(input, ...)   # tenta o primário
            except Exception as exc:
                if not _is_transient(exc): raise
                time.sleep(backoff_exponencial) # espera e tenta de novo
                # após N tentativas, usa fallback se configurado

    def bind_tools(self, tools, **kwargs):
        # propaga bind_tools para o LLM real e preserva o wrapper
        primary_bound = self._primary.bind_tools(tools, **kwargs)
        fallback_bound = self._fallback.bind_tools(tools, **kwargs) if self._fallback else None
        return _ThrottledLLM(primary_bound, fallback_bound)

    def __getattr__(self, name):
        return getattr(self._primary, name)     # delega atributos para o LLM real
```

> **Por que herdar de `Runnable` e não de uma classe Pydantic?**
> `AgentExecutor` chama `bind_tools` no LLM internamente. Se o wrapper fosse Pydantic,
> `__setattr__` impediria a troca de estado. Herdar de `Runnable` resolve isso.

**Variáveis de ambiente relevantes:**

| Variável | Propósito |
|----------|-----------|
| `LLM_MODEL` | Modelo principal (ex: `gemini-2.5-flash`) |
| `LLM_FALLBACK_MODEL` | Modelo alternativo para erros 503 persistentes |
| `LLM_FALLBACK_AFTER` | Nº de tentativas antes de acionar o fallback (padrão: 3) |
| `LLM_RPM` | Requests por minuto — rate limiter (padrão: 10) |
| `LLM_MAX_RETRIES` | Tentativas totais por chamada (padrão: 8) |
| `LLM_RETRY_BASE_DELAY` | Delay base em segundos para backoff exponencial (padrão: 15) |
| `LLM_RETRY_MAX_DELAY` | Teto do delay de backoff (padrão: 120) |

---

### Passo 3 — Implemente `tools.py` (se houver sistema externo)

Se algum agente precisa chamar uma API ou persistir dados, crie uma `BaseTool`.

**Estrutura obrigatória:**

```python
class MinhaFerramenta(BaseTool):
    name: str = "nome_da_ferramenta"          # como o LLM chama a tool
    description: str = "..."                  # o LLM decide quando usar baseado nisso
    args_schema: type[BaseModel] = MeuInput   # valida e normaliza o input do LLM

    def _run(self, campo1: str, campo2: int, ...) -> str:
        # Faz a chamada ao sistema externo
        # Retorna string descritiva (o LLM lê esse retorno para continuar)
        ...
```

**Padrão de Schema com normalização de campo:**

O LLM pode enviar campos em formatos inconsistentes (`titulo`, `Titulo`, `title`...). Use `model_validator` para normalizar antes de validar:

```python
class MeuInput(BaseModel):
    titulo: str
    tipo: str

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data):
        key_map = {
            "titulo": "titulo", "title": "titulo", "Title": "titulo",
            "tipo": "tipo", "type": "tipo", "Type": "tipo",
        }
        return {key_map[k]: v for k, v in data.items() if k in key_map}
```

**Padrão Registry (anti-hallucination de IDs):**

Quando agentes subsequentes precisam referenciar IDs criados por agentes anteriores, o LLM pode alucinar IDs inexistentes. Use um Registry global para validar:

```python
# Instância global — compartilhada entre todos os agentes
registry = MeuRegistry()

class MinhaFerramenta(BaseTool):
    def _run(self, parent_id: int, ...):
        # Antes de criar, valida se o parent_id existe
        if parent_id not in registry.get_ids("TipoPai"):
            return f"ERRO: ID {parent_id} não existe. IDs válidos: {registry.format_valid_ids('TipoPai')}"

        # Após criar com sucesso, registra o novo ID
        novo_id = chamar_api(...)
        registry.register("MeuTipo", novo_id, titulo, parent_id)
        return f"SUCESSO: criado ID={novo_id}. Para criar filhos, use parent_id={novo_id}"
```

> O retorno da tool precisa ser **informativo e orientado à ação** — o LLM lê essa string e decide o que fazer na próxima iteração.

---

### Passo 4 — Implemente `agents/_base.py`

Centraliza dois elementos reutilizáveis:

**`Agent`** — wrapper fino que padroniza a interface de invocação:

```python
class Agent:
    __slots__ = ("role", "_runner")

    def __init__(self, role: str, runner: Any) -> None:
        self.role = role
        self._runner = runner

    def invoke(self, inputs: dict) -> str:
        result = self._runner.invoke(inputs)
        # AgentExecutor retorna dict; LCEL chain retorna str
        if isinstance(result, dict):
            return result.get("output", str(result))
        return str(result)
```

**`make_tool_agent`** — factory que elimina o boilerplate de criar `AgentExecutor`:

```python
def make_tool_agent(role: str, llm, tool, system: str, max_iterations: int = 15) -> Agent:
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),  # obrigatório para tool-calling
    ])
    executor = AgentExecutor(
        agent=create_tool_calling_agent(llm, [tool], prompt),
        tools=[tool],
        verbose=False,
        max_iterations=max_iterations,
        handle_parsing_errors=True,
    )
    return Agent(role=role, runner=executor)
```

> `{agent_scratchpad}` é o espaço onde o LLM registra chamadas de tool e respostas intermediárias. É obrigatório para tool-calling funcionar.

---

### Passo 5 — Implemente cada agente

Cada arquivo de agente tem exatamente a mesma estrutura, variando apenas os prompts e parâmetros:

```
agents/meu_agente.py
├── _SYSTEM      # system prompt: quem é o agente, suas regras e restrições
├── _TASK_TEMPLATE  # human prompt: o que fazer, formato de saída esperado
├── create_xxx_agent(llm, tool?) → Agent    # factory
└── executar_xxx(agent, inputs...) → str    # executa a tarefa
```

**Dois padrões de agente:**

#### Agente simples (sem tools) — usa LCEL

Use quando o agente só precisa do LLM, sem chamar sistemas externos:

```python
def create_meu_agente(llm) -> Agent:
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        ("human", "{input}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return Agent(role="Meu Agente", runner=chain)

def executar_tarefa(agent: Agent, contexto: str) -> str:
    return agent.invoke({"input": _TASK_TEMPLATE.format(contexto=contexto)})
```

#### Agente com tool-calling — usa `make_tool_agent`

Use quando o agente precisa chamar uma API ou persistir dados:

```python
def create_meu_agente(llm, tool: MinhaFerramenta) -> Agent:
    return make_tool_agent("Meu Agente", llm, tool, _SYSTEM, max_iterations=15)

def executar_tarefa(agent: Agent, contexto: str) -> str:
    return agent.invoke({"input": _TASK_TEMPLATE.format(contexto=contexto)})
```

**Como calibrar `max_iterations`:**

| Situação | Valor sugerido |
|----------|----------------|
| Agente cria 1 item | 5–8 |
| Agente cria 2-3 itens | 10–15 |
| Agente cria até 15 itens | 25–35 |
| Agente cria 50+ itens | 80–120 |

Cada tool-call consome 2 iterações (chamada + resposta). Margem de 20% é recomendada.

**Como escrever bons prompts para tool-calling:**

No `_SYSTEM`:
- Defina claramente o papel e o que o agente **nunca** deve fazer
- Especifique o formato de saída esperado após cada tool-call
- Indique regras de validação que o agente deve respeitar (ex: use o `parent_id` exato)

No `_TASK_TEMPLATE`:
- Comece com o contexto do que já foi feito nas etapas anteriores
- Liste os campos obrigatórios e seus formatos
- Adicione o formato de saída de cada item criado (facilita rastreabilidade no log)
- Termine com os dados de entrada encapsulados em seções nomeadas

---

### Passo 6 — Implemente `workflow.py`

O orquestrador é Python puro — sem framework de grafo ou orquestração:

```python
def main():
    validate_config()

    # 1. Carrega a entrada
    specification = load_specification(sys.argv[1] if len(sys.argv) > 1 else None)

    # 2. Instancia infraestrutura
    llm  = create_llm()
    tool = MinhaFerramenta()

    # 3. Instancia agentes
    agente_a = create_agente_a(llm)
    agente_b = create_agente_b(llm, tool)
    agente_c = create_agente_c(llm, tool)

    # 4. Executa o pipeline — cada etapa recebe o output da anterior
    output_a = executar_a(agente_a, specification)
    output_b = executar_b(agente_b, output_a)
    output_c = executar_c(agente_c, output_b, specification)  # pode repassar inputs anteriores

    print(output_c)
```

> **Por que não usar LangGraph aqui?**
> Para pipelines lineares sem ciclos, branches ou checkpoints, o grafo é over-engineering.
> O valor do LangGraph aparece quando você precisa de: retomar do ponto de falha sem reiniciar tudo,
> ciclos de reflexão/correção, ou paralelismo entre nós.

---

### Passo 7 — Configure `agents/__init__.py`

Re-exporte tudo que o `workflow.py` precisa importar:

```python
from agents._base import Agent
from agents.agente_a import create_agente_a, executar_a
from agents.agente_b import create_agente_b, executar_b

__all__ = [
    "Agent",
    "create_agente_a", "executar_a",
    "create_agente_b", "executar_b",
]
```

---

## Diagrama de Dependências

```
workflow.py
    ├── config.py           → LLM (com rate limit + retry)
    ├── tools.py            → BaseTool + Registry
    └── agents/
        ├── __init__.py     → re-exporta tudo
        ├── _base.py        → Agent, make_tool_agent
        ├── bic.py          → usa: _base, config(llm)
        ├── mimi.py         → usa: _base, tools
        ├── givaldo.py      → usa: _base, tools
        └── jaiminho.py     → usa: _base, tools
```

A `tools.py` é **importada pelos agentes**, não pelo `workflow.py` diretamente. O `workflow.py` só instancia a tool e passa como argumento.

---

## Checklist para Criar um Novo Pipeline

```
[ ] Definir quantas etapas o pipeline tem e o papel de cada uma
[ ] Criar config.py com validate_config() e create_llm()
[ ] Criar .env.example com todas as variáveis documentadas
[ ] Criar tools.py se algum agente precisa de sistema externo
    [ ] BaseTool com name, description, args_schema, _run()
    [ ] WorkItemRegistry (ou equivalente) se IDs são passados entre agentes
    [ ] model_validator no schema para normalizar campos do LLM
[ ] Criar agents/_base.py com classe Agent e make_tool_agent
[ ] Para cada agente, criar agents/nome_agente.py com:
    [ ] _SYSTEM prompt
    [ ] _TASK_TEMPLATE prompt
    [ ] create_xxx_agent() usando LCEL ou make_tool_agent
    [ ] executar_xxx() que chama agent.invoke() com o template formatado
[ ] Criar agents/__init__.py re-exportando tudo
[ ] Criar workflow.py chamando os agentes em sequência
[ ] Criar specs/ com ao menos um exemplo de input
[ ] Criar Dockerfile com usuário não-root
[ ] Criar requirements.txt com versões fixadas (>=X,<Y)
```

---

## Armadilhas Conhecidas e Como Evitar

| Problema | Causa | Solução |
|----------|-------|---------|
| LLM alucina `parent_id` | LLM inventa IDs que não existem | `WorkItemRegistry` valida antes de chamar a API e retorna IDs válidos no erro |
| Tool-calling não funciona | Falta `{agent_scratchpad}` no prompt | Sempre incluir `("placeholder", "{agent_scratchpad}")` no `ChatPromptTemplate` |
| `bind_tools` falha no wrapper | Wrapper herda de Pydantic | Herdar de `Runnable` e implementar `bind_tools` manualmente |
| Erros 503 frequentes | Rate limit do provider | `_ThrottledLLM` com RPM + retry exponencial + fallback de modelo |
| Agente para no meio da execução | `max_iterations` baixo | Calcular: (nº máximo de itens × 2) + margem de 20% |
| LLM usa Markdown em vez de HTML | System prompt insuficiente | Adicionar "Nunca Markdown" e listar tags HTML permitidas no system prompt |
| Campos em formatos variados | LLM não é consistente no naming | `model_validator` com `key_map` normalizando PascalCase, camelCase e snake_case |

---

## Dependências do Projeto

```
langchain>=0.3.0,<3.0          # AgentExecutor, create_tool_calling_agent
langchain-core>=0.3.0,<3.0     # ChatPromptTemplate, BaseTool, Runnable, StrOutputParser
langchain-google-genai>=2.0.0  # ChatGoogleGenerativeAI
requests>=2.31.0               # chamadas HTTP à API externa
python-dotenv>=1.0.1           # carregamento do .env
```

Para trocar de provider de LLM, substitua `langchain-google-genai` pelo pacote correspondente
(ex: `langchain-openai`, `langchain-anthropic`) e ajuste `create_llm()` em `config.py`.
