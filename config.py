import sys
import os
import logging
import time
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

logger = logging.getLogger("config")

# ── Modelo ──
LLM_MODEL = os.getenv("LLM_MODEL", "ollama/llama3.1")

# ── Detecção automática de provider pelo prefixo do modelo ──
PROVIDER = LLM_MODEL.split("/")[0]  # "ollama", "gemini", "openai", etc.

# ── Configurações específicas por provider ──
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "32768"))

# Rate limiting: requests por minuto (0 = sem limite, ex: Ollama local)
_DEFAULT_RPM = {"ollama": 0, "gemini": 10, "openai": 30, "anthropic": 30}
LLM_RPM = int(os.getenv("LLM_RPM", str(_DEFAULT_RPM.get(PROVIDER, 15))))

# Mapa de env vars obrigatórias por provider
_PROVIDER_KEY_MAP = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def validate_config():
    required = ["AZURE_ORG", "AZURE_PROJECT", "AZURE_PAT"]

    # Adiciona a key do provider se for hospedado
    provider_key = _PROVIDER_KEY_MAP.get(PROVIDER)
    if provider_key:
        required.append(provider_key)

    missing = [v for v in required if not os.getenv(v)]
    if missing:
        sys.exit(
            f"Variáveis de ambiente obrigatórias não definidas: {', '.join(missing)}\n"
            f"Copie .env.example para .env e preencha os valores."
        )

    logger.info("Provider: %s | Modelo: %s | RPM: %s", PROVIDER, LLM_MODEL, LLM_RPM or "ilimitado")


class _RateLimiter:
    """Throttle simples baseado em janela deslizante de 60s."""

    def __init__(self, max_rpm: int):
        self.max_rpm = max_rpm
        self._timestamps: list[float] = []

    def wait_if_needed(self):
        if self.max_rpm <= 0:
            return
        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < 60]
        if len(self._timestamps) >= self.max_rpm:
            sleep_for = 60 - (now - self._timestamps[0]) + 0.5
            logger.info("[RATE-LIMIT] Aguardando %.1fs para respeitar %d RPM...", sleep_for, self.max_rpm)
            time.sleep(sleep_for)
        self._timestamps.append(time.time())


_rate_limiter = _RateLimiter(LLM_RPM)


def _wrap_with_rate_limit(llm):
    """Envolve o método call() do LLM com rate limiting."""
    if LLM_RPM <= 0:
        return llm

    original_call = llm.call

    def _throttled_call(*args, **kwargs):
        _rate_limiter.wait_if_needed()
        return original_call(*args, **kwargs)

    llm.call = _throttled_call
    logger.info("Rate limiting ativo: %d RPM", LLM_RPM)
    return llm


def create_llm() -> LLM:
    if PROVIDER == "ollama":
        return LLM(
            model=LLM_MODEL,
            base_url=OLLAMA_BASE,
            extra_body={"num_ctx": LLM_NUM_CTX},
        )

    # Providers hospedados (Gemini, OpenAI, Anthropic, etc.)
    llm = LLM(model=LLM_MODEL)
    return _wrap_with_rate_limit(llm)


def load_specification(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    sys.exit(
        "Uso: python workflow.py <arquivo_especificacao.md>\n"
        " ou: cat spec.md | python workflow.py"
    )
