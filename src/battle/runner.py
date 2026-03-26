import os
import shutil
import tempfile
from dataclasses import dataclass, field

from claude_agent_sdk import query, ResultMessage

from .adapters.base import PluginAdapter


@dataclass
class CellResult:
    plugin_id: str
    model: str
    run_index: int
    result_text: str
    cost_usd: float
    num_turns: int
    artifact_files: list[str]  # relative paths of files written in cwd
    artifact_dir: str          # path to saved artifacts (permanent storage)
    error: str | None = None


async def run_cell(
    adapter: PluginAdapter,
    model: str,
    prompt: str,
    run_index: int,
    artifact_base_dir: str | None = None,
) -> CellResult:
    """Run one (plugin, model) cell and return its result."""
    cwd = tempfile.mkdtemp(prefix=f"battle_{adapter.plugin_id}_{run_index}_")
    try:
        options = adapter.get_options(model=model, cwd=cwd)
        result_text = ""
        cost_usd = 0.0
        num_turns = 0
        error = None

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    result_text = message.result or ""
                    cost_usd = message.total_cost_usd or 0.0
                    num_turns = message.num_turns or 0
        except Exception as e:
            error = str(e)

        # Collect artifact files (relative paths)
        artifact_files: list[str] = []
        for root, _, files in os.walk(cwd):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, cwd)
                artifact_files.append(rel)

        # Copy artifacts to permanent storage
        artifact_dir = ""
        if artifact_base_dir:
            dest = os.path.join(
                artifact_base_dir,
                f"{adapter.plugin_id}__{model.replace('/', '_')}__{run_index}",
            )
            os.makedirs(dest, exist_ok=True)
            if artifact_files:
                shutil.copytree(cwd, dest, dirs_exist_ok=True)
            artifact_dir = dest

        return CellResult(
            plugin_id=adapter.plugin_id,
            model=model,
            run_index=run_index,
            result_text=result_text,
            cost_usd=cost_usd,
            num_turns=num_turns,
            artifact_files=artifact_files,
            artifact_dir=artifact_dir,
            error=error,
        )
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
