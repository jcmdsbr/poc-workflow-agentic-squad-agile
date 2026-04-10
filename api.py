import uuid
import logging
from enum import Enum
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from config import validate_config, MAX_SPEC_CHARS

logger = logging.getLogger("api")

app = FastAPI(
    title="Agent Pipeline API",
    description="Executa o pipeline de agentes a partir de uma especificação funcional.",
    version="1.0.0",
)

# ── Job store in-memory (POC) ─────────────────────────────────────────────────

class JobStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class Job(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    finished_at: str | None = None
    result: str | None = None
    error: str | None = None


_jobs: dict[str, Job] = {}
_executor = ThreadPoolExecutor(max_workers=4)

# ── Request / Response schemas ────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    specification: str = Field(
        ...,
        description="Especificação funcional em texto livre (Markdown recomendado).",
        min_length=10,
    )


class PipelineResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_job(job_id: str, specification: str) -> None:
    """Executa o pipeline em background e atualiza o job store."""
    from workflow import run_pipeline  # Import tardio para evitar ciclo na inicialização

    job = _jobs[job_id]
    try:
        result = run_pipeline(specification)
        _jobs[job_id] = job.model_copy(update={
            "status": JobStatus.completed,
            "result": result,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        logger.error("Job %s falhou: %s", job_id, exc)
        _jobs[job_id] = job.model_copy(update={
            "status": JobStatus.failed,
            "error": str(exc),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })


def _create_job(specification: str) -> str:
    if len(specification) > MAX_SPEC_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"Especificação excede o limite de {MAX_SPEC_CHARS} caracteres.",
        )
    job_id = str(uuid.uuid4())
    _jobs[job_id] = Job(
        job_id=job_id,
        status=JobStatus.running,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _executor.submit(_run_job, job_id, specification)
    logger.info("Job %s criado (%d chars)", job_id, len(specification))
    return job_id


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    validate_config()
    logger.info("API iniciada — pipeline pronto.")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post(
    "/pipeline",
    response_model=PipelineResponse,
    status_code=202,
    summary="Inicia o pipeline com uma especificação em texto",
)
async def start_pipeline(body: PipelineRequest):
    """
    Recebe a especificação funcional como texto e inicia o pipeline de agentes.
    Retorna um `job_id` para acompanhar o status via `GET /pipeline/{job_id}`.
    """
    job_id = await run_in_threadpool(_create_job, body.specification)
    return PipelineResponse(
        job_id=job_id,
        status=JobStatus.running,
        message="Pipeline iniciado. Consulte GET /pipeline/{job_id} para o resultado.",
    )


@app.post(
    "/pipeline/upload",
    response_model=PipelineResponse,
    status_code=202,
    summary="Inicia o pipeline fazendo upload de um arquivo de especificação",
)
async def start_pipeline_upload(file: UploadFile = File(..., description="Arquivo de especificação (.md ou .txt)")):
    """
    Recebe a especificação funcional como arquivo (`.md` ou `.txt`) e inicia o pipeline.
    """
    content = await file.read()
    try:
        specification = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Arquivo deve estar em UTF-8.")

    job_id = await run_in_threadpool(_create_job, specification)
    return PipelineResponse(
        job_id=job_id,
        status=JobStatus.running,
        message="Pipeline iniciado. Consulte GET /pipeline/{job_id} para o resultado.",
    )


@app.get(
    "/pipeline/{job_id}",
    response_model=Job,
    summary="Consulta o status e resultado de um job",
)
async def get_pipeline_status(job_id: str):
    """Retorna o status atual do job. Quando `status=completed`, o campo `result` contém a saída do pipeline."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    return job


@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok"}
