"""Per-session opaque tokens correlating hook calls with ClaudeSession rows.

In-memory dict is the source of truth at runtime. The DB column
``ClaudeSession.hook_token`` mirrors it for audit/diagnostic; we do
NOT rebuild the registry from the DB on daemon boot (daemon is
on-demand and restart kills sessions, per ARCHITECTURE.md §1.4).
"""

from uuid import uuid4


def generate_token() -> str:
    return uuid4().hex


class TokenRegistry:
    def __init__(self) -> None:
        self._map: dict[str, str] = {}

    def register(self, token: str, session_id: str) -> None:
        self._map[token] = session_id

    def resolve(self, token: str) -> str | None:
        return self._map.get(token)

    def revoke(self, token: str) -> None:
        self._map.pop(token, None)

    def find_token_for(self, session_id: str) -> str | None:
        """Reverse lookup. Used only by tests and the JARVIS_DEBUG endpoint."""
        for token, sid in self._map.items():
            if sid == session_id:
                return token
        return None
