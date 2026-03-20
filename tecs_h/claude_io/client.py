"""Claude CLI subprocess wrapper with JSON parsing and retry."""

import json
import re
import subprocess


class ClaudeCliError(Exception):
    """Raised when Claude CLI exits with non-zero status."""
    pass


JSON_SUFFIX = "\n\n반드시 JSON만 출력해. 코드 블록이나 설명 없이 순수 JSON만."


def extract_json(raw: str) -> dict:
    """Extract JSON dict from Claude CLI output.

    Strategy: (1) full parse, (2) ```json``` block, (3) first { to last }.
    """
    raw = raw.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: ```json ... ``` code block
    match = re.search(r"```json\s*\n(.*?)\n\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: first { to last }
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last > first:
        try:
            return json.loads(raw[first:last + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No JSON found in output: {raw[:200]}")


def claude_call(prompt: str, timeout: int = 120, max_retries: int = 2) -> dict:
    """Call Claude CLI with -p flag and return parsed JSON.

    Retries up to max_retries times on JSON parse failure.
    """
    full_prompt = prompt + JSON_SUFFIX
    last_error = None

    for attempt in range(1 + max_retries):
        if attempt > 0:
            full_prompt = (
                f"이전 응답이 JSON이 아니었다. 다시 시도해줘.\n\n{prompt}{JSON_SUFFIX}"
            )

        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Claude CLI timed out after {timeout}s")

        if result.returncode != 0:
            raise ClaudeCliError(
                f"Claude CLI exited with code {result.returncode}: {result.stderr}"
            )

        try:
            return extract_json(result.stdout)
        except ValueError as e:
            last_error = e
            continue

    raise last_error
