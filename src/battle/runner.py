import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass, field

from claude_agent_sdk import query, ResultMessage

from .adapters.base import PluginAdapter, install_plugin_settings

# Maximum time (seconds) for a single cell run
CELL_TIMEOUT = 900


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
        # Install plugin settings (hooks etc.) into cwd so Claude Code picks them up
        if adapter.plugin_path:
            install_plugin_settings(adapter.plugin_path, cwd)
        options = adapter.get_options(model=model, cwd=cwd)
        result_text = ""
        cost_usd = 0.0
        num_turns = 0
        error = None

        try:
            async def _run_query() -> None:
                nonlocal result_text, cost_usd, num_turns
                async for message in query(prompt=adapter.wrap_prompt(prompt), options=options):
                    if isinstance(message, ResultMessage):
                        result_text = message.result or ""
                        cost_usd = message.total_cost_usd or 0.0
                        num_turns = message.num_turns or 0

            await asyncio.wait_for(_run_query(), timeout=CELL_TIMEOUT)
        except asyncio.TimeoutError:
            error = f"Cell timed out after {CELL_TIMEOUT}s"
        except Exception as e:
            error = str(e)

        # Collect artifact files (relative paths), skipping vendored dirs
        skip_dirs = {"node_modules", ".git", "__pycache__", ".next", ".cache"}
        artifact_files: list[str] = []
        for root, dirs, files in os.walk(cwd):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
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
                shutil.copytree(cwd, dest, symlinks=True, dirs_exist_ok=True)
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
