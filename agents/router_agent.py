# ==========================================
# Router Agent (100% LLM-Based - Production)
# ==========================================

from llm.provider import get_llm

llm = get_llm()


ROUTER_PROMPT = """
You are an intelligent routing agent for an HR AI system.

Your job is to classify the user query into EXACTLY ONE category:

CATEGORIES:

1. attendance
   → login/logout, working hours, missing punch, attendance reports

2. leave
   → leave status, leave request, leave balance, leave reason

3. shift
   → shift timing, shift allocation, shift mismatch

4. policy
   → HR rules, attendance policy, company rules

5. explanation
   → ANY query asking WHY something happened
   (examples: why absent, reason for half-day, explain LOP)

6. irrelevant
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
→ explanation

Query: What is leave status?
→ leave

Query: What is the weather today?
→ irrelevant
"""


def router_agent(query: str) -> str:
    try:
        print(f"\n[ROUTER] Incoming Query: {query}")

        # --------------------------------------
        # STEP 1: Call LLM
        # --------------------------------------
        response = llm.invoke(
            f"{ROUTER_PROMPT}\n\nUser Query:\n{query}"
        )

        route = response.content.strip().lower()

        print(f"[ROUTER] Raw LLM Output: {route}")

        # --------------------------------------
        # STEP 2: Strict Validation (IMPORTANT)
        # --------------------------------------
        valid_routes = {
            "attendance",
            "leave",
            "shift",
            "policy",
            "explanation",
            "irrelevant"
        }

        if route in valid_routes:
            return route

        # --------------------------------------
        # STEP 3: Safety Normalization
        # --------------------------------------
        if "attendance" in route:
            return "attendance"
        elif "leave" in route:
            return "leave"
        elif "shift" in route:
            return "shift"
        elif "policy" in route:
            return "policy"
        elif "explain" in route or "reason" in route:
            return "explanation"

        # --------------------------------------
        # STEP 4: Final Fallback
        # --------------------------------------
        print("[ROUTER] Fallback → attendance")
        return "attendance"

    except Exception as e:
        print("[ROUTER ERROR]:", str(e))
        return "attendance"