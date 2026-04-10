import sys
import os
import logging
import time
import random
from pathlib import Path
from dotenv import load_dotenv

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
_KNOWN_PROVIDERS = {"ollama", "gemini", "openai", "anthropic"}


def _detect_provider(model: str) -> str:
    prefix = model.split("/")[0]
    if prefix in _KNOWN_PROVIDERS:
        return prefix
    for provider in _KNOWN_PROVIDERS:
        if provider in model.lower():
            logger.warning(
                "Prefixo '%s' não reconhecido. Detectado '%s' pelo nome do modelo.",
                prefix, provider,
            )
            return provider
    return prefix


def _model_name(model: str) -> str:
    """Remove o prefixo do provider: 'gemini/gemini-2.5-flash' → 'gemini-2.5-flash'."""
    parts = model.split("/", 1)
    return parts[1] if len(parts) == 2 and parts[0] in _KNOWN_PROVIDERS else model


PROVIDER = _detect_provider(LLM_MODEL)

# ── Configurações específicas por provider ──
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "8192"))

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


def _build_raw_llm(model: str):
    """Cria um LangChain BaseChatModel sem rate limiting."""
    name = _model_name(model)
    provider = _detect_provider(model)

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=name, base_url=OLLAMA_BASE, num_ctx=LLM_NUM_CTX)
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=name)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=name)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=name)
    else:
        raise ValueError(
            f"Provider '{provider}' não suportado. Use: ollama, gemini, openai ou anthropic.\n"
            f"Formato esperado em LLM_MODEL: <provider>/<modelo>  ex: gemini/gemini-2.5-flash"
        )


def _wrap_with_rate_limit(llm):
    """Envolve llm.invoke com rate limiting, retry exponencial e fallback de modelo."""
    original_invoke = llm.invoke

    # Cria LLM de fallback se configurado
    fallback_invoke = None
    if _FALLBACK_MODEL:
        try:
            _fallback_llm = _build_raw_llm(_FALLBACK_MODEL)
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
            model_label = _FALLBACK_MODEL if use_fallback else LLM_MODEL

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
    """Cria e retorna o LangChain BaseChatModel configurado com rate limiting e retry."""
    llm = _build_raw_llm(LLM_MODEL)
    if PROVIDER != "ollama":
        llm = _wrap_with_rate_limit(llm)
    else:
        logger.info("Ollama local: rate limiting desativado")
    return llm


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
_KNOWN_PROVIDERS = {"ollama", "gemini", "openai", "anthropic"}

def _detect_provider(model: str) -> str:
    prefix = model.split("/")[0]
    if prefix in _KNOWN_PROVIDERS:
        return prefix
    # Fallback: detecta pelo nome do modelo se o prefixo não for reconhecido
    for provider in _KNOWN_PROVIDERS:
        if provider in model.lower():
            logger.warning(
                "Prefixo '%s' não reconhecido. Detectado '%s' pelo nome do modelo. "
                "Recomendado usar formato: %s/%s",
                prefix, provider, provider, model,
            )
            return provider
    return prefix

PROVIDER = _detect_provider(LLM_MODEL)

# ── Configurações específicas por provider ──
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Ollama: contexto menor = respostas mais rápidas. Aumente se a spec for muito grande.
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "8192"))

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

# Retry config para erros transientes (503, 429, etc.)
# 503 "high demand" do Gemini pode durar minutos — defaults conservadores
_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "6"))
_RETRY_BASE_DELAY = int(os.getenv("LLM_RETRY_BASE_DELAY", "10"))  # segundos
_RETRY_MAX_DELAY = int(os.getenv("LLM_RETRY_MAX_DELAY", "60"))   # teto do backoff


def _wrap_with_rate_limit(llm):
    """Envolve o método call() do LLM com rate limiting e retry para erros transientes."""
    original_call = llm.call

    def _throttled_call(*args, **kwargs):
        _rate_limiter.wait_if_needed()

        last_exception = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return original_call(*args, **kwargs)
            except Exception as exc:
                exc_str = str(exc)
                _TRANSIENT = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "high demand", "overloaded", "quota")
                is_transient = any(code in exc_str for code in _TRANSIENT)
                if not is_transient or attempt == _MAX_RETRIES:
                    raise
                last_exception = exc
                # Exponential backoff com jitter e teto para evitar esperas infinitas
                base = min(_RETRY_BASE_DELAY * (2 ** (attempt - 1)), _RETRY_MAX_DELAY)
                delay = base + random.uniform(0, min(base * 0.3, 5))
                logger.warning(
                    "[RETRY] Erro transiente (tentativa %d/%d). Aguardando %.1fs (base=%ds, teto=%ds)... | %s",
                    attempt, _MAX_RETRIES, delay, base, _RETRY_MAX_DELAY, exc_str[:120],
                )
                time.sleep(delay)
                _rate_limiter.wait_if_needed()

        raise last_exception  # pragma: no cover

    llm.call = _throttled_call
    logger.info(
        "Rate limiting ativo: %d RPM | Retry: até %d tentativas | backoff: %ds–%ds",
        LLM_RPM, _MAX_RETRIES, _RETRY_BASE_DELAY, _RETRY_MAX_DELAY,
    )
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
