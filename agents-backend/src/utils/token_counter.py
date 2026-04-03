from __future__ import annotations

import os
from typing import Any

try:
    import tiktoken
except Exception:  # pragma: no cover
    tiktoken = None


def resolve_model_name(explicit: str | None = None) -> str:
    return explicit or os.getenv("LLM_MODEL", "gpt-4o-mini")


def has_tiktoken(model_name: str | None = None) -> bool:
    model = resolve_model_name(model_name)
    return _get_encoding(model) is not None


def _get_encoding(model_name: str):
    if tiktoken is None:
        return None
    try:
        return tiktoken.encoding_for_model(model_name)
    except Exception:
        try:
            return tiktoken.get_encoding("o200k_base")
        except Exception:
            try:
                return tiktoken.get_encoding("cl100k_base")
            except Exception:
                return None


def _normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for item in content:
            if isinstance(item, dict):
                out.append(str(item.get("text") or item.get("content") or item))
            else:
                out.append(str(item))
        return "\n".join(out)
    return str(content)


def count_text_tokens(text: str, model_name: str | None = None) -> int:
    model = resolve_model_name(model_name)
    enc = _get_encoding(model)
    if enc is None:
        # Conservative fallback if tokenizer unavailable.
        t = text or ""
        return max(1, len(t) // 4) if t else 0
    return len(enc.encode(text or ""))


def count_messages_tokens(messages: list[Any], model_name: str | None = None) -> int:
    total = 0
    for m in messages or []:
        role = ""
        content = ""

        if isinstance(m, tuple) and len(m) >= 2:
            role = str(m[0])
            content = _normalize_content(m[1])
        else:
            role = str(getattr(m, "type", ""))
            content = _normalize_content(getattr(m, "content", m))

        total += count_text_tokens(f"{role}\n{content}", model_name)

    return total


def extract_usage_from_response(resp: Any) -> dict[str, int] | None:
    """Extract provider-reported token usage when available."""
    if resp is None:
        return None

    md = getattr(resp, "response_metadata", None)
    if isinstance(md, dict):
        usage = md.get("token_usage") or md.get("usage")
        if isinstance(usage, dict):
            in_t = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
            out_t = int(
                usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
            )
            total = int(usage.get("total_tokens", in_t + out_t) or (in_t + out_t))
            return {
                "input_tokens": in_t,
                "output_tokens": out_t,
                "total_tokens": total,
            }

    um = getattr(resp, "usage_metadata", None)
    if isinstance(um, dict):
        in_t = int(um.get("input_tokens", um.get("prompt_tokens", 0)) or 0)
        out_t = int(um.get("output_tokens", um.get("completion_tokens", 0)) or 0)
        total = int(um.get("total_tokens", in_t + out_t) or (in_t + out_t))
        return {"input_tokens": in_t, "output_tokens": out_t, "total_tokens": total}

    return None


def add_usage(
    total: dict[str, Any], input_tokens: int, output_tokens: int, source: str
) -> None:
    total["input_tokens"] = int(total.get("input_tokens", 0)) + int(input_tokens or 0)
    total["output_tokens"] = int(total.get("output_tokens", 0)) + int(
        output_tokens or 0
    )
    total["total_tokens"] = int(total.get("input_tokens", 0)) + int(
        total.get("output_tokens", 0)
    )
    total.setdefault("sources", []).append(source)
