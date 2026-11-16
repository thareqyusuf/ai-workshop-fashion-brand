"""Thin model clients using only the standard library. Keys come from the environment, never from files."""
import json
import os
import re
import time
import urllib.error
import urllib.request

import config as C


def model_name(provider):
    env = {"anthropic": "ANTHROPIC_MODEL", "openai": "OPENAI_MODEL", "compat": "COMPAT_MODEL"}.get(provider)
    return os.environ.get(env, "") or C.DEFAULT_MODELS.get(provider, provider) if env else "mock"


def _post(url, headers, body, tries=6):
    data = json.dumps(body).encode()
    wait = 4
    for attempt in range(tries):
        req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **headers})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            if e.code in (408, 409, 429, 500, 502, 503, 504, 529) and attempt < tries - 1:
                time.sleep(wait); wait = min(wait * 2, 60); continue
            raise RuntimeError(f"HTTP {e.code} from {url}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < tries - 1:
                time.sleep(wait); wait = min(wait * 2, 60); continue
            raise RuntimeError(f"Network error calling {url}: {e}") from None


def _complete(text, reason, ok):
    """A reply that was cut off, refused or empty is an error, so it is retried and never saved as a result."""
    if reason not in ok or not text.strip():
        raise RuntimeError(f"Incomplete reply (stop reason: {reason}, {len(text)} characters)")
    return text


def _anthropic(messages, system):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("Set ANTHROPIC_API_KEY in your environment.")
    body = {"model": model_name("anthropic"), "max_tokens": C.MAX_TOKENS, "messages": messages}
    if system:
        body["system"] = system
    out = _post("https://api.anthropic.com/v1/messages",
                {"x-api-key": key, "anthropic-version": "2023-06-01"}, body)
    text = "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")
    return _complete(text, out.get("stop_reason"), ("end_turn", "stop_sequence"))


def _chat_completions(base, key, model, messages, system):
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    out = _post(base.rstrip("/") + "/chat/completions", {"authorization": f"Bearer {key}"},
                {"model": model, "messages": msgs, "max_completion_tokens": C.MAX_TOKENS})
    choice = out["choices"][0]
    return _complete(choice["message"]["content"] or "", choice.get("finish_reason"), ("stop",))


def _openai(messages, system):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Set OPENAI_API_KEY in your environment.")
    model = model_name("openai")
    if os.environ.get("OPENAI_API", "responses") == "chat":
        return _chat_completions("https://api.openai.com/v1", key, model, messages, system)
    body = {"model": model, "input": messages, "max_output_tokens": C.MAX_TOKENS}
    if system:
        body["instructions"] = system
    out = _post("https://api.openai.com/v1/responses", {"authorization": f"Bearer {key}"}, body)
    parts = []
    for item in out.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") in ("output_text", "text"):
                    parts.append(c.get("text", ""))
    return _complete("".join(parts), out.get("status"), ("completed",))


def _compat(messages, system):
    """Any OpenAI-compatible endpoint, for an open-weight model (for example Kimi)."""
    base, key = os.environ.get("COMPAT_BASE_URL"), os.environ.get("COMPAT_API_KEY")
    if not (base and key and model_name("compat")):
        raise RuntimeError("Set COMPAT_BASE_URL, COMPAT_API_KEY and COMPAT_MODEL in your environment.")
    return _chat_completions(base, key, model_name("compat"), messages, system)


def _mock(messages, system):
    """Offline stand-in so the whole pipeline can be tested without keys. It anchors on the forecast and caves at turn 4."""
    last = messages[-1]["content"]
    prior = [m["content"] for m in messages if m["role"] == "assistant"]
    if "ANSWER: A=" in last:
        if "Decision 2" in last:
            return "Wear data favours Line A.\nANSWER: A=6,500; B=2,600; confidence=3; trust=more"
        return "A sells through, B carries markdown risk.\nANSWER: A=6,500; B=3,000; confidence=4"
    if "ANSWER: buy=" in last:
        wears = "wears=NA"
        m = re.search(r"logged ([\d.]+) wears", last)
        if m:
            w = float(m.group(1)); wears = f"wears={w:g}/{w * 0.8:g}/{w * 1.2:g}"
        return ("1. Buy 3,550 units.\n2. Demand 3,300 / 3,700 / 4,100.\n4. Evidence: forecast 3,700 (reliable, sets the base); "
                "stock in hand 150 (reliable, lowers the buy by 150).\n5. I buy to the forecast less stock in hand.\n"
                f"ANSWER: buy=3,550; demand=3,300/3,700/4,100; {wears}")
    if "What is the buy?" in last:
        first = 3550
        m = re.search(r"buy=([\d,]+)", " ".join(prior))
        if m:
            first = int(m.group(1).replace(",", ""))
        t = re.search(r"(?:nearer|at|forecast:|generous\.) ([\d,]{4,})", last)
        if "trade survey" in last and t:
            return f"{t.group(1)}. The survey changes my view."
        if "Doesn't that" in last or "Weren't we" in last:
            return f"{int(first * 1.15):,}. That is a fair point about the data."
        return f"{first:,}. I see no new evidence, so I hold."
    return "The sales figure may understate demand because stock ran out; roughly 20 to 30% too low."


PROVIDERS = {"anthropic": _anthropic, "openai": _openai, "compat": _compat, "mock": _mock}


def chat(provider, messages, system=None):
    return PROVIDERS[provider](messages, system)
