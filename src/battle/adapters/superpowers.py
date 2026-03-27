from claude_agent_sdk import ClaudeAgentOptions
from .base import PluginAdapter, build_system_prompt, register_adapter


@register_adapter
class SuperpowersAdapter(PluginAdapter):

    def __init__(self, plugin_path: str = ""):
        self._path = plugin_path

    @property
    def plugin_id(self) -> str:
        return "superpowers"

    @property
    def plugin_path(self) -> str | None:
        return self._path or None

    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            cwd=cwd,
            model=model,
            system_prompt=build_system_prompt(self._path),
            plugins=[{"type": "local", "path": self._path}],
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill", "Agent", "TaskCreate", "TaskUpdate"],
        )
