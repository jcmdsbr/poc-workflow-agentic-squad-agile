import sys
import os
import logging
import time
import random
from pathlib import Path
from dotenv import load_dotenv
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
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
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


def _wrap_with_rate_limit(llm):
    """Envolve llm.invoke com rate limiting, retry exponencial e fallback de modelo."""
    original_invoke = llm.invoke

    # Cria LLM de fallback se configurado
    fallback_invoke = None
    if _FALLBACK_MODEL:
        try:
            _fallback_llm = ChatGoogleGenerativeAI(model=_FALLBACK_MODEL)
            fallback_invoke = _fallback_llm.invoke
            logger.info(
                "Fallback model configurado: %s (ativado após %d falhas consecutivas)",
                _FALLBACK_MODEL, _FALLBACK_AFTER,
            )
        except Exception as exc:
            logger.warning("Não foi possível criar fallback LLM '%s': %s", _FALLBACK_MODEL, exc)

    def _throttled_invoke(*args, **kwargs):
        _rate_limiter.wait_if_needed()

        last_exception = None
        for attempt in range(1, _MAX_RETRIES + 1):
            use_fallback = fallback_invoke is not None and attempt > _FALLBACK_AFTER
            call_fn = fallback_invoke if use_fallback else original_invoke
            model_label = _FALLBACK_MODEL if use_fallback else f"gemini/{LLM_MODEL}"

            try:
                if use_fallback and attempt == _FALLBACK_AFTER + 1:
                    logger.warning("[FALLBACK] Alternando para: %s", _FALLBACK_MODEL)
                return call_fn(*args, **kwargs)
            except Exception as exc:
                if not _is_transient(exc) or attempt == _MAX_RETRIES:
                    raise
                last_exception = exc
                base = min(_RETRY_BASE_DELAY * (2 ** (attempt - 1)), _RETRY_MAX_DELAY)
                delay = base + random.uniform(0, min(base * 0.3, 10))
                logger.warning(
                    "[RETRY %d/%d] [%s] Aguardando %.1fs | %s",
                    attempt, _MAX_RETRIES, model_label, delay, str(exc)[:120],
                )
                time.sleep(delay)
                _rate_limiter.wait_if_needed()

        raise last_exception  # pragma: no cover

    llm.invoke = _throttled_invoke
    logger.info(
        "Rate limiting: %d RPM | Retry: %d tentativas | backoff: %ds–%ds | Fallback: %s",
        LLM_RPM, _MAX_RETRIES, _RETRY_BASE_DELAY, _RETRY_MAX_DELAY,
        _FALLBACK_MODEL or "não configurado",
    )
    return llm


def create_llm():
    """Cria e retorna o ChatGoogleGenerativeAI configurado com rate limiting e retry."""
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL)
    return _wrap_with_rate_limit(llm)


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

