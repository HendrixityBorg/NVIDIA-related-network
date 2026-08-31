from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path

from .agent_plan import build_agent_tasks
from .contracts import ResearchProfile, SubjectIdentity
from .discovery import plan_search_queries, seed_candidates
from .io import write_document, write_jsonl


RUN_DIRECTORIES = [
    "discovery",
    "stage_reports",
    "normalized",
    "review",
    "agent_tasks",
    "artifacts",
]


def initialise_run(
    profile: ResearchProfile, run_root: Path, *, overwrite: bool = False
) -> None:
    if run_root.exists() and any(run_root.iterdir()) and not overwrite:
        raise FileExistsError(f"run directory is not empty: {run_root}")
    for directory in RUN_DIRECTORIES:
        (run_root / directory).mkdir(parents=True, exist_ok=True)
    write_document(run_root / "profile.yaml", profile.model_dump(mode="json"))
    write_jsonl(
        run_root / "discovery/source_candidates.jsonl",
        [item.model_dump(mode="json") for item in seed_candidates(profile)],
    )
    write_jsonl(
        run_root / "discovery/search_queries.jsonl",
        [item.model_dump(mode="json") for item in plan_search_queries(profile)],
    )
    for task in build_agent_tasks(profile):
        write_document(
            run_root / f"agent_tasks/{task.agent}.json",
            task.model_dump(mode="json"),
        )
    for relative in (
        "discovery/source_frontier.jsonl",
        "normalized/entities.jsonl",
        "normalized/sources.jsonl",
        "normalized/evidence.jsonl",
        "normalized/relationships.jsonl",
        "review/counterparty_tasks.jsonl",
        "review/counterparty_decisions.jsonl",
    ):
        (run_root / relative).touch(exist_ok=True)


def profile_from_subject(
    subject: SubjectIdentity,
    *,
    project_slug: str,
    cutoff_date: date,
    evidence_start_date: date,
) -> ResearchProfile:
    return ResearchProfile(
        project_slug=project_slug,
        target=subject,
        cutoff_at=datetime.combine(cutoff_date, time(23, 59, 59), tzinfo=timezone.utc),
        evidence_start_date=evidence_start_date,
        snapshot_version=f"{project_slug}-{cutoff_date.isoformat()}",
        coverage=[
            "supplier、customer、partner、investor_or_investee、peer",
            "目标公司年报、适用的持仓申报、近两年 IR/新闻、产品与生态网络",
            "第三方新闻线索与全部上市对手方的监管/IR 反向复核",
        ],
        exclusions=[
            "非上市对手方不进入最终关系图",
            "受登录、付费墙、验证码、robots 或限流控制的正文不抓取",
            "未公开关系、个人数据、客户机密及未经授权原始材料",
        ],
    )
