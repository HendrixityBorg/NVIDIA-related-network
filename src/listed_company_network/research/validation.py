from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ..models import (
    Entity,
    Evidence,
    EvidenceRole,
    FactStatus,
    ListingStatus,
    RelationDirection,
    Relationship,
    Source,
)
from .contracts import (
    CompletionStatus,
    CounterpartyReviewDecision,
    CounterpartyReviewTask,
    ResearchProfile,
    StageReport,
    ValidationReport,
)
from .io import load_document, read_jsonl


NORMALIZED_FILES = {
    "entities": "normalized/entities.jsonl",
    "sources": "normalized/sources.jsonl",
    "evidence": "normalized/evidence.jsonl",
    "relationships": "normalized/relationships.jsonl",
}


def load_run_models(run_root: Path) -> tuple[
    list[Entity], list[Source], list[Evidence], list[Relationship]
]:
    return (
        [Entity.model_validate(row) for row in read_jsonl(run_root / NORMALIZED_FILES["entities"])],
        [Source.model_validate(row) for row in read_jsonl(run_root / NORMALIZED_FILES["sources"])],
        [Evidence.model_validate(row) for row in read_jsonl(run_root / NORMALIZED_FILES["evidence"])],
        [Relationship.model_validate(row) for row in read_jsonl(run_root / NORMALIZED_FILES["relationships"])],
    )


def _unique_ids(kind: str, rows: list, errors: list[str]) -> dict:
    ids = [row.id for row in rows]
    duplicates = [item for item, count in Counter(ids).items() if count > 1]
    if duplicates:
        errors.append(f"{kind} 存在重复 ID: {', '.join(sorted(duplicates)[:10])}")
    return {row.id: row for row in rows}


def _stage_reports(run_root: Path) -> dict[str, StageReport]:
    directory = run_root / "stage_reports"
    reports: dict[str, StageReport] = {}
    if not directory.is_dir():
        return reports
    for path in sorted(directory.glob("*.json")):
        report = StageReport.model_validate(load_document(path))
        reports[report.stage.value] = report
    return reports


def validate_run(
    profile: ResearchProfile,
    run_root: Path,
    *,
    generated_at: datetime | None = None,
) -> ValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}
    try:
        entities, sources, evidence, relationships = load_run_models(run_root)
    except (FileNotFoundError, ValueError) as exc:
        errors.append(f"无法加载规范化数据: {exc}")
        entities, sources, evidence, relationships = [], [], [], []

    entity_map = _unique_ids("entity", entities, errors)
    source_map = _unique_ids("source", sources, errors)
    evidence_map = _unique_ids("evidence", evidence, errors)
    _unique_ids("relationship", relationships, errors)

    checks["subject_present"] = profile.target.id in entity_map
    if not checks["subject_present"]:
        errors.append(f"目标实体缺失: {profile.target.id}")

    for item in evidence:
        if item.source_id not in source_map:
            errors.append(f"证据 {item.id} 引用了不存在的来源 {item.source_id}")
    for item in sources:
        if item.published_at and item.published_at > profile.cutoff_at.date():
            errors.append(f"来源 {item.id} 的发布时间晚于研究截点")
        policy = item.access_policy
        if not policy.access or not policy.redistribution:
            errors.append(f"来源 {item.id} 缺少访问/许可说明")

    semantic_by_relationship: dict[str, list[Evidence]] = {}
    relation_keys: set[tuple] = set()
    expected_directions = {
        "supplier": RelationDirection.SUPPLIES_TO,
        "customer": RelationDirection.SELLS_TO,
        "partner": RelationDirection.PARTNERS_WITH,
        "investor_or_investee": RelationDirection.INVESTS_IN,
        "peer": RelationDirection.COMPETES_WITH,
    }
    symmetric_target_source = {"partner", "investor_or_investee", "peer", "customer"}
    for relation in relationships:
        key = (
            relation.source_entity_id,
            relation.target_entity_id,
            relation.relation_type.value,
            relation.direction.value,
            relation.product_scope_id,
        )
        if key in relation_keys:
            errors.append(f"关系语义键重复: {key}")
        relation_keys.add(key)
        if relation.as_of > profile.cutoff_at.date():
            errors.append(f"关系 {relation.id} 的 as_of 晚于研究截点")
        for entity_id in (relation.source_entity_id, relation.target_entity_id):
            if entity_id not in entity_map:
                errors.append(f"关系 {relation.id} 引用了不存在的实体 {entity_id}")
        if profile.listed_counterparties_only:
            for entity_id in (relation.source_entity_id, relation.target_entity_id):
                entity = entity_map.get(entity_id)
                if entity_id != profile.target.id and entity and entity.listing_status != ListingStatus.LISTED:
                    errors.append(f"关系 {relation.id} 的对手方 {entity_id} 在截点并非上市实体")
        expected = expected_directions[relation.relation_type.value]
        if relation.direction not in {expected, RelationDirection.UNKNOWN}:
            errors.append(f"关系 {relation.id} 的方向与关系类型不一致")
        if relation.relation_type.value == "supplier":
            if relation.target_entity_id != profile.target.id:
                errors.append(f"供应商关系 {relation.id} 必须为 对手方 -> 目标公司")
        elif relation.relation_type.value in symmetric_target_source:
            if relation.source_entity_id != profile.target.id:
                errors.append(f"{relation.relation_type.value} 关系 {relation.id} 必须以目标公司为 source")

        semantic_ids = relation.relationship_evidence_ids or relation.evidence_ids
        semantic = []
        for evidence_id in relation.evidence_ids:
            if evidence_id not in evidence_map:
                errors.append(f"关系 {relation.id} 引用了不存在的证据 {evidence_id}")
        for evidence_id in semantic_ids:
            row = evidence_map.get(evidence_id)
            if row is None:
                continue
            if relation.evidence_roles.get(evidence_id) == EvidenceRole.LEAD_ONLY:
                continue
            semantic.append(row)
        semantic_by_relationship[relation.id] = semantic
        if not semantic:
            errors.append(f"关系 {relation.id} 没有可用于语义判断的证据")
            continue
        if not any(row.human_verified for row in semantic):
            errors.append(f"关系 {relation.id} 没有经过人工核验的语义证据")
        if not any(row.excerpt or row.visual_description for row in semantic):
            errors.append(
                f"关系 {relation.id} 缺少可离线理解的有限摘录或视觉描述"
            )
        semantic_sources = [source_map.get(row.source_id) for row in semantic]
        semantic_sources = [row for row in semantic_sources if row is not None]
        if relation.fact_status == FactStatus.CONFIRMED and semantic_sources and all(
            row.source_family == "third_party_news" for row in semantic_sources
        ):
            errors.append(f"关系 {relation.id} 不能仅凭第三方新闻标为 confirmed")

    reports = _stage_reports(run_root)
    stage_statuses: dict[str, str] = {}
    for policy in profile.source_policies:
        report = reports.get(policy.family.value)
        if report is None:
            stage_statuses[policy.family.value] = "missing"
            errors.append(f"缺少阶段报告: {policy.family.value}")
            continue
        stage_statuses[policy.family.value] = report.status.value
        if report.status not in policy.accepted_terminal_states:
            errors.append(
                f"阶段 {policy.family.value} 状态 {report.status.value} 不满足策略"
            )
        if report.pending:
            errors.append(f"阶段 {policy.family.value} 仍有 {report.pending} 条未终结记录")

    tasks_path = run_root / "review/counterparty_tasks.jsonl"
    decisions_path = run_root / "review/counterparty_decisions.jsonl"
    tasks = [CounterpartyReviewTask.model_validate(row) for row in read_jsonl(tasks_path)]
    decisions = [
        CounterpartyReviewDecision.model_validate(row) for row in read_jsonl(decisions_path)
    ]
    _unique_ids("counterparty task", tasks, errors)
    _unique_ids("counterparty decision", decisions, errors)
    task_by_entity = {item.counterparty.id: item for item in tasks}
    decision_by_task = {item.task_id: item for item in decisions}
    if len(task_by_entity) != len(tasks):
        errors.append("同一上市对手方存在重复反向复核任务")
    if len(decision_by_task) != len(decisions):
        errors.append("同一反向复核任务存在多个终态决定")
    task_by_id = {item.id: item for item in tasks}
    for decision in decisions:
        task = task_by_id.get(decision.task_id)
        if task is None:
            errors.append(f"反向复核决定 {decision.id} 引用了不存在的任务")
        elif task.counterparty.id != decision.counterparty_entity_id:
            errors.append(f"反向复核决定 {decision.id} 的对手方与任务不一致")
    counterparties = {
        entity_id
        for relation in relationships
        for entity_id in (relation.source_entity_id, relation.target_entity_id)
        if entity_id != profile.target.id
        and entity_id in entity_map
        and entity_map[entity_id].listing_status == ListingStatus.LISTED
    }
    missing_tasks = sorted(counterparties - set(task_by_entity))
    if missing_tasks:
        errors.append(f"上市对手方缺少反向监管复核任务: {', '.join(missing_tasks[:20])}")
    missing_decisions = sorted(
        item.counterparty.id for item in tasks if item.id not in decision_by_task
    )
    if missing_decisions:
        errors.append(f"反向监管复核缺少终态: {', '.join(missing_decisions[:20])}")
    extra_tasks = sorted(set(task_by_entity) - counterparties)
    if extra_tasks:
        warnings.append(f"存在当前关系图之外的复核任务: {', '.join(extra_tasks[:20])}")

    checks.update(
        {
            "references_valid": not any("引用" in item or "不存在" in item for item in errors),
            "all_stages_terminal": len(reports) == len(profile.source_policies)
            and all(item.pending == 0 for item in reports.values()),
            "all_listed_counterparties_reviewed": not missing_tasks and not missing_decisions,
            "no_news_only_confirmed": not any("第三方新闻" in item for item in errors),
            "cutoff_respected": not any("晚于研究截点" in item for item in errors),
        }
    )
    passed = not errors
    counts = {
        "entities": len(entities),
        "sources": len(sources),
        "evidence": len(evidence),
        "relationships": len(relationships),
        "counterparty_tasks": len(tasks),
        "counterparty_decisions": len(decisions),
    }
    for relation_type, count in Counter(item.relation_type.value for item in relationships).items():
        counts[f"relationship_{relation_type}"] = count
    return ValidationReport(
        **{"pass": passed},
        release_ready=passed,
        generated_at=generated_at or datetime.now(timezone.utc),
        errors=errors,
        warnings=warnings,
        counts=counts,
        stage_statuses=stage_statuses,
        checks=checks,
        limitations=[
            "公开检索未命中不证明关系不存在。",
            "监管文件通常不会披露全部客户、供应商或合作伙伴。",
        ],
    )
