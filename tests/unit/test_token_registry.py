from orchestrator.hooks.tokens import TokenRegistry, generate_token


def test_generate_token_is_unique_hex() -> None:
    a, b = generate_token(), generate_token()
    assert a != b
    assert len(a) == 32
    assert all(c in "0123456789abcdef" for c in a)


def test_register_then_resolve_returns_session_id() -> None:
    reg = TokenRegistry()
    token = generate_token()
    reg.register(token, "sess-1")
    assert reg.resolve(token) == "sess-1"


def test_resolve_unknown_returns_none() -> None:
    assert TokenRegistry().resolve("nope") is None


def test_revoke_removes_token() -> None:
    reg = TokenRegistry()
    token = generate_token()
    reg.register(token, "sess-1")
    reg.revoke(token)
    assert reg.resolve(token) is None


def test_revoke_unknown_is_noop() -> None:
    TokenRegistry().revoke("never-registered")  # must not raise
