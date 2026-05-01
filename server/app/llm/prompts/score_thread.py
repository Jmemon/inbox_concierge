import json


SYSTEM_PROMPT = """You evaluate whether an email thread fits a user's description
of a bucket they're considering creating. Given the description and one thread,
score the match 0-10:
 - 10: obvious match
 - 7-9: clearly a match
 - 4-6: borderline ("near miss")
 - 0-3: clearly not a match

Also extract:
 - rationale: one short line explaining why
 - snippet: a verbatim quotation from the thread that most influenced your score

Output exactly one line of JSON, no other text or code fences:
  {"score": <int 0-10>, "rationale": "<one line>", "snippet": "<verbatim>"}
"""


def build_user_message(*, thread_str: str, name: str, description: str) -> str:
    return (
        f'User wants to create a bucket called "{name}" described as:\n\n'
        f"{description}\n\nThread to score:\n\n{thread_str}"
    )


def parse_response(text: str) -> dict | None:
    text = (text or "").strip()
    if text.startswith("```"):
        s, e = text.find("{"), text.rfind("}")
        if s >= 0 and e > s: text = text[s : e + 1]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    score = obj.get("score")
    if not isinstance(score, int) or not 0 <= score <= 10:
        return None
    return {"score": score, "rationale": str(obj.get("rationale", "")),
            "snippet": str(obj.get("snippet", ""))}
