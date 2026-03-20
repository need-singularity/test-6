"""LLM router: decides which backend (llama local vs claude CLI) to use per role.

Usage:
    from tecs_h.claude_io.router import llm_call

    result = llm_call(prompt, role="predictor")
"""

import os

from tecs_h.claude_io.client import claude_call

# Default: all roles use llama. Override with TECS_H_CLAUDE_ROLES env var.
# Example: TECS_H_CLAUDE_ROLES=resolver,repackaging  (only resolver and repackaging use Claude)
_claude_roles: set[str] | None = None
_llama_available: bool | None = None


def _get_claude_roles() -> set[str]:
    global _claude_roles
    if _claude_roles is None:
        env = os.environ.get("TECS_H_CLAUDE_ROLES", "resolver")
        _claude_roles = {r.strip() for r in env.split(",") if r.strip()}
    return _claude_roles


def _is_llama_available() -> bool:
    global _llama_available
    if _llama_available is None:
        try:
            from tecs_h.claude_io.llm import get_llm
            _llama_available = True
        except ImportError:
            _llama_available = False
    return _llama_available


def llm_call(prompt: str, role: str = "default") -> dict:
    """Route LLM call based on role.

    Roles: predictor, resolver, non_topo_baseline, repackaging, default
    Default config: resolver uses Claude CLI, everything else uses llama.
    Override with TECS_H_CLAUDE_ROLES env var.
    """
    claude_roles = _get_claude_roles()

    if role in claude_roles or not _is_llama_available():
        return claude_call(prompt)

    from tecs_h.claude_io.llm import llama_call
    return llama_call(prompt)
