from typing import Any, Dict, List, Literal, Optional, TypedDict


IntentType = Literal[
    "attendance",
    "leave",
    "attendance_explanation",
    "policy",
    "irrelevant",
]

ModeType = Literal[
    "lookup",
    "reasoning",
]


class DBResult(TypedDict, total=False):
    """
    Normalized database execution result.
    """
    rows: List[Dict[str, Any]]
    columns: List[str]
    error: Optional[str]
    row_count: int


class AgentState(TypedDict, total=False):
    """
    Shared working state passed between graph nodes.

    This state is designed to support the full dynamic pipeline:
    query -> routing -> schema selection -> context building
    -> SQL generation -> validation -> execution -> correction
    -> result reasoning -> final response

    Keep this file as the single source of truth for all keys
    written/read by graph nodes.
    """

    # ----------------------------
    # User input / routing
    # ----------------------------
    query: str
    intent: IntentType
    mode: ModeType

    # ----------------------------
    # Schema / context engineering
    # ----------------------------
    selected_tables: List[str]
    schema_context: Dict[str, Any]
    business_context: List[str]
    join_hints: List[str]
    llm_context: Dict[str, Any]
    full_context: Dict[str, Any]

    # ----------------------------
    # SQL generation / correction
    # ----------------------------
    sql: str
    previous_sql: str
    validation_error: str
    db_error: str
    retry_count: int
    max_retries: int

    # ----------------------------
    # Execution / response
    # ----------------------------
    db_result: DBResult
    response: str


def create_initial_state(query: str, max_retries: int = 2) -> AgentState:
    """
    Build a clean initial state for graph invocation.

    Example:
        state = create_initial_state("Show attendance for employee AD25061070")
    """
    return AgentState(
        query=query.strip(),
        intent="irrelevant",
        mode="lookup",
        selected_tables=[],
        schema_context={},
        business_context=[],
        join_hints=[],
        llm_context={},
        full_context={},
        sql="",
        previous_sql="",
        validation_error="",
        db_error="",
        retry_count=0,
        max_retries=max_retries,
        db_result=DBResult(
            rows=[],
            columns=[],
            error=None,
            row_count=0,
        ),
        response="",
    )


def reset_errors(state: AgentState) -> AgentState:
    """
    Clear validation and DB execution errors before retry/correction.
    """
    state["validation_error"] = ""
    state["db_error"] = ""
    return state


def mark_retry(state: AgentState) -> AgentState:
    """
    Increment retry counter safely.
    """
    state["retry_count"] = state.get("retry_count", 0) + 1
    return state


def can_retry(state: AgentState) -> bool:
    """
    Check whether correction/retry is still allowed.
    """
    return state.get("retry_count", 0) < state.get("max_retries", 2)