from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_tool_calling_agent, AgentExecutor


class Agent:
    """Wrapper leve em torno de um LangChain chain ou AgentExecutor."""

    __slots__ = ("role", "_runner")

    def __init__(self, role: str, runner: Any) -> None:
        self.role = role
        self._runner = runner

    def invoke(self, inputs: dict) -> str:
        result = self._runner.invoke(inputs)
        if isinstance(result, dict):
            return result.get("output", str(result))
        return str(result)


def make_tool_agent(role: str, llm, tool, system: str, max_iterations: int = 15) -> Agent:
    """Cria um Agent com tool-calling (AgentExecutor) a partir de um system prompt."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    executor = AgentExecutor(
        agent=create_tool_calling_agent(llm, [tool], prompt),
        tools=[tool],
        verbose=False,
        max_iterations=max_iterations,
        handle_parsing_errors=True,
    )
    return Agent(role=role, runner=executor)
