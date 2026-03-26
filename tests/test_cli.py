import subprocess, sys


def test_battle_help():
    result = subprocess.run(
        [sys.executable, "-m", "battle.cli", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--plugins" in result.stdout


def test_battle_register_and_list(tmp_battle_home, monkeypatch, tmp_path):
    plugin_dir = tmp_path / "myplugin"
    plugin_dir.mkdir()
    from battle.cli import cli_register, cli_list
    cli_register(name="myplugin", path=str(plugin_dir))
    # should not raise
    cli_list()
