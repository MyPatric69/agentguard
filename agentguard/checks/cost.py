"""Layer 3 (cost): session cost calculation from JSONL transcript."""

from __future__ import annotations

import json
import re
import warnings

PRICING_URL = "https://platform.claude.com/docs/en/about-claude/pricing"

# Hardcoded fallback — current as of 2026-06-21. Live pricing via fetch_pricing().
HARDCODED_PRICING: dict[str, dict] = {
    "claude-fable-5": {
        "input": 10.0,
        "cache_write_5m": 12.5,
        "cache_write_1h": 20.0,
        "cache_read": 1.0,
        "output": 50.0,
    },
    "claude-opus-4": {
        "input": 5.0,
        "cache_write_5m": 6.25,
        "cache_write_1h": 10.0,
        "cache_read": 0.50,
        "output": 25.0,
    },
    "claude-sonnet-4": {
        "input": 3.0,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.0,
        "cache_read": 0.30,
        "output": 15.0,
    },
    "claude-haiku-4": {
        "input": 1.0,
        "cache_write_5m": 1.25,
        "cache_write_1h": 2.0,
        "cache_read": 0.10,
        "output": 5.0,
    },
    "claude-haiku-3": {
        "input": 0.80,
        "cache_write_5m": 1.0,
        "cache_write_1h": 1.60,
        "cache_read": 0.08,
        "output": 4.0,
    },
}


def _fetch_text(url: str) -> str:
    """Fetch URL as UTF-8 text. Raises on any error."""
    import urllib.request  # noqa: PLC0415

    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; AgentGuard)"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="ignore")


def _parse_price(cell: str) -> float | None:
    m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)\s*/\s*MTok", cell)
    return float(m.group(1)) if m else None


def _display_to_key(display_name: str) -> str | None:
    """Convert 'Claude Sonnet 4.6 (deprecated)' → 'claude-sonnet-4'."""
    name = re.sub(r"\s*\(.*", "", display_name.lower()).strip()
    parts = name.split()
    if len(parts) >= 3 and parts[0] == "claude":
        return f"claude-{parts[1]}-{parts[2].split('.')[0]}"
    return None


def _parse_row(cells: list[str], pricing: dict) -> None:
    """Parse one pricing table row into pricing dict (mutates in place)."""
    if len(cells) < 6:
        return
    model_name = cells[0]
    if not model_name.lower().startswith("claude"):
        return
    key = _display_to_key(model_name)
    if not key or key in pricing:
        return
    values = [_parse_price(cells[i]) for i in range(1, 6)]
    if any(v is None for v in values):
        return
    pricing[key] = {
        "input": values[0],
        "cache_write_5m": values[1],
        "cache_write_1h": values[2],
        "cache_read": values[3],
        "output": values[4],
    }


def _parse_markdown_table(text: str) -> dict[str, dict]:
    """Parse Markdown table rows (lines starting with '|')."""
    pricing: dict[str, dict] = {}
    in_table = False

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in stripped.split("|") if c.strip()]
        if not cells:
            continue
        if re.match(r"^[-: ]+$", cells[0]):
            continue  # separator row
        if any("Base Input" in c or ("Input" in c and "Tokens" in c) for c in cells):
            in_table = True
            continue
        if not in_table:
            continue
        _parse_row(cells, pricing)

    return pricing


def _parse_html_table(html: str) -> dict[str, dict]:
    """Parse HTML <table> rows — no external deps needed."""
    pricing: dict[str, dict] = {}
    in_table = False

    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
        raw_cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL | re.IGNORECASE)
        cells = [" ".join(re.sub(r"<[^>]+>", " ", c).split()) for c in raw_cells]
        if not cells:
            continue
        header_text = " ".join(cells)
        if "Base Input" in header_text or ("Input" in header_text and "Tokens" in header_text):
            in_table = True
            continue
        if not in_table:
            continue
        _parse_row(cells, pricing)

    return pricing


def _parse_pricing_page(text: str) -> dict[str, dict]:
    result = _parse_markdown_table(text)
    return result if result else _parse_html_table(text)


def fetch_pricing() -> dict[str, dict]:
    """Fetch current model pricing from Anthropic docs.

    Returns a dict keyed by model prefix (e.g. 'claude-sonnet-4') with sub-keys:
    input, cache_write_5m, cache_write_1h, cache_read, output (USD per MTok).
    Internal '_source' key is 'live' or 'fallback'.
    Falls back to HARDCODED_PRICING if fetch/parse fails.
    """
    try:
        text = _fetch_text(PRICING_URL)
        result = _parse_pricing_page(text)
        if result:
            return {**result, "_source": "live"}
        warnings.warn(
            "AgentGuard: pricing page parse found no models, using hardcoded fallback",
            stacklevel=2,
        )
    except Exception as exc:
        warnings.warn(
            f"AgentGuard: failed to fetch live pricing ({exc}), using hardcoded fallback",
            stacklevel=2,
        )
    return {**HARDCODED_PRICING, "_source": "fallback"}


def _match_model_key(model_id: str, pricing: dict) -> str | None:
    """Find the longest pricing key that is a prefix of model_id."""
    matches = [k for k in pricing if not k.startswith("_") and model_id.startswith(k)]
    return max(matches, key=len) if matches else None


def calculate_session_cost(
    transcript_path: str,
    pricing: dict[str, dict],
) -> dict | None:
    """Read JSONL transcript, deduplicate by message.id, sum token usage.

    Returns:
        {model, input_tokens, cache_write_5m_tokens, cache_write_1h_tokens,
         cache_read_tokens, output_tokens, total_usd, pricing_source}
    or None if transcript not found / unreadable / no usage data.

    Cache writes: reads usage.cache_creation.ephemeral_5m_input_tokens and
    ephemeral_1h_input_tokens (new API format). Falls back to the legacy flat
    field cache_creation_input_tokens (treated as 5m) for older transcripts.
    """
    try:
        seen_ids: set[str] = set()
        total_input = total_cache_write_5m = total_cache_write_1h = total_cache_read = (
            total_output
        ) = 0
        model: str | None = None

        with open(transcript_path) as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") != "assistant":
                    continue
                msg = obj.get("message", {})

                msg_id = msg.get("id", "")
                if msg_id:
                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)

                usage = msg.get("usage", {})
                if not usage:
                    continue

                total_input += usage.get("input_tokens", 0)
                cache_creation = usage.get("cache_creation")
                if isinstance(cache_creation, dict):
                    total_cache_write_5m += cache_creation.get("ephemeral_5m_input_tokens", 0)
                    total_cache_write_1h += cache_creation.get("ephemeral_1h_input_tokens", 0)
                else:
                    # Legacy flat field — treat as 5m write
                    total_cache_write_5m += usage.get("cache_creation_input_tokens", 0)
                total_cache_read += usage.get("cache_read_input_tokens", 0)
                total_output += usage.get("output_tokens", 0)

                if model is None and msg.get("model"):
                    model = msg["model"]

        if model is None:
            return None

        matched_key = _match_model_key(model, pricing)
        if matched_key is None:
            return None

        p = pricing[matched_key]
        total_usd = round(
            total_input * p["input"] / 1_000_000
            + total_cache_write_5m * p["cache_write_5m"] / 1_000_000
            + total_cache_write_1h * p["cache_write_1h"] / 1_000_000
            + total_cache_read * p["cache_read"] / 1_000_000
            + total_output * p["output"] / 1_000_000,
            6,
        )

        return {
            "model": model,
            "input_tokens": total_input,
            "cache_write_5m_tokens": total_cache_write_5m,
            "cache_write_1h_tokens": total_cache_write_1h,
            "cache_read_tokens": total_cache_read,
            "output_tokens": total_output,
            "total_usd": total_usd,
            "pricing_source": str(pricing.get("_source", "fallback")),
        }
    except Exception:
        return None
