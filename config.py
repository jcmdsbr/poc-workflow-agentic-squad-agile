import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "32768"))


def validate_config():
    required = ["AZURE_ORG", "AZURE_PROJECT", "AZURE_PAT"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        sys.exit(
            f"Variáveis de ambiente obrigatórias não definidas: {', '.join(missing)}\n"
            f"Copie .env.example para .env e preencha os valores."
        )


def create_llm() -> LLM:
    kwargs: dict = {"model": LLM_MODEL}

    # Ollama local precisa de base_url e num_ctx
    if OLLAMA_BASE:
        kwargs["base_url"] = OLLAMA_BASE
        kwargs["extra_body"] = {"num_ctx": LLM_NUM_CTX}

    return LLM(**kwargs)


def load_specification(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    sys.exit(
        "Uso: python workflow.py <arquivo_especificacao.md>\n"
        " ou: cat spec.md | python workflow.py"
    )
