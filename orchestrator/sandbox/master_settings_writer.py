"""F8.b: writers pra settings.json e .ai-jail config do master session."""
import json
from pathlib import Path


def write_master_settings(cwd: Path, *, mcp_url: str, token: str) -> None:
    """Escreve <cwd>/.claude/settings.json com MCP server config.

    Sem hooks F2 (decisao 9 da spec): master e global, nao tem lifecycle
    per-task semantics.
    """
    claude_dir = cwd / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "mcpServers": {
            "j-arvis-master": {
                "type": "http",
                "url": mcp_url,
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))


def write_master_aijail_config(
    cwd: Path, *, claude_session_id: str, allow_port: int,
) -> None:
    """Escreve <cwd>/.ai-jail. Master usa --resume <session-id> e
    --dangerously-skip-permissions. allow_tcp_ports inclui a porta do daemon
    pra Claude conseguir falar com MCP server.
    """
    command_argv = ["claude", "--dangerously-skip-permissions", "--resume", claude_session_id]
    args_json = json.dumps(command_argv)
    (cwd / ".ai-jail").write_text(
        f"command = {args_json}\n"
        "rw_maps = []\n"
        "ro_maps = []\n"
        "hide_dotdirs = []\n"
        "mask = []\n"
        f"allow_tcp_ports = [{allow_port}]\n"
    )
