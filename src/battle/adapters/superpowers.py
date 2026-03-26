from claude_agent_sdk import ClaudeAgentOptions
from .base import BENCHMARK_SYSTEM, PluginAdapter, register_adapter


@register_adapter
class SuperpowersAdapter(PluginAdapter):

    def __init__(self, plugin_path: str):
        self._path = plugin_path

    @property
    def plugin_id(self) -> str:
        return "superpowers"

    def get_options(self, model: str, cwd: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            cwd=cwd,
            model=model,
            system_prompt=BENCHMARK_SYSTEM,
            plugins=[{"type": "local", "path": self._path}],
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Skill"],
        )
