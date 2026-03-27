import json
import os
import re
import subprocess
from pathlib import Path


def battle_home() -> Path:
    home = os.environ.get("BATTLE_HOME")
    if home:
        return Path(home)
    return Path.home() / ".battle"


def _is_github_shorthand(s: str) -> bool:
    """Return True if s looks like 'owner/repo' (not an absolute/relative path)."""
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", s))


def _normalize(val: dict | str) -> dict:
    """Normalise a stored plugin entry to the canonical dict form.

    Older versions stored just a path string. Accept both for backward compat.
    """
    if isinstance(val, str):
        return {"path": val}
    return val


class Config:
    def __init__(self):
        self._home = battle_home()
        self._home.mkdir(parents=True, exist_ok=True)
        self._path = self._home / "plugins.json"
        self._data: dict[str, dict] = {}
        if self._path.exists():
            raw = json.loads(self._path.read_text())
            self._data = {k: _normalize(v) for k, v in raw.items()}

    def _save(self):
        self._path.write_text(json.dumps(self._data, indent=2))

    def _resolve_plugin_source(self, repo_dir: Path, name: str) -> str:
        """Read .claude-plugin/marketplace.json and resolve the plugin source directory."""
        marketplace_path = repo_dir / ".claude-plugin" / "marketplace.json"
        if marketplace_path.exists():
            try:
                marketplace = json.loads(marketplace_path.read_text())
                for plugin in marketplace.get("plugins", []):
                    if plugin.get("name") == name:
                        source = plugin.get("source", "./").rstrip("/")
                        resolved = (repo_dir / source).resolve()
                        # Ensure resolved path is within repo_dir (prevent path traversal)
                        if not str(resolved).startswith(str(repo_dir.resolve())):
                            raise ValueError(f"Plugin source '{source}' escapes repo directory")
                        return str(resolved)
            except (json.JSONDecodeError, KeyError):
                pass
        return str(repo_dir)

    def _clone_or_pull(self, name: str, repo: str) -> str:
        """Clone owner/repo to ~/.battle/plugins/<name>/, or pull if already cloned."""
        plugins_dir = self._home / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        # Validate name contains no path separators or traversal
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError(f"Invalid plugin name '{name}': must not contain path separators")
        dest = plugins_dir / name
        if dest.exists():
            subprocess.run(["git", "-C", str(dest), "pull", "--ff-only"], check=True, timeout=120)
        else:
            url = f"https://github.com/{repo}.git"
            subprocess.run(["git", "clone", "--recurse-submodules", url, str(dest)], check=True, timeout=120)
        # Ensure submodules are initialized (--recurse-submodules can silently fail)
        subprocess.run(["git", "-C", str(dest), "submodule", "update", "--init", "--recursive"], check=True, timeout=120)
        return self._resolve_plugin_source(dest, name)

    def register(
        self,
        name: str,
        path: str,
        trigger: str | None = None,
        system_prefix: str | None = None,
    ) -> None:
        """Register a plugin by name and source path (or GitHub shorthand).

        Args:
            name:          Short plugin identifier, e.g. "homerun".
            path:          Local filesystem path or "owner/repo" GitHub shorthand.
            trigger:       Optional slash command that activates the plugin,
                           e.g. "/homerun".  When set, battle prepends this to
                           the task prompt so the plugin's skill fires correctly.
            system_prefix: Optional text prepended to the benchmark system prompt.
                           Useful for plugins whose behaviour depends on a persona
                           or context block in the system prompt.
        """
        if _is_github_shorthand(path):
            local_path = self._clone_or_pull(name, path)
        else:
            local_path = path

        meta: dict = {"path": local_path}
        if trigger is not None:
            meta["trigger"] = trigger
        if system_prefix is not None:
            meta["system_prefix"] = system_prefix

        self._data[name] = meta
        self._save()

        # Warn if the resolved path has no plugin.json — plugin won't load
        plugin_json = Path(local_path) / ".claude-plugin" / "plugin.json"
        if not plugin_json.exists():
            print(
                f"Warning: {local_path!r} has no .claude-plugin/plugin.json — "
                f"'{name}' will behave like baseline (no plugin skills loaded)."
            )

    def get_meta(self, name: str) -> dict:
        """Return the full metadata dict for a registered plugin."""
        if name not in self._data:
            raise KeyError(f"Plugin '{name}' not registered. Run: battle register {name} <path-or-repo>")
        return dict(self._data[name])

    def list_plugins(self) -> dict[str, dict]:
        """Return all registered plugins as {name: meta_dict}."""
        return {k: dict(v) for k, v in self._data.items()}

    def resolve(self, name_or_path: str) -> str:
        """Return the local filesystem path for a plugin name or absolute path."""
        p = Path(name_or_path)
        if p.is_absolute() and p.exists():
            return str(p)
        if name_or_path in self._data:
            return self._data[name_or_path]["path"]
        raise KeyError(f"Plugin '{name_or_path}' not registered. Run: battle register {name_or_path} /path/to/plugin")
