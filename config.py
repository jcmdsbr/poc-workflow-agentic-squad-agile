import sys
import os
import logging
import time
import random
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("config")

# ── Modelo Gemini ──
# Aceita "gemini-2.5-flash" ou "gemini/gemini-2.5-flash" (remove prefixo se presente)
_raw_model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
LLM_MODEL = _raw_model.split("/", 1)[1] if _raw_model.startswith("gemini/") else _raw_model
PROVIDER = "gemini"

# Rate limiting: requests por minuto
LLM_RPM = int(os.getenv("LLM_RPM", "10"))


def validate_config():
    required = ["AZURE_ORG", "AZURE_PROJECT", "AZURE_PAT", "GEMINI_API_KEY"]

    missing = [v for v in required if not os.getenv(v)]
    if missing:
        sys.exit(
            f"Variáveis de ambiente obrigatórias não definidas: {', '.join(missing)}\n"
            f"Copie .env.example para .env e preencha os valores."
        )

    logger.info("Modelo: %s | RPM: %s", LLM_MODEL, LLM_RPM)


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

# Retry config para erros transientes (503, 429, etc.)
_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "8"))
_RETRY_BASE_DELAY = int(os.getenv("LLM_RETRY_BASE_DELAY", "15"))  # segundos
_RETRY_MAX_DELAY = int(os.getenv("LLM_RETRY_MAX_DELAY", "120"))   # teto do backoff

# Fallback: modelo alternativo ativado quando o modelo primário continua em 503
_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "")
_FALLBACK_AFTER = int(os.getenv("LLM_FALLBACK_AFTER", "3"))  # tentativas antes de alternar

_TRANSIENT_ERRORS = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "high demand", "overloaded", "quota")


def _is_transient(exc: Exception) -> bool:
    return any(code in str(exc) for code in _TRANSIENT_ERRORS)


class _ThrottledLLM(Runnable):
    """Wrapper sobre ChatGoogleGenerativeAI com rate limiting, retry e fallback.

    Herda de Runnable (não Pydantic) para suportar | e bind_tools sem
    restrições de __setattr__.
    """

    def __init__(self, primary, fallback=None):
        self._primary = primary
        self._fallback = fallback

    def invoke(self, input, config=None, **kwargs):
        _rate_limiter.wait_if_needed()

        last_exc = None
        for attempt in range(1, _MAX_RETRIES + 1):
            use_fallback = self._fallback is not None and attempt > _FALLBACK_AFTER
            llm = self._fallback if use_fallback else self._primary
            model_label = _FALLBACK_MODEL if use_fallback else LLM_MODEL

            try:
                if use_fallback and attempt == _FALLBACK_AFTER + 1:
                    logger.warning("[FALLBACK] Alternando para: %s", _FALLBACK_MODEL)
                return llm.invoke(input, config, **kwargs)
            except Exception as exc:
                if not _is_transient(exc) or attempt == _MAX_RETRIES:
                    raise
                last_exc = exc
                base = min(_RETRY_BASE_DELAY * (2 ** (attempt - 1)), _RETRY_MAX_DELAY)
                delay = base + random.uniform(0, min(base * 0.3, 10))
                logger.warning(
                    "[RETRY %d/%d] [%s] Aguardando %.1fs | %s",
                    attempt, _MAX_RETRIES, model_label, delay, str(exc)[:120],
                )
                time.sleep(delay)
                _rate_limiter.wait_if_needed()

        raise last_exc  # pragma: no cover

    def bind_tools(self, tools, **kwargs):
        """Vincula tools e preserva o wrapping de rate limiting."""
        primary_bound = self._primary.bind_tools(tools, **kwargs)
        fallback_bound = self._fallback.bind_tools(tools, **kwargs) if self._fallback else None
        return _ThrottledLLM(primary_bound, fallback_bound)

    def __getattr__(self, name: str):
        return getattr(self._primary, name)


def create_llm() -> _ThrottledLLM:
    api_key = os.getenv("GEMINI_API_KEY")
    primary = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=api_key)

    fallback = None
    if _FALLBACK_MODEL:
        try:
            fallback = ChatGoogleGenerativeAI(model=_FALLBACK_MODEL, google_api_key=api_key)
        except Exception as exc:
            logger.warning("Não foi possível criar fallback '%s': %s", _FALLBACK_MODEL, exc)

    logger.info(
        "Rate limiting: %d RPM | Retry: %d tentativas | backoff: %ds–%ds | Fallback: %s",
        LLM_RPM, _MAX_RETRIES, _RETRY_BASE_DELAY, _RETRY_MAX_DELAY,
        _FALLBACK_MODEL or "não configurado",
    )
    return _ThrottledLLM(primary, fallback)


_MAX_SPEC_CHARS = int(os.getenv("MAX_SPEC_CHARS", str(50_000)))


def load_specification(path: str | None) -> str:
    if path:
        content = Path(path).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        content = sys.stdin.read()
    else:
        sys.exit(
            "Uso: python workflow.py <arquivo_especificacao.md>\n"
            " ou: cat spec.md | python workflow.py"
        )
    if len(content) > _MAX_SPEC_CHARS:
        logger.warning(
            "Especificação com %d caracteres excede o limite recomendado de %d. "
            "Isso pode ultrapassar o context window do LLM e degradar a qualidade.",
            len(content), _MAX_SPEC_CHARS,
        )
    return content

