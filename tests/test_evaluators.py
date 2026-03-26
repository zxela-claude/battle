import json
import pytest
from unittest.mock import MagicMock, patch
from battle.evaluators.llm_judge import RubricScore, score_cell


def _json_str(ac=8, style=7, quality=7, security=9, bugs=8, rationale="Good"):
    return json.dumps({
        "ac_completeness": ac, "code_style": style, "code_quality": quality,
        "security": security, "bugs": bugs, "rationale": rationale,
    })


def test_score_cell_returns_rubric_score():
    with patch("battle.evaluators.llm_judge.anyio") as mock_anyio:
        mock_anyio.run.return_value = _json_str()
        score = score_cell(
            artifact_files={"index.tsx": "export default function App() {}"},
            acceptance_criteria=["App renders without errors"],
            judge_model="claude-opus-4-6",
        )
    assert isinstance(score, RubricScore)
    assert score.ac_completeness == 8
    assert score.overall == pytest.approx((8 + 7 + 7 + 9 + 8) / 5, rel=0.01)


def test_score_cell_handles_empty_artifacts():
    with patch("battle.evaluators.llm_judge.anyio") as mock_anyio:
        mock_anyio.run.return_value = _json_str(ac=1, style=1, quality=1, security=1, bugs=1, rationale="No code")
        score = score_cell(
            artifact_files={},
            acceptance_criteria=["Build completes"],
            judge_model="claude-opus-4-6",
        )
    assert score.overall < 5


def test_score_cell_strips_markdown_fences():
    fenced = "```json\n" + _json_str(ac=7, style=7, quality=7, security=7, bugs=7, rationale="Avg") + "\n```"
    with patch("battle.evaluators.llm_judge.anyio") as mock_anyio:
        mock_anyio.run.return_value = fenced
        score = score_cell(
            artifact_files={"app.py": "print('hello')"},
            acceptance_criteria=["Runs without errors"],
        )
    assert score.ac_completeness == 7


def test_rubric_score_overall():
    score = RubricScore(
        ac_completeness=10, code_style=8, code_quality=6, security=9, bugs=7,
        rationale="test"
    )
    assert score.overall == pytest.approx(8.0, rel=0.01)


# --- Static analysis tests (append to existing test_evaluators.py) ---
import subprocess
from unittest.mock import MagicMock
from battle.evaluators.static import StaticResult, run_eslint


def test_run_eslint_no_js_files_returns_not_ran(tmp_path):
    # No JS files → ran=False, zero counts
    result = run_eslint(artifact_dir=str(tmp_path))
    assert result.error_count == 0
    assert result.warning_count == 0
    assert result.ran is False


def test_run_eslint_parses_json_output(tmp_path, monkeypatch):
    # Write a JS file so eslint is attempted
    (tmp_path / "index.js").write_text("var x = 1\n")

    mock_output = '[{"filePath":"index.js","messages":[{"severity":2,"message":"no-var"}],"errorCount":1,"warningCount":0}]'

    def fake_run(cmd, *args, **kwargs):
        result = MagicMock()
        result.stdout = mock_output
        result.returncode = 1
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_eslint(artifact_dir=str(tmp_path))
    assert result.error_count == 1
    assert result.warning_count == 0
    assert result.ran is True


def test_run_eslint_handles_timeout(tmp_path, monkeypatch):
    (tmp_path / "index.ts").write_text("const x = 1;")

    def fake_run_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="npx", timeout=60)

    monkeypatch.setattr(subprocess, "run", fake_run_timeout)
    result = run_eslint(artifact_dir=str(tmp_path))
    assert result.ran is False
    assert result.error_count == 0


def test_run_eslint_skips_node_modules(tmp_path, monkeypatch):
    # Files inside node_modules should not be passed to eslint
    node_mod = tmp_path / "node_modules" / "somelib"
    node_mod.mkdir(parents=True)
    (node_mod / "index.js").write_text("var x = 1;")

    # No non-node_modules JS files → should not call subprocess at all
    called = []
    def fake_run(*args, **kwargs):
        called.append(True)
        return MagicMock(stdout="[]", returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_eslint(artifact_dir=str(tmp_path))
    assert not called, "subprocess.run should not be called when only node_modules files exist"
    assert result.ran is False
