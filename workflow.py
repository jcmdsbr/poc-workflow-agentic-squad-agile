import sys
import os
import logging
from datetime import datetime, timezone
from crewai import Crew, Process

from config import validate_config, create_llm, load_specification, LLM_MODEL, PROVIDER
from tools import AzureDevOpsTool
from agents import (
    create_bic_agent,
    create_architecture_task,
    create_mimi_agent,
    create_features_task,
    create_givaldo_agent,
    create_stories_task,
    create_jaiminho_agent,
    create_tasks_task,
)

logger = logging.getLogger("workflow")


def main():
    validate_config()

    spec_path = sys.argv[1] if len(sys.argv) > 1 else None
    specification = load_specification(spec_path)

    logger.info("=" * 60)
    logger.info("PIPELINE DE AGENTES — INÍCIO")
    logger.info("=" * 60)
    logger.info("Provider: %s | Modelo: %s", PROVIDER, LLM_MODEL)
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

    # Tasks (encadeadas via context)
    architecture_task = create_architecture_task(bic, specification)
    features_task = create_features_task(mimi, architecture_task)
    stories_task = create_stories_task(givaldo, features_task)
    tasks_task = create_tasks_task(jaiminho, stories_task)

    all_agents = [bic, mimi, givaldo, jaiminho]
    all_tasks = [architecture_task, features_task, stories_task, tasks_task]

    for i, (task, agent) in enumerate(zip(all_tasks, all_agents), 1):
        logger.info("Etapa %d: [%s] → %s", i, agent.role, task.expected_output)

    logger.info("-" * 60)

    crew = Crew(
        agents=all_agents,
        tasks=all_tasks,
        process=Process.sequential,
        verbose=False,
    )

    start = datetime.now(timezone.utc)
    result = crew.kickoff()
    elapsed = datetime.now(timezone.utc) - start

    logger.info("=" * 60)
    logger.info("PIPELINE CONCLUÍDO em %s", str(elapsed).split(".")[0])
    logger.info("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
