"""Request-scoped context for passing data between ToolDispatchAgent and tools.

The Hosted Agent adapter is single-threaded, so a simple module-level
variable is safe for storing per-request state.
"""

_user_tc: str | None = None


def set_user_tc(tc: str | None) -> None:
    """Store the user's Tc token for the current request."""
    global _user_tc
    _user_tc = tc


def get_user_tc() -> str | None:
    """Retrieve the user's Tc token set by ToolDispatchAgent."""
    return _user_tc
