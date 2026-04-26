# ==========================================
# LangGraph Builder (One-Agent Dynamic SQL Pipeline)
# ==========================================

from __future__ import annotations

from langgraph.graph import END, StateGraph

from graph.state import AgentState
from graph.nodes import (
    context_builder_node,
    result_reasoning_node,
    route_query_node,
    schema_selection_node,
    should_continue_after_routing,
    should_retry_after_execution,
    should_retry_after_validation,
    sql_correction_node,
    sql_execution_node,
    sql_generation_node,
    sql_validation_node,
)


def build_graph():
    """
    Build the one-agent HRMS execution graph.

    Final flow:
        route_query
            -> schema_selection
            -> context_builder
            -> sql_generation
            -> sql_validation
                -> sql_execution
                -> sql_correction (if validation fails and retries remain)
            -> sql_execution
                -> sql_correction (if DB error and retries remain)
            -> result_reasoning
            -> END

    Notes:
    - There is only one active execution pipeline.
    - Router decides whether the query should continue or stop as irrelevant.
    - SQL correction is shared for both validation and execution failures.
    - Result reasoning handles both lookup-mode and reasoning-mode responses.
    """
    graph = StateGraph(AgentState)

    # ------------------------------------------
    # ADD NODES
    # ------------------------------------------
    graph.add_node("route_query", route_query_node)
    graph.add_node("schema_selection", schema_selection_node)
    graph.add_node("context_builder", context_builder_node)
    graph.add_node("sql_generation", sql_generation_node)
    graph.add_node("sql_validation", sql_validation_node)
    graph.add_node("sql_execution", sql_execution_node)
    graph.add_node("sql_correction", sql_correction_node)
    graph.add_node("result_reasoning", result_reasoning_node)

    # ------------------------------------------
    # ENTRY POINT
    # ------------------------------------------
    graph.set_entry_point("route_query")

    # ------------------------------------------
    # ROUTER DECISION
    # ------------------------------------------
    graph.add_conditional_edges(
        "route_query",
        should_continue_after_routing,
        {
            "continue": "schema_selection",
            "irrelevant": "result_reasoning",
        },
    )

    # ------------------------------------------
    # MAIN PIPELINE
    # ------------------------------------------
    graph.add_edge("schema_selection", "context_builder")
    graph.add_edge("context_builder", "sql_generation")
    graph.add_edge("sql_generation", "sql_validation")

    # ------------------------------------------
    # VALIDATION DECISION
    # ------------------------------------------
    graph.add_conditional_edges(
        "sql_validation",
        should_retry_after_validation,
        {
            "execute": "sql_execution",
            "correction": "sql_correction",
            "finish": "result_reasoning",
        },
    )

    # After correction, validate again
    graph.add_edge("sql_correction", "sql_validation")

    # ------------------------------------------
    # EXECUTION DECISION
    # ------------------------------------------
    graph.add_conditional_edges(
        "sql_execution",
        should_retry_after_execution,
        {
            "correction": "sql_correction",
            "finish": "result_reasoning",
        },
    )

    # ------------------------------------------
    # FINAL NODE
    # ------------------------------------------
    graph.add_edge("result_reasoning", END)

    compiled_graph = graph.compile()

    # Optional development-time graph print
    #_print_graph_structure(compiled_graph)

    return compiled_graph
