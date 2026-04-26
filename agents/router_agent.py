# ==========================================
# Router Agent
# ==========================================

from __future__ import annotations

import re
from typing import Any, Dict

from llm.provider import get_llm


VALID_ROUTES = {
    "attendance",
    "leave",
    "attendance_explanation",
    "policy",
    "irrelevant",
}


ROUTER_PROMPT = """
You are an expert intent router for an HRMS AI system.

Your task is to classify the user query into EXACTLY ONE category.

VALID CATEGORIES:
1. attendance
2. leave
3. attendance_explanation
4. policy
5. irrelevant

CATEGORY DEFINITIONS:

attendance:
- login/logout queries
- attendance records
- worked hours / worked minutes
- monthly attendance summaries
- late coming
- missing punch
- shift timing questions related to attendance
- employee day-wise attendance details

leave:
- leave status
- leave request details
- leave type
- leave reason
- leave dates
- leave balance
- comp-off
- statutory leave
- daily leave records

attendance_explanation:
- any WHY / REASON / EXPLAIN query about attendance, leave outcome, LOP, half-day, absent marking, permission, weekoff, or payroll impact
- examples:
  - why was employee absent
  - explain half day
  - reason for lop
  - why was this marked as leave
  - why did this become permission

policy:
- HR rules
- leave policy
- attendance policy
- week off rules
- permission rules
- CL policy
- company rules
- eligibility or limit questions

irrelevant:
- not related to HRMS / attendance / leave / policy

IMPORTANT RULES:
- Return ONLY one category
- No explanation
- No punctuation
- No JSON
- No extra text
- If the query asks why / explain / reason, prefer attendance_explanation
- If the query is about worked hours, login/logout, or attendance facts, prefer attendance
- If the query is about leave records/details, prefer leave
- If the query is about rules/limits/eligibility, prefer policy
- If unsure but HRMS-related, choose the closest valid category instead of irrelevant

EXAMPLES:

Query: Show login details for employee AD25061070
attendance

Query: What is the total worked hours for employee AD25061070 in March 2026
attendance

Query: Show leave details for employee AD25061070
leave

Query: Why was employee AD25061070 marked absent on 2026-03-03
attendance_explanation

Query: Why is there LOP this month
attendance_explanation

Query: What is the CL policy
policy

Query: Tell me a joke
irrelevant
""".strip()


# ------------------------------------------
# HELPERS
# ------------------------------------------
def _extract_text_from_response(response: Any) -> str:
    if response is None:
        return ""

    if isinstance(response, str):
        return response.strip()

    content = getattr(response, "content", None)

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text")
                if text_value is not None:
                    parts.append(str(text_value))
            else:
                parts.append(str(item))
        return " ".join(parts).strip()

    return str(response).strip()


def _normalize_route(route: str) -> str:
    route = (route or "").strip().lower()

    if route in VALID_ROUTES:
        return route

    route = re.sub(r"[^a-zA-Z_ ]+", " ", route).strip().lower()

    # Normalize old / alternate labels
    if route == "explanation":
        return "attendance_explanation"

    if route == "shift":
        return "attendance"

    # Soft matching
    if "attendance_explanation" in route:
        return "attendance_explanation"
    if "explanation" in route or "reason" in route or "why" in route:
        return "attendance_explanation"
    if "attendance" in route:
        return "attendance"
    if "leave" in route or "compoff" in route or "comp off" in route or "comp-off" in route:
        return "leave"
    if "policy" in route or "rule" in route:
        return "policy"
    if "irrelevant" in route:
        return "irrelevant"
    if "shift" in route:
        return "attendance"

    return "attendance"


def _keyword_fallback(query: str) -> str:
    """
    Deterministic fallback when LLM is unavailable or returns noisy output.
    """
    q = (query or "").strip().lower()

    if not q:
        return "irrelevant"

    explanation_terms = [
        "why", "reason", "explain", "what caused", "how come",
        "why was", "why is", "why did"
    ]
    if any(term in q for term in explanation_terms):
        return "attendance_explanation"

    policy_terms = [
        "policy", "rule", "allowed", "eligibility", "eligible",
        "limit", "limits", "company rule", "permission rule", "cl policy"
    ]
    if any(term in q for term in policy_terms):
        return "policy"

    leave_terms = [
        "leave", "lop", "comp off", "comp-off", "compoff",
        "statutory leave", "leave balance", "leave type", "leave reason"
    ]
    if any(term in q for term in leave_terms):
        return "leave"

    attendance_terms = [
        "attendance", "login", "logout", "logoff", "worked hours",
        "worked minutes", "working hours", "working minutes",
        "late", "missing punch", "shift", "punch", "present", "absent"
    ]
    if any(term in q for term in attendance_terms):
        return "attendance"

    return "irrelevant"


def _infer_mode(route: str) -> str:
    if route in {"attendance_explanation", "policy"}:
        return "reasoning"
    return "lookup"


def _infer_complexity(route: str, query: str) -> str:
    q = (query or "").strip().lower()

    if route in {"attendance_explanation", "policy"}:
        return "explanation"

    if any(term in q for term in ["count", "sum", "total", "hours", "minutes", "monthly", "month", "summary"]):
        return "aggregate"

    if any(term in q for term in ["status", "week off", "weekoff", "permission", "half day", "half-day", "lop"]):
        return "status_interpretation"

    return "simple"


# ------------------------------------------
# PUBLIC API
# ------------------------------------------
def router_agent(query: str) -> str:
    """
    Backward-compatible router:
    returns only the normalized route string.
    """
    result = route_query(query)
    return result["intent"]


def route_query(query: str) -> Dict[str, str]:
    """
    Production router:
    returns structured routing output.

    Example:
    {
        "intent": "attendance",
        "mode": "lookup",
        "complexity": "simple"
    }
    """
    clean_query = (query or "").strip()

    print(f"\n[ROUTER] Incoming Query: {clean_query}")

    if not clean_query:
        return {
            "intent": "irrelevant",
            "mode": "lookup",
            "complexity": "simple",
        }

    try:
        llm = get_llm("router")

        prompt = f"{ROUTER_PROMPT}\n\nUser Query:\n{clean_query}"
        response = llm.invoke(prompt)
        raw_output = _extract_text_from_response(response).lower()

        print(f"[ROUTER] Raw LLM Output: {raw_output}")

        intent = _normalize_route(raw_output)

        if intent not in VALID_ROUTES:
            intent = _keyword_fallback(clean_query)

    except Exception as exc:
        print("[ROUTER ERROR]:", str(exc))
        intent = _keyword_fallback(clean_query)

    mode = _infer_mode(intent)
    complexity = _infer_complexity(intent, clean_query)

    print(f"[ROUTER] Final Route: {intent}")
    print(f"[ROUTER] Mode: {mode}")
    print(f"[ROUTER] Complexity: {complexity}")

    return {
        "intent": intent,
        "mode": mode,
        "complexity": complexity,
    }