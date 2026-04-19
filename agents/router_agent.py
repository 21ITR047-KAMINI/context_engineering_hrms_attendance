# ==========================================
# Router Agent (100% LLM-Based - Production)
# ==========================================

from llm.provider import get_llm

llm = get_llm("router")


ROUTER_PROMPT = """
You are an intelligent routing agent for an HR AI system.

Your job is to classify the user query into EXACTLY ONE category:

CATEGORIES:

1. attendance
   → login/logout, working hours, missing punch, attendance reports

2. leave
   → leave status, leave request, leave balance, leave reason

3. attendance_explanation
   → ANY query asking WHY something happened
   (examples: why absent, reason for half-day, explain LOP)

4. policy
   → HR rules, attendance policy, company rules

5. irrelevant
   → not related to HR or attendance system
   (examples: weather, jokes, general questions)


IMPORTANT RULES:

- Return ONLY one word from the categories above
- Do NOT explain
- Do NOT add punctuation
- Do NOT return multiple categories
- If unsure → choose the closest category


EXAMPLES:

Query: Show login details
→ attendance

Query: Why was employee absent?
→ attendance_explanation

Query: What is leave status?
→ leave

Query: What is the weather today?
→ irrelevant
"""


def router_agent(query: str) -> str:
    def _normalize_route(raw: str) -> str:
        route = (raw or "").strip().lower()

        alias_map = {
            "explanation": "attendance_explanation",
            "reasoning": "attendance_explanation",
            "why": "attendance_explanation",
            "shift": "attendance",
        }
        route = alias_map.get(route, route)

        valid_routes = {
            "attendance",
            "leave",
            "attendance_explanation",
            "policy",
            "irrelevant",
        }
        if route in valid_routes:
            return route

        if "attendance" in route:
            return "attendance"
        if "leave" in route:
            return "leave"
        if "policy" in route:
            return "policy"
        if "explain" in route or "reason" in route or "why" in route:
            return "attendance_explanation"
        if "shift" in route:
            return "attendance"

        return "irrelevant"

    try:
        print(f"\n[ROUTER] Incoming Query: {query}")

        # --------------------------------------
        # STEP 1: Call LLM
        # --------------------------------------
        response = llm.invoke(
            f"{ROUTER_PROMPT}\n\nUser Query:\n{query}"
        )

        raw_content = getattr(response, "content", response)
        route = str(raw_content).strip().lower()

        print(f"[ROUTER] Raw LLM Output: {route}")
        normalized = _normalize_route(route)
        print(f"[ROUTER] Normalized Route: {normalized}")
        return normalized

    except Exception as e:
        print("[ROUTER ERROR]:", str(e))
        return "irrelevant"
