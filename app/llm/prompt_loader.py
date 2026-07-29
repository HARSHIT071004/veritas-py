import os
from functools import cache


_PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


@cache
def load_prompt(name: str) -> str:
    path = os.path.join(_PROMPT_DIR, f"{name}.txt")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt '{name}' not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def format_prompt(name: str, **kwargs) -> str:
    return load_prompt(name).format(**kwargs)
