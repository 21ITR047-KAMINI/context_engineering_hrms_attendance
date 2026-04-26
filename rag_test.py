# rag_test.py

from pprint import pprint

from rag.schema_selector import select_schema_bundle
from rag.schema_loader import load_full_schema_document
from rag.business_rules import get_rules
from rag.context_builder import build_context


def guess_intent(query: str) -> str:
    q = query.lower()

    if any(w in q for w in ["why", "reason", "explain", "absent"]):
        return "attendance_explanation"

    if any(w in q for w in ["policy", "rule"]):
        return "policy"

    if any(w in q for w in ["leave", "lop", "permission", "weekoff", "half day"]):
        return "leave"

    return "attendance"


def run_full_rag_debug(query: str):
    intent = guess_intent(query)

    print("\n==============================")
    print("STEP 0: USER QUERY")
    print("==============================")
    print("Query :", query)
    print("Intent:", intent)

    # ------------------------------------------
    # STEP 1: SCHEMA SELECTOR
    # ------------------------------------------
    bundle = select_schema_bundle(
        query=query,
        intent=intent,
        use_llm=False
    )

    selected_tables = bundle["selected_tables"]
    selected_columns = bundle["selected_columns"]

    print("\n==============================")
    print("STEP 1: schema_selector.py")
    print("==============================")
    print("Selected Tables:")
    pprint(selected_tables)

    print("\nSelected Columns:")
    pprint(selected_columns)

    # ------------------------------------------
    # STEP 2: SCHEMA LOADER
    # ------------------------------------------
    full_schema = load_full_schema_document()
    schema_tables = full_schema.get("tables", {})

    selected_schema = {
        table: schema_tables.get(table)
        for table in selected_tables
        if table in schema_tables
    }

    print("\n==============================")
    print("STEP 2: schema_loader.py")
    print("==============================")
    print("Loaded Schema Metadata:")

    for table, meta in selected_schema.items():
        print(f"\nTable: {table}")
        print("Columns:", list(meta.get("columns", {}).keys())[:10])
        print("Domain :", meta.get("domain"))
        print("Used For:", meta.get("used_for"))

    # ------------------------------------------
    # STEP 3: BUSINESS RULES
    # ------------------------------------------
    rules = get_rules(
        intent=intent,
        tables=selected_tables,
        include_policy_json=False
    )

    print("\n==============================")
    print("STEP 3: business_rules.py")
    print("==============================")
    print(f"Total Rules: {len(rules)}")

    print("\nSample Rules:")
    for r in rules[:10]:
        print("-", r)

    # ------------------------------------------
    # STEP 4: CONTEXT BUILDER
    # ------------------------------------------
    context = build_context(
        query=query,
        intent=intent,
        schema=selected_schema,
        rules=rules
    )

    print("\n==============================")
    print("STEP 4: context_builder.py")
    print("==============================")

    print("\nBusiness Focus:")
    pprint(context.get("business_focus"))

    print("\nQuery Guidance:")
    pprint(context.get("query_guidance"))

    print("\nJoin Hints:")
    pprint(context.get("join_hints"))

    print("\nLLM Context Preview:")
    llm_ctx = context.get("llm_context", {})
    pprint({
        "tables": llm_ctx.get("tables"),
        "intent": llm_ctx.get("intent"),
        "rules_count": len(llm_ctx.get("rules", []))
    })

    print("\n==============================")
    print("RAG FLOW COMPLETED")
    print("==============================")


if __name__ == "__main__":
    user_query = input("Enter your HRMS query: ").strip()

    if not user_query:
        raise ValueError("Query cannot be empty.")

    run_full_rag_debug(user_query)