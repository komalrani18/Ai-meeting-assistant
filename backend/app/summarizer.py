"""
Map-reduce summarization:
  - Short transcripts: one LLM call -> final JSON (summary + action items) directly.
  - Long transcripts: "map" each chunk to brief notes + candidate action items,
    then "reduce" all chunk notes into one final JSON via a second LLM call.

Action items are requested in a strict format so downstream parsing (PDF, frontend
table) doesn't have to guess: "[Person] will [Action] by [Deadline]".
"""
import json
import re
from typing import List

from app.chunking import chunk_transcript, needs_chunking
from app.llm import get_chat_client
from app.schemas import ActionItem

MAP_SYSTEM_PROMPT = (
    "You are an executive assistant reviewing one part of a longer meeting transcript. "
    "Write brief bullet notes (5-8 bullets) covering the key topics and decisions discussed "
    "in THIS PART ONLY, and list any action items you can identify in this part in the "
    "exact format '[Person Name] will [Action] by [Deadline]' (use 'unspecified' if a name "
    "or deadline is not stated). Be concise. Do not summarize parts you haven't seen."
)

REDUCE_SYSTEM_PROMPT = (
    "You are an executive assistant. You will be given bullet notes and candidate action "
    "items collected from sequential parts of one meeting. Merge them into a single final "
    "output. Respond with ONLY a valid JSON object (no markdown fences, no commentary), "
    "matching exactly this schema:\n"
    '{\n'
    '  "summary": "<a concise 3-sentence executive summary of the whole meeting>",\n'
    '  "action_items": [\n'
    '    {"person": "<name>", "action": "<what they will do>", "deadline": "<when, or \'unspecified\'>"}\n'
    "  ]\n"
    "}\n"
    "Deduplicate action items that refer to the same commitment (e.g., mentioned in "
    "overlapping chunks). If no action items were found, return an empty list."
)

DIRECT_SYSTEM_PROMPT = (
    "You are an executive assistant. Read the following meeting transcript. Respond with "
    "ONLY a valid JSON object (no markdown fences, no commentary), matching exactly this "
    "schema:\n"
    '{\n'
    '  "summary": "<a concise 3-sentence summary of the main topics discussed>",\n'
    '  "action_items": [\n'
    '    {"person": "<name>", "action": "<what they will do>", "deadline": "<when, or \'unspecified\'>"}\n'
    "  ]\n"
    "}\n"
    "If no action items were mentioned, return an empty list for action_items."
)


def _extract_json(raw: str) -> dict:
    """LLMs sometimes wrap JSON in ```json fences or add stray text; strip and parse
    defensively, falling back to the first {...} block found."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Last resort: don't fail the whole job over a formatting slip
    return {"summary": raw.strip()[:800], "action_items": []}


def _to_action_items(raw_items: list) -> List[ActionItem]:
    items = []
    for it in raw_items or []:
        try:
            items.append(
                ActionItem(
                    person=str(it.get("person", "unspecified")).strip() or "unspecified",
                    action=str(it.get("action", "")).strip(),
                    deadline=str(it.get("deadline", "unspecified")).strip() or "unspecified",
                )
            )
        except Exception:
            continue
    # de-dupe exact repeats (cheap safety net on top of the LLM's own dedup)
    seen = set()
    deduped = []
    for it in items:
        key = (it.person.lower(), it.action.lower(), it.deadline.lower())
        if key not in seen:
            seen.add(key)
            deduped.append(it)
    return deduped


def _summarize_chunk(client, chunk_text: str, chunk_index: int, total_chunks: int) -> str:
    messages = [
        {"role": "system", "content": MAP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Part {chunk_index + 1} of {total_chunks} of the meeting transcript:\n\n{chunk_text}",
        },
    ]
    return client.invoke(messages, temperature=0.2, max_tokens=700)


def summarize_transcript(full_text: str):
    """Returns (summary: str, action_items: List[ActionItem], num_chunks: int)."""
    client = get_chat_client()

    if not full_text.strip():
        return "The transcript was empty — no speech was detected in the audio.", [], 0

    if not needs_chunking(full_text):
        messages = [
            {"role": "system", "content": DIRECT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Transcript:\n\n{full_text}"},
        ]
        raw = client.invoke(messages, temperature=0.2, max_tokens=1200)
        parsed = _extract_json(raw)
        return parsed.get("summary", ""), _to_action_items(parsed.get("action_items")), 1

    # --- Map ---
    chunks = chunk_transcript(full_text)
    chunk_notes = [
        _summarize_chunk(client, chunk, i, len(chunks)) for i, chunk in enumerate(chunks)
    ]

    # --- Reduce ---
    combined_notes = "\n\n---\n\n".join(
        f"Notes from part {i + 1}/{len(chunks)}:\n{notes}" for i, notes in enumerate(chunk_notes)
    )
    reduce_messages = [
        {"role": "system", "content": REDUCE_SYSTEM_PROMPT},
        {"role": "user", "content": combined_notes},
    ]
    raw = client.invoke(reduce_messages, temperature=0.2, max_tokens=1500)
    parsed = _extract_json(raw)
    return parsed.get("summary", ""), _to_action_items(parsed.get("action_items")), len(chunks)
