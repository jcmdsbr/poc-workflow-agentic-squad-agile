import sys
import os
import logging
from datetime import datetime, timezone

from config import validate_config, create_llm, load_specification, LLM_MODEL
from tools import AzureDevOpsTool
from agents import (
    create_bic_agent, generate_architecture,
    create_mimi_agent, create_features,
    create_givaldo_agent, create_stories,
    create_jaiminho_agent, create_tasks,
)

logger = logging.getLogger("workflow")


def main():
    validate_config()

    spec_path = sys.argv[1] if len(sys.argv) > 1 else None
    specification = load_specification(spec_path)

    logger.info("=" * 60)
    logger.info("PIPELINE DE AGENTES — INÍCIO")
    logger.info("=" * 60)
    logger.info("Modelo: %s", LLM_MODEL)
    logger.info("Especificação: %s (%d caracteres)", spec_path or "stdin", len(specification))
    logger.info("Azure DevOps: org=%s, project=%s", os.getenv("AZURE_ORG"), os.getenv("AZURE_PROJECT"))
    logger.info("-" * 60)

    # Infraestrutura
    llm = create_llm()
    tool = AzureDevOpsTool()

    # Agentes
    bic = create_bic_agent(llm)
    mimi = create_mimi_agent(llm, tool)
    givaldo = create_givaldo_agent(llm, tool)
    jaiminho = create_jaiminho_agent(llm, tool)

    pipeline = [
        (bic,      "Documento de Arquitetura"),
        (mimi,     "Features no Azure DevOps"),
        (givaldo,  "User Stories no Azure DevOps"),
        (jaiminho, "Tasks no Azure DevOps"),
    ]
    for i, (agent, expected) in enumerate(pipeline, 1):
        logger.info("Etapa %d: [%s] → %s", i, agent.role, expected)
    logger.info("-" * 60)

    start = datetime.now(timezone.utc)
    try:
        logger.info("[1/4] %s — Arquitetura...", bic.role)
        arch_output = generate_architecture(bic, specification)

        logger.info("[2/4] %s — Features...", mimi.role)
        features_output = create_features(mimi, arch_output)

        logger.info("[3/4] %s — User Stories...", givaldo.role)
        stories_output = create_stories(givaldo, features_output, specification)

        logger.info("[4/4] %s — Tasks...", jaiminho.role)
        tasks_output = create_tasks(jaiminho, stories_output, specification)

    except Exception as exc:
        elapsed = datetime.now(timezone.utc) - start
        logger.error("=" * 60)
        logger.error("PIPELINE FALHOU após %s", str(elapsed).split(".")[0])
        logger.error("Erro: %s", exc)
        logger.error("=" * 60)
        raise

    elapsed = datetime.now(timezone.utc) - start
    logger.info("=" * 60)
    logger.info("PIPELINE CONCLUÍDO em %s", str(elapsed).split(".")[0])
    logger.info("=" * 60)
    print(tasks_output)


if __name__ == "__main__":
    main()

