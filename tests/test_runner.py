import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from battle.runner import CellResult, run_cell, _estimate_cost, CELL_TIMEOUT
from battle.adapters.baseline import BaselineAdapter


def make_mock_result(cost=0.05, result_text="done", num_turns=3):
    from claude_agent_sdk import ResultMessage
    msg = MagicMock(spec=ResultMessage)
    msg.total_cost_usd = cost
    msg.result = result_text
    msg.num_turns = num_turns
    return msg


@pytest.mark.asyncio
async def test_run_cell_returns_cell_result(tmp_path):
    adapter = BaselineAdapter()

    async def fake_query(*args, **kwargs):
        yield make_mock_result()

    with patch("battle.runner.query", fake_query):
        result = await run_cell(
            adapter=adapter,
            model="claude-sonnet-4-6",
            prompt="build something",
            run_index=0,
        )

    assert isinstance(result, CellResult)
    assert result.plugin_id == "baseline"
    assert result.model == "claude-sonnet-4-6"
    assert result.cost_usd == 0.05
    assert result.num_turns == 3
    assert result.error is None


@pytest.mark.asyncio
async def test_run_cell_captures_artifacts(tmp_path):
    adapter = BaselineAdapter()
    captured_cwd = {}

    async def fake_query(*args, **kwargs):
        # Write a file in the cell's cwd
        cwd = kwargs.get("options").cwd
        os.makedirs(cwd, exist_ok=True)
        with open(os.path.join(cwd, "index.tsx"), "w") as f:
            f.write("export default function App() {}")
        captured_cwd["path"] = cwd
        yield make_mock_result()

    with patch("battle.runner.query", fake_query):
        result = await run_cell(
            adapter=adapter,
            model="claude-sonnet-4-6",
            prompt="build something",
            run_index=0,
            artifact_base_dir=str(tmp_path),
        )

    assert "index.tsx" in result.artifact_files
    assert result.artifact_dir != ""
    assert os.path.exists(os.path.join(result.artifact_dir, "index.tsx"))


@pytest.mark.asyncio
async def test_run_cell_handles_error(tmp_path):
    adapter = BaselineAdapter()

    async def fake_query_error(*args, **kwargs):
        raise RuntimeError("SDK failure")
        yield  # make it an async generator

    with patch("battle.runner.query", fake_query_error):
        result = await run_cell(
            adapter=adapter,
            model="claude-sonnet-4-6",
            prompt="build something",
            run_index=0,
        )

    assert result.error is not None
    assert "SDK failure" in result.error


@pytest.mark.asyncio
async def test_run_cell_cleans_up_temp_dir():
    adapter = BaselineAdapter()
    created_cwd = []

    async def fake_query(*args, **kwargs):
        cwd = kwargs.get("options").cwd
        created_cwd.append(cwd)
        yield make_mock_result()

    with patch("battle.runner.query", fake_query):
        await run_cell(
            adapter=adapter,
            model="claude-sonnet-4-6",
            prompt="test",
            run_index=0,
        )

    assert created_cwd, "query was called"
    assert not os.path.exists(created_cwd[0]), "temp dir should be cleaned up"


def test_estimate_cost_sonnet_no_cache():
    # 1M input + 1M output at sonnet pricing: $3 + $15 = $18
    cost = _estimate_cost("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0)


def test_estimate_cost_with_cache_tokens():
    # Sonnet: input_rate=$3/M, output_rate=$15/M
    # 100k uncached input:        100_000 * 3   / 1M = 0.30
    # 500k cache creation:        500_000 * 3 * 1.25 / 1M = 1.875
    # 400k cache read:            400_000 * 3 * 0.10 / 1M = 0.12
    # 200k output:                200_000 * 15  / 1M = 3.00
    # Total: 5.295
    cost = _estimate_cost(
        "claude-sonnet-4-6",
        input_tokens=100_000,
        output_tokens=200_000,
        cache_creation_tokens=500_000,
        cache_read_tokens=400_000,
    )
    assert cost == pytest.approx(5.295)


def test_estimate_cost_unknown_model_uses_sonnet_fallback():
    cost = _estimate_cost("some-future-model", 1_000_000, 1_000_000)
    assert cost == pytest.approx(18.0)


def make_mock_assistant(
    input_tokens=500,
    output_tokens=200,
    cache_creation_input_tokens=0,
    cache_read_input_tokens=0,
):
    from claude_agent_sdk import AssistantMessage
    msg = MagicMock(spec=AssistantMessage)
    msg.usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
    }
    return msg


@pytest.mark.asyncio
async def test_run_cell_timeout_estimates_cost_from_streaming():
    adapter = BaselineAdapter()

    async def fake_query_slow(*args, **kwargs):
        yield make_mock_assistant(input_tokens=10_000, output_tokens=5_000)
        yield make_mock_assistant(input_tokens=12_000, output_tokens=6_000)
        await asyncio.sleep(9999)

    with patch("battle.runner.query", fake_query_slow), \
         patch("battle.runner.CELL_TIMEOUT", 0.1):
        result = await run_cell(
            adapter=adapter,
            model="claude-sonnet-4-6",
            prompt="build something",
            run_index=0,
        )

    assert result.error is not None
    assert "timed out" in result.error
    assert result.num_turns == 2
    # 22_000 input * 3/1M + 11_000 output * 15/1M = 0.066 + 0.165 = 0.231
    assert result.cost_usd == pytest.approx(0.231)


@pytest.mark.asyncio
async def test_run_cell_timeout_accounts_for_cached_tokens():
    adapter = BaselineAdapter()

    async def fake_query_slow(*args, **kwargs):
        # Turn 1: big cache creation (system prompt cached)
        yield make_mock_assistant(
            input_tokens=1_000,
            output_tokens=2_000,
            cache_creation_input_tokens=50_000,
            cache_read_input_tokens=0,
        )
        # Turn 2: cache hit on subsequent turn
        yield make_mock_assistant(
            input_tokens=500,
            output_tokens=3_000,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=50_000,
        )
        await asyncio.sleep(9999)

    with patch("battle.runner.query", fake_query_slow), \
         patch("battle.runner.CELL_TIMEOUT", 0.1):
        result = await run_cell(
            adapter=adapter,
            model="claude-sonnet-4-6",
            prompt="build something",
            run_index=0,
        )

    assert result.num_turns == 2
    # Sonnet: input=$3/M, output=$15/M
    # 1_500 uncached input:        1_500 * 3 / 1M     = 0.0045
    # 50_000 cache creation:       50_000 * 3.75 / 1M = 0.1875
    # 50_000 cache read:           50_000 * 0.30 / 1M = 0.015
    # 5_000 output:                5_000 * 15 / 1M    = 0.075
    expected = _estimate_cost("claude-sonnet-4-6", 1_500, 5_000, 50_000, 50_000)
    assert result.cost_usd == pytest.approx(expected)
    assert result.cost_usd > 0
