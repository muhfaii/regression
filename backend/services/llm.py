"""LLM chat service — calls OpenAI-compatible API for analysis interpretation."""
from __future__ import annotations

import json
import os

import httpx

SYSTEM_PROMPT = """You are an expert statistical data analysis assistant embedded in a data-analysis application. You help users understand their data, interpret statistical results, and choose the right analyses.

Your capabilities:
- Explain statistical test results in plain, accessible language
- Help identify which tests are appropriate based on variable types
- Guide users through the analysis workflow
- Answer questions about statistical concepts

Available analyses: descriptive statistics, independent/paired t-tests, one-way/factorial/mixed ANOVA, Mann-Whitney, Wilcoxon, Kruskal-Wallis, Pearson/Spearman correlation, chi-square independence, OLS/panel/logistic regression, moderation, mediation, reliability (Cronbach's alpha), factor analysis (EFA), CFA (SEM), power analysis, time series analysis, survival analysis (Kaplan-Meier, Cox PH), nonparametric tests.

Guidelines:
- Be concise but thorough. Cite actual numbers from results when available.
- If the user asks about a test not yet run, suggest running it.
- If variable types don't match a requested test, explain why and suggest alternatives.
- When interpreting p-values and effect sizes, explain what they mean practically."""


def is_configured() -> bool:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    return bool(api_key)


def get_model_name() -> str:
    return os.environ.get("LLM_MODEL", "gpt-4o-mini")


def _build_messages(
    conversation_messages: list,
    session_info: dict | None,
) -> list[dict]:
    system_text = SYSTEM_PROMPT

    if session_info:
        cols_lines = []
        for c in session_info.get("columns", []):
            cols_lines.append(f"  - {c['name']} ({c.get('inferred_type', c.get('raw_dtype', '?'))})")
        cols_str = "\n".join(cols_lines) if cols_lines else "  (none)"

        system_text += f"""

## Loaded Dataset
- File: {session_info.get('filename', 'unknown')}
- Rows: {session_info.get('row_count', '?')}
- Columns:
{cols_str}
- Context: {session_info.get('dataset_context', 'generic')}
"""

    messages: list[dict] = [{"role": "system", "content": system_text}]

    for msg in conversation_messages:
        role = "assistant" if msg.role == "assistant" else "user"
        payload = _resolve_payload(msg.payload)

        if msg.content_type == "text" and isinstance(payload, dict):
            content = payload.get("text", "")
        elif msg.content_type == "result" and isinstance(payload, dict):
            content = json.dumps(payload, indent=2, default=str)
        elif msg.content_type == "config" and isinstance(payload, dict):
            content = json.dumps(payload, indent=2, default=str)
        else:
            content = str(payload) if isinstance(payload, str) else json.dumps(payload, default=str)

        if content.strip():
            messages.append({"role": role, "content": content})

    return messages


def _resolve_payload(payload):
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return payload
    return payload


async def chat_completion(messages: list[dict]) -> str:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("LLM_API_KEY environment variable is not set.")

    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2500,
            },
        )
        if resp.status_code >= 400:
            detail = resp.text[:500]
            try:
                detail = resp.json().get("error", {}).get("message", detail)
            except Exception:
                pass
            raise ValueError(f"LLM API error ({resp.status_code}): {detail}")

        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def generate_chat_response(
    conversation_messages: list,
    session_info: dict | None,
) -> str:
    messages = _build_messages(conversation_messages, session_info)
    return await chat_completion(messages)
