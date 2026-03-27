import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass, field

from claude_agent_sdk import query, AssistantMessage, ResultMessage

from .adapters.base import PluginAdapter, install_plugin_settings

# Per-million-token pricing (USD) by model for cost estimation from token counts.
# Used as fallback when a ResultMessage (which carries total_cost_usd) is unavailable,
# e.g. when a cell times out before the session completes.
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_cost_per_million, output_cost_per_million)
    "claude-sonnet-4-6":      (3.0,  15.0),
    "claude-sonnet-4-5":      (3.0,  15.0),
    "claude-opus-4-6":        (15.0, 75.0),
    "claude-opus-4-5":        (15.0, 75.0),
    "claude-haiku-4-5":       (0.80,  4.0),
}


def _estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Estimate cost in USD from token counts and model pricing.

    The Anthropic API reports three disjoint input token buckets:
      - input_tokens: uncached input (standard rate)
      - cache_creation_input_tokens: written to cache (1.25x input rate)
      - cache_read_input_tokens: read from cache (0.1x input rate)
    """
    pricing = _MODEL_PRICING.get(model)
    if pricing is None:
        pricing = (3.0, 15.0)
    inp_rate, out_rate = pricing
    input_cost = (
        input_tokens * inp_rate
        + cache_creation_tokens * inp_rate * 1.25
        + cache_read_tokens * inp_rate * 0.10
    )
    return (input_cost + output_tokens * out_rate) / 1_000_000

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

        # Incremental tracking for cost estimation on timeout
        _streaming_turns = 0
        _total_input_tokens = 0
        _total_output_tokens = 0
        _total_cache_creation_tokens = 0
        _total_cache_read_tokens = 0

        try:
            async def _run_query() -> None:
                nonlocal result_text, cost_usd, num_turns
                nonlocal _streaming_turns, _total_input_tokens, _total_output_tokens
                nonlocal _total_cache_creation_tokens, _total_cache_read_tokens
                async for message in query(prompt=adapter.wrap_prompt(prompt), options=options):
                    if isinstance(message, AssistantMessage):
                        _streaming_turns += 1
                        usage = message.usage or {}
                        _total_input_tokens += usage.get("input_tokens", 0)
                        _total_output_tokens += usage.get("output_tokens", 0)
                        _total_cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
                        _total_cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                    elif isinstance(message, ResultMessage):
                        result_text = message.result or ""
                        cost_usd = message.total_cost_usd or 0.0
                        num_turns = message.num_turns or 0

            await asyncio.wait_for(_run_query(), timeout=CELL_TIMEOUT)
        except asyncio.TimeoutError:
            error = f"Cell timed out after {CELL_TIMEOUT}s"
        except Exception as e:
            error = str(e)

        # If we never got a ResultMessage (timeout / error), use streaming data
        total_tokens = _total_input_tokens + _total_cache_creation_tokens + _total_cache_read_tokens
        if cost_usd == 0.0 and total_tokens > 0:
            cost_usd = _estimate_cost(
                model, _total_input_tokens, _total_output_tokens,
                _total_cache_creation_tokens, _total_cache_read_tokens,
            )
        if num_turns == 0 and _streaming_turns > 0:
            num_turns = _streaming_turns

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
