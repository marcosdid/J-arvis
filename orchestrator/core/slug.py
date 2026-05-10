"""Branch slug derivation from task titles.

`slugify_for_branch` is used as the default branch name when a task
starts its first session. The output is conservative: lowercase ASCII,
hyphens only, max 60 chars. For more permissive overrides (e.g.
`feature/JIRA-123/foo`), use the user-set `task.branch` field, which
is validated by a different regex at the API layer.

NB: this function MUST stay in 1:1 sync with ui/src/lib/slug.ts. Any
divergence will cause server-side validation to disagree with the
slug preview shown in NewTaskForm placeholder.
"""
import re

_SLUG_INVALID_RE = re.compile(r"[^a-z0-9]+")
_SLUG_COLLAPSE_RE = re.compile(r"-+")


class InvalidBranchSlugError(Exception):
    """Raised when slugify yields an empty result (e.g. all-punctuation title)."""


def slugify_for_branch(text: str) -> str:
    """Derive a kebab-case slug suitable as a git branch name.

    Rules: lowercase, replace non-[a-z0-9] runs with single hyphen,
    strip leading/trailing hyphens, truncate at 60 chars.
    Raises InvalidBranchSlugError if the result is empty.
    """
    s = text.lower().strip()
    s = _SLUG_INVALID_RE.sub("-", s)
    s = _SLUG_COLLAPSE_RE.sub("-", s).strip("-")
    if not s:
        raise InvalidBranchSlugError(f"cannot slugify '{text}' to a valid branch name")
    return s[:60].rstrip("-")
