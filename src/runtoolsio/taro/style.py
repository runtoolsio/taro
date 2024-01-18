from runtoolsio.runcore.run import Outcome, RunState
from runtoolsio.runcore.util import DateTimeFormat
from runtoolsio.taro.theme import Theme


def job_id_style(job):
    if job.run.termination and job.run.termination.status.is_outcome(Outcome.FAULT):
        return Theme.job + " " + Theme.state_failure
    return Theme.job


def job_id_stats_style(job_stats):
    if job_stats.termination_status.is_outcome(Outcome.FAULT):
        return Theme.job + " " + Theme.state_failure
    return Theme.job


def instance_style(job):
    if job.run.termination and job.run.termination.status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return Theme.instance


def general_style(job):
    if job.run.termination and job.run.termination.status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return ""


def stats_style(stats):
    if stats.termination_status.is_outcome(Outcome.FAULT):
        return Theme.state_failure
    return ""


def warn_style(_):
    return Theme.warning


def job_state_style(job):
    return state_style(job.run.lifecycle.run_state)


def job_term_style(job):
    is_outcome = job.run.termination.status.is_outcome
    if is_outcome(Outcome.FAULT):
        return Theme.state_failure
    if is_outcome(Outcome.ABORTED):
        return Theme.state_incomplete
    if is_outcome(Outcome.REJECTED):
        return Theme.state_discarded

    return ""


def stats_state_style(stats):
    return state_style(stats.last_state)


def state_style(state):
    if state == RunState.ENDED:
        return ""
    if state == RunState.EXECUTING:
        return Theme.state_executing

    return Theme.state_before_execution


def stats_failed_style(stats):
    if stats.failed_count:
        return Theme.highlight + " " + Theme.state_failure
    return stats_style(stats)


def stats_warn_style(stats):
    if stats.warning_count:
        return Theme.warning
    return stats_style(stats)


def job_instance_styled(job_instance):
    return [
        (job_id_style(job_instance), job_instance.entity_id),
        (Theme.id_separator, "@"),
        (instance_style(job_instance), job_instance.instance_id)
    ]


def entity_instance_id_styled(metadata):
    return [
        (Theme.job, metadata.entity_id),
        (Theme.id_separator, "@"),
        (Theme.instance, metadata.run_id)
    ]


def job_status_line_styled(job_run, *, ts_prefix_format=DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE):
    return job_instance_id_status_line_styled(
        job_run.metadata, job_run.run.lifecycle.run_state, job_run.run.lifecycle.last_changed_at, ts_prefix_format=ts_prefix_format)


def job_instance_id_status_line_styled(
        metadata, current_state, ts=None, *, ts_prefix_format=DateTimeFormat.DATE_TIME_MS_LOCAL_ZONE):
    style_text_tuples = \
        entity_instance_id_styled(metadata) + [("", " -> "), (state_style(current_state), current_state.name)]
    ts_prefix_formatted = ts_prefix_format(ts) if ts else None
    if ts_prefix_formatted:
        return [("", ts_prefix_formatted + " ")] + style_text_tuples
    else:
        return style_text_tuples
