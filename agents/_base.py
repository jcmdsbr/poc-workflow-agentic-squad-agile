from typing import Any


class Agent:
    """Wrapper leve em torno de um LangChain chain ou AgentExecutor."""

    __slots__ = ("role", "_runner")

    def __init__(self, role: str, runner: Any) -> None:
        self.role = role
        self._runner = runner

    def invoke(self, inputs: dict) -> Any:
        return self._runner.invoke(inputs)
