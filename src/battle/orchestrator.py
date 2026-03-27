import asyncio
from dataclasses import dataclass, field

from .adapters.base import get_adapter
from .adapters.baseline import BaselineAdapter
from .runner import CellResult, run_cell


@dataclass
class MatrixConfig:
    plugin_names: list[str]           # e.g. ["superpowers", "homerun"]
    plugin_meta: dict[str, dict]      # name -> {path, trigger?, system_prefix?}
    models: list[str]
    prompt: str
    runs_per_cell: int
    artifact_base_dir: str


async def run_matrix(config: MatrixConfig, sequential: bool = False) -> list[CellResult]:
    """Run all (plugin × model × run_index) cells.

    When sequential=True, cells run one at a time instead of in parallel.
    """
    # Build adapter list: baseline always first, then named plugins
    adapters = [BaselineAdapter()]
    for name in config.plugin_names:
        meta = config.plugin_meta.get(name, {})
        adapters.append(get_adapter(
            name,
            plugin_path=meta.get("path"),
            trigger=meta.get("trigger"),
            system_prefix=meta.get("system_prefix"),
        ))

    cell_args = [
        dict(
            adapter=adapter,
            model=model,
            prompt=config.prompt,
            run_index=run_index,
            artifact_base_dir=config.artifact_base_dir,
        )
        for adapter in adapters
        for model in config.models
        for run_index in range(config.runs_per_cell)
    ]

    if sequential:
        results = []
        for kwargs in cell_args:
            results.append(await run_cell(**kwargs))
        return results

    tasks = [run_cell(**kwargs) for kwargs in cell_args]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    results = []
    for i, result in enumerate(raw_results):
        if isinstance(result, BaseException):
            adapter = cell_args[i]["adapter"]
            model = cell_args[i]["model"]
            print(f"  Cell {adapter.plugin_id}/{model} failed: {result}")
            results.append(CellResult(
                plugin_id=adapter.plugin_id,
                model=model,
                run_index=cell_args[i]["run_index"],
                result_text="",
                artifact_dir="",
                artifact_files=[],
                cost_usd=0.0,
                num_turns=0,
                error=str(result),
            ))
        else:
            results.append(result)
    return results
