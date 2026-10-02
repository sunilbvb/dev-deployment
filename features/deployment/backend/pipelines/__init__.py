"""Visual Pipeline Builder & Sequential Execution Engine.

Modular architecture:
- storage: Pipeline definitions persistence, schema validation, and template resolution
- engine: Sequential execution worker, live run state tracker, and history logging
"""

from .storage import (
    delete_pipeline,
    get_pipelines,
    resolve_pipeline,
    save_pipeline,
)
from .engine import (
    _PIPELINE_RUNS,
    _PIPELINES_LOCK,
    _prune_pipeline_runs,
    _record_pipeline_history,
    execute_pipeline,
    get_pipeline_run,
    run_pipeline,
    stop_pipeline_run,
)

__all__ = [
    "resolve_pipeline",
    "get_pipelines",
    "save_pipeline",
    "delete_pipeline",
    "run_pipeline",
    "execute_pipeline",
    "stop_pipeline_run",
    "get_pipeline_run",
    "_PIPELINE_RUNS",
    "_PIPELINES_LOCK",
    "_prune_pipeline_runs",
    "_record_pipeline_history",
]
