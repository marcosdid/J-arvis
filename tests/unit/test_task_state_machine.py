import pytest

from orchestrator.core.tasks import is_valid_transition

VALID = {
    ("idea", "ready"), ("idea", "discarded"),
    ("ready", "idea"), ("ready", "in_progress"), ("ready", "discarded"),
    ("in_progress", "review"), ("in_progress", "discarded"),
    ("review", "in_progress"), ("review", "done"), ("review", "discarded"),
    ("discarded", "idea"),
}
ALL_STATES = ["idea", "ready", "in_progress", "review", "done", "discarded"]


@pytest.mark.parametrize("frm,to", sorted(VALID))
def test_valid_transitions(frm: str, to: str) -> None:
    assert is_valid_transition(frm, to) is True


def test_same_state_is_valid_idempotent() -> None:
    for s in ALL_STATES:
        assert is_valid_transition(s, s) is True


@pytest.mark.parametrize(
    "frm,to",
    [(f, t) for f in ALL_STATES for t in ALL_STATES
     if (f, t) not in VALID and f != t],
)
def test_invalid_transitions(frm: str, to: str) -> None:
    assert is_valid_transition(frm, to) is False
