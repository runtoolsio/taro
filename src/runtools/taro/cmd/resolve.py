"""Shared instance resolution for action commands (stop, approve, resume).

Handles both pattern-based lookup and interactive selection when no patterns are provided.
"""

from typing import Optional, Callable

from runtools.runcore.criteria import JobRunCriteria
from runtools.runcore.util import MatchingStrategy
from runtools.taro.tui.selector import select_instance


def resolve_instances(
        conn,
        patterns: Optional[list[str]],
        *,
        update_criteria: Callable[[JobRunCriteria], None] | None = None,
        instance_filter: Callable | None = None,
        select_title: str = "Select instance",
) -> list:
    """Resolve patterns (or interactive selection) to a list of live JobInstances.

    Args:
        conn: An open EnvironmentConnector.
        patterns: CLI patterns to match. None/empty triggers interactive selector.
        update_criteria: Optional callback to add criteria (e.g. PhaseCriterion) to each query.
        instance_filter: Optional predicate applied to each fetched instance.
        select_title: Title for the interactive selector when multiple instances match.

    Returns:
        List of matched JobInstance objects (may be empty).
    """
    if not patterns:
        return _resolve_no_patterns(conn, update_criteria, instance_filter, select_title)
    return _resolve_with_patterns(conn, patterns, update_criteria, instance_filter)


def _resolve_no_patterns(conn, update_criteria, instance_filter, select_title) -> list:
    criteria = JobRunCriteria()
    if update_criteria:
        update_criteria(criteria)

    instances = conn.get_instances(criteria)
    instances = [i for i in instances if not i.snap().lifecycle.is_ended]

    if instance_filter:
        instances = [i for i in instances if instance_filter(i)]

    if len(instances) <= 1:
        return instances

    selected = select_instance(conn, instances, run_match=criteria, title=select_title)
    return [selected] if selected else []


def _resolve_with_patterns(conn, patterns, update_criteria, instance_filter) -> list:
    seen_ids = set()
    result = []

    for pattern in patterns:
        criteria = JobRunCriteria.parse(pattern, MatchingStrategy.FN_MATCH)
        if update_criteria:
            update_criteria(criteria)

        instances = conn.get_instances(criteria)
        if instance_filter:
            instances = [i for i in instances if instance_filter(i)]

        for inst in instances:
            inst_id = inst.id
            if inst_id not in seen_ids:
                seen_ids.add(inst_id)
                result.append(inst)

    return result
