"""Local LLM wrapper using llama-cpp-python.

Replaces claude_call for predictor, non_topo_baseline, novelty repackaging.
Keeps same interface: prompt in → dict out.
"""

import json
import re

from llama_cpp import Llama

_llm = None

DEFAULT_MODEL_PATH = "models/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"


def get_llm(model_path: str | None = None) -> Llama:
    """Lazy-load the local LLM."""
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path=model_path or DEFAULT_MODEL_PATH,
            n_ctx=4096,
            n_gpu_layers=-1,  # use GPU if available, else CPU
            verbose=False,
        )
    return _llm


def extract_json(raw: str) -> dict:
    """Extract JSON dict from LLM output."""
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"```json\s*\n(.*?)\n\s*```", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last > first:
        try:
            parsed = json.loads(raw[first:last + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No JSON dict found: {raw[:200]}")


def llama_call(prompt: str, temperature: float = 0.3, max_tokens: int = 1024) -> dict:
    """Call local LLM and return parsed JSON dict. Same interface as claude_call."""
    llm = get_llm()
    suffix = "\n\nRespond with ONLY a JSON object. No markdown, no explanation."
    response = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt + suffix}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = response["choices"][0]["message"]["content"]
    return extract_json(text)
