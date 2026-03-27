from abc import ABC, abstractmethod
import shutil
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

# System prompt appended to every plugin cell (after any plugin-specific prefix).
# Ensures the agent proceeds autonomously in a headless benchmark environment.
BENCHMARK_SYSTEM = (
    "You are running in an automated benchmark evaluation with no human present. "
    "When a skill or workflow requires user approval, confirmation, or clarification, "
    "proceed autonomously — act as both the designer and the approver. "
    "Complete any brainstorming or planning steps yourself, approve your own plan, "
    "then implement immediately without waiting for external input."
)


def install_plugin_settings(plugin_path: str, cwd: str) -> None:
    """Copy the plugin's .claude/settings.json into cwd so hooks are discovered.

    Claude Code finds settings by scanning up from the cwd. Writing the plugin's
    settings here mirrors how hooks work during a real interactive session.
    Skills are handled separately via ClaudeAgentOptions.plugins.
    """
    src = Path(plugin_path) / ".claude" / "settings.json"
    if not src.exists():
        return
    dest_dir = Path(cwd) / ".claude"
    dest_dir.mkdir(exist_ok=True)
    shutil.copy2(src, dest_dir / "settings.json")


class PluginAdapter(ABC):
    """Base class for all plugin adapters."""

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Short identifier, e.g. 'superpowers', 'homerun', 'baseline'."""

    @property
    def plugin_path(self) -> str | None:
        """Filesystem path to the installed plugin root, or None for baseline."""
        return None

    @property
    def trigger_command(self) -> str | None:
        """Optional slash command that activates this plugin, e.g. '/homerun'.

        When set, the runner prepends this to the task prompt so the plugin's
        skill fires instead of the raw task text reaching a vanilla Claude session.
        Declared at registration time via: battle register <name> <path> --trigger /cmd
        """
        return None

    def wrap_prompt(self, prompt: str) -> str:
        """Wrap the task prompt with the plugin's trigger command if needed."""
        if self.trigger_command:
            return f"{self.trigger_command} {prompt}"
        return prompt

    @abstractmethod
    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        """Return ClaudeAgentOptions for a single cell run."""


class GenericPluginAdapter(PluginAdapter):
    """Adapter for any registered plugin, driven entirely by config metadata.

    No magic: invocation trigger and system prompt prefix are declared
    explicitly at registration time, not scraped from plugin internals.
    """

    def __init__(
        self,
        name: str,
        plugin_path: str,
        trigger: str | None = None,
        system_prefix: str | None = None,
    ):
        self._name = name
        self._path = plugin_path
        self._trigger = trigger
        self._system_prefix = system_prefix

    @property
    def plugin_id(self) -> str:
        return self._name

    @property
    def plugin_path(self) -> str | None:
        return self._path or None

    @property
    def trigger_command(self) -> str | None:
        return self._trigger

    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        parts = []
        if self._system_prefix:
            parts.append(self._system_prefix)
        parts.append(BENCHMARK_SYSTEM)
        system_prompt = "\n\n".join(parts)

        return ClaudeAgentOptions(
            cwd=cwd,
            model=model,
            system_prompt=system_prompt,
            plugins=[{"type": "local", "path": self._path}],
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"],
            setting_sources=["user", "project"],
        )


def get_adapter(
    name: str,
    plugin_path: str | None = None,
    trigger: str | None = None,
    system_prefix: str | None = None,
) -> PluginAdapter:
    """Resolve adapter by plugin name.

    'baseline' → BaselineAdapter (no plugin, no trigger).
    All other names → GenericPluginAdapter configured from registered metadata.
    """
    from .baseline import BaselineAdapter  # local import avoids circular dep
    if name == "baseline":
        return BaselineAdapter()
    if plugin_path is not None:
        return GenericPluginAdapter(
            name=name,
            plugin_path=plugin_path,
            trigger=trigger,
            system_prefix=system_prefix,
        )
    raise ValueError(
        f"Plugin '{name}' has no registered path. Run: battle register {name} <path-or-repo>"
    )
