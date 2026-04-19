# ==========================================
# Business Rules
# ==========================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_POLICY_PATH = Path("/mnt/data/Software_dept_leave_policy.json")


VALID_INTENTS = {
    "attendance",
    "leave",
    "attendance_explanation",
    "policy",
    "irrelevant",
}


# ------------------------------------------
# HELPERS
# ------------------------------------------
def _normalize_intent(intent: Optional[str]) -> str:
    value = (intent or "").strip().lower()
    return value if value in VALID_INTENTS else "attendance"


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    output: List[str] = []

    for item in items:
        cleaned = str(item).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            output.append(cleaned)

    return output


def _load_policy_json(policy_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load optional department policy JSON.
    If file is missing, return empty dict without failing the RAG flow.
    """
    path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH

    if not path.exists() or not path.is_file():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _table_set(tables: List[str]) -> set[str]:
    return {str(table).strip() for table in tables if str(table).strip()}


# ------------------------------------------
# CORE BASE RULES
# ------------------------------------------
COMMON_RULES = [
    "Use database records as the source of truth; do not assume facts not supported by retrieved schema and query results.",
    "Prefer the minimum business interpretation needed for the question unless the user explicitly asks for explanation or policy reasoning.",
    "When multiple tables appear to overlap, prefer the table that stores the operational decision or status over a purely descriptive or reference table.",
]

ATTENDANCE_RULES = [
    "Attendance queries usually rely first on login_mast for login_date, login_time, logoff_time, shift_code, and login behavior.",
    "Shift interpretation should use shift_details and employee shift assignment tables when attendance timing needs comparison with expected shift timing.",
    "Late coming, shift mismatch, missing login, or missing logout should be interpreted only when the underlying shift and attendance records support that conclusion.",
]

LEAVE_RULES = [
    "Leave queries usually require emp_leave_setting for processed leave status and Leave_detail or leave_dates for leave request details and date-wise workflow.",
    "Approved leave on the same employee and date can explain absence or non-working attendance states when supported by records.",
    "If leave status, leave dates, and leave detail records conflict, prefer the most operationally current status table unless the user explicitly asks about workflow history.",
]

EXPLANATION_RULES = [
    "For why-questions, combine attendance evidence, leave evidence, shift timing, and monthly summary evidence when required before concluding the reason.",
    "Do not claim a causal reason such as absent, half-day, late, or LOP unless supporting evidence exists across the relevant attendance, leave, shift, or monthly summary tables.",
    "For explanation queries, consider whether leave, statutory leave, holidays, weekly off, shift timing, permissions, or LOP-related monthly summaries change the final interpretation.",
]

POLICY_RULES = [
    "Policy questions should be answered using rule tables, policy metadata, and department policy JSON when available, instead of relying only on transactional records.",
    "Employee-specific exception tables override generic policy tables when both are available and applicable.",
    "Reference tables such as mstWeekoffType or mstCLPolicyRule should be used to interpret policy names and counts, not as proof of actual attendance events by themselves.",
]


# ------------------------------------------
# TABLE-SPECIFIC RULES
# ------------------------------------------
TABLE_RULES: Dict[str, List[str]] = {
    "login_mast": [
        "login_mast is the primary attendance event table for login and logout activity.",
        "Compare login_time and logoff_time with shift timing only when shift context is available.",
        "A missing or incomplete login_mast record alone should not automatically be treated as policy violation without checking leave, holiday, or shift context when relevant.",
    ],
    "emp_compoff": [
        "emp_compoff should be used for compensatory off requests, approval state, availability, and comp-off reasoning.",
        "Comp-off availability and approval must be checked before concluding that comp-off can explain absence or non-working attendance.",
    ],
    "Leave_detail": [
        "Leave_detail stores leave application details such as reason, type, application date, and timing.",
        "Use Leave_detail when the user asks about leave reason, type, applied date, or leave duration details.",
    ],
    "leave_dates": [
        "leave_dates provides day-wise leave entries and approval workflow at the date level.",
        "Use leave_dates when validating whether a specific date was covered by leave and how that date was approved.",
    ],
    "emp_leave_setting": [
        "emp_leave_setting should be treated as the processed leave status table for employee-date leave interpretation.",
        "Fields such as leave_status, LopCount, EmpLop, markedby, and isApproval are important for operational leave outcome reasoning.",
    ],
    "mstEmployeeStatutoryLeave": [
        "mstEmployeeStatutoryLeave should be used for employee statutory leave records tied to special leave dates.",
    ],
    "mstLeaveStatusStatutory": [
        "mstLeaveStatusStatutory defines statutory leave types and year-wise allocations; it is a policy/reference source, not an attendance event table.",
    ],
    "emp_default_shift": [
        "emp_default_shift stores the employee's default assigned shift and should be used when no better date-range shift assignment is available.",
    ],
    "trnEmployeeWeeklyShift": [
        "trnEmployeeWeeklyShift stores temporary or date-range shift assignments and should take precedence over default shift when the attendance date falls within the weekly shift range.",
    ],
    "shift_details": [
        "shift_details is the authoritative shift timing reference for expected in-time, out-time, and rest interval interpretation.",
        "Use shift_details when explaining late coming, shift duration, weekly off logic, or whether a shift crosses to the next day.",
    ],
    "mstShiftNameAndTime": [
        "mstShiftNameAndTime is a reference table for shift naming and canonical timing display.",
    ],
    "cl_detail": [
        "cl_detail is the monthly leave balance and summary table used for CL, LOP, permissions, holidays, and working-days reasoning.",
        "Use cl_detail for monthly summaries, LOP explanations, permission-based reasoning, and leave balance interpretation.",
    ],
    "trnExceptionEmployeeCLPolicy": [
        "trnExceptionEmployeeCLPolicy contains employee-specific exceptions to standard CL policy and should override generic CL policy where applicable.",
    ],
    "mstCLPolicyRule": [
        "mstCLPolicyRule defines generic casual leave policy counts and should be used for policy explanation rather than transactional attendance proof.",
    ],
    "mstWeekoffType": [
        "mstWeekoffType is a reference table for weekly off naming and type interpretation.",
    ],
    "holiday_master": [
        "holiday_master should be used to determine whether a date is a configured holiday before concluding absence or late-related penalties.",
    ],
    "trnCandidateHolidayMapping": [
        "trnCandidateHolidayMapping should be checked when holiday applicability can differ by employee or category.",
    ],
    "pay_mst_category": [
        "pay_mst_category controls category-level attendance, permission, holiday, and LOP policy behavior.",
    ],
    "mstRestrictLeaveMarkingCategory": [
        "mstRestrictLeaveMarkingCategory defines leave-marking restrictions by employee category and should be considered for policy or restriction questions.",
    ],
}


# ------------------------------------------
# POLICY JSON -> RULES
# ------------------------------------------
def _extract_software_policy_rules(policy_data: Dict[str, Any]) -> List[str]:
    """
    Convert uploaded department policy JSON into plain business rules.
    """
    if not policy_data:
        return []

    rules: List[str] = []
    leave_policy = policy_data.get("leave_policy", {})
    attendance_integration = policy_data.get("attendance_integration_rules", {})

    casual_leave = leave_policy.get("casual_leave", {})
    permission_policy = leave_policy.get("permission_policy", {})
    leave_penalty = leave_policy.get("leave_penalty", {})
    attendance_behavior_rules = leave_policy.get("attendance_behavior_rules", {})
    weekend_policy = leave_policy.get("weekend_policy", {})
    special_leaves = leave_policy.get("special_leaves", {})
    holiday_policy = leave_policy.get("holiday_policy", {})

    # Casual leave
    standard = casual_leave.get("allocation", {}).get("standard", {})
    external = casual_leave.get("allocation", {}).get("external_qsecure", {})

    if standard:
        annual_quota = standard.get("annual_quota")
        monthly_limit = standard.get("monthly_limit")
        if annual_quota is not None:
            rules.append(
                f"Software department standard employees have an annual casual leave quota of {annual_quota} days."
            )
        if monthly_limit is not None:
            rules.append(
                f"Software department standard employees have a monthly casual leave limit of {monthly_limit} day."
            )

    if external:
        annual_quota = external.get("annual_quota")
        if annual_quota is not None:
            rules.append(
                f"Software department external QSecure employees have an annual casual leave quota of {annual_quota} days."
            )

    eligibility = casual_leave.get("eligibility", {})
    if eligibility:
        if eligibility.get("interns") is False:
            rules.append("Software department interns are not eligible for casual leave.")
        if eligibility.get("standard_employees") is True:
            rules.append("Software department standard employees are eligible for casual leave.")
        if eligibility.get("external_qsecure") is True:
            rules.append("Software department external QSecure employees are eligible for casual leave.")

    carry_forward = casual_leave.get("carry_forward", {})
    if carry_forward.get("allowed") is True:
        rules.append("Casual leave carry forward is allowed on a monthly basis only and cannot be carried to the next year.")

    # Permission policy
    if permission_policy:
        allowed = permission_policy.get("allowed_per_month")
        duration = permission_policy.get("duration_hours_per_permission")
        if allowed is not None and duration is not None:
            rules.append(
                f"Software department permission policy allows {allowed} permissions per month, each up to {duration} hours."
            )

    # Leave penalty
    unapproved_leave = leave_penalty.get("unapproved_leave", {})
    uninformed_leave = leave_penalty.get("uninformed_leave", {})

    if unapproved_leave.get("penalty_multiplier") is not None:
        rules.append(
            f"Unapproved leave has a penalty multiplier of {unapproved_leave['penalty_multiplier']} in the Software department policy."
        )

    if uninformed_leave.get("penalty_multiplier") is not None:
        rules.append(
            f"Uninformed leave has a penalty multiplier of {uninformed_leave['penalty_multiplier']} in the Software department policy."
        )

    additional_action = uninformed_leave.get("additional_action", [])
    if additional_action:
        rules.append(
            "Uninformed leave may trigger additional actions such as "
            + ", ".join(str(item) for item in additional_action)
            + "."
        )

    # Attendance behavior
    if attendance_behavior_rules:
        combined_limit = attendance_behavior_rules.get("late_and_permission_combined_limit")
        exceed_action = attendance_behavior_rules.get("exceed_limit_action")
        grace_allowed = attendance_behavior_rules.get("grace_time_allowed")

        if combined_limit is not None and exceed_action:
            rules.append(
                f"If the combined late-and-permission count exceeds {combined_limit}, the action is {exceed_action} under Software department policy."
            )

        if grace_allowed is False:
            rules.append("Software department attendance behavior policy does not allow grace time.")

    # Weekend policy
    weekend_rules = weekend_policy.get("rules", {})
    less_than_one_year = weekend_rules.get("less_than_1_year", {})
    greater_equal_one_year = weekend_rules.get("greater_than_or_equal_1_year", {})

    if less_than_one_year:
        working_days = less_than_one_year.get("working_days", [])
        shift_hours = less_than_one_year.get("shift_hours")
        if working_days:
            rules.append(
                "For Software department employees with less than 1 year experience, working Saturdays include "
                + ", ".join(str(item) for item in working_days)
                + "."
            )
        if shift_hours is not None:
            rules.append(
                f"For Software department employees with less than 1 year experience, weekend shift hours are {shift_hours}."
            )

    if greater_equal_one_year:
        saturday = greater_equal_one_year.get("saturday")
        shift_hours = greater_equal_one_year.get("shift_hours")
        if saturday:
            rules.append(
                f"For Software department employees with 1 year or more experience, Saturday is treated as {saturday}."
            )
        if shift_hours is not None:
            rules.append(
                f"For Software department employees with 1 year or more experience, weekend shift hours are {shift_hours}."
            )

    # Special leaves
    marriage_leave = special_leaves.get("marriage_leave", {})
    if marriage_leave.get("days") is not None:
        rules.append(
            f"Marriage leave in the Software department policy allows {marriage_leave['days']} days."
        )

    sick_leave = special_leaves.get("sick_leave", {})
    if sick_leave.get("days") is not None:
        rules.append(
            f"Sick leave in the Software department policy allows {sick_leave['days']} days."
        )

    death_leave = special_leaves.get("death_leave", {})
    if death_leave.get("days") is not None:
        rules.append(
            f"Death leave in the Software department policy allows {death_leave['days']} days."
        )

    paternity_leave = special_leaves.get("paternity_leave", {})
    if paternity_leave.get("days") is not None:
        rules.append(
            f"Paternity leave in the Software department policy allows {paternity_leave['days']} days."
        )

    # Holiday policy
    holidays = holiday_policy.get("holidays", [])
    if holidays:
        rules.append(
            "Software department holiday policy includes: " + ", ".join(str(item) for item in holidays) + "."
        )

    # Integration flow
    processing_flow = attendance_integration.get("processing_flow", [])
    if processing_flow:
        rules.append(
            "Attendance and leave integration processing flow is: "
            + " -> ".join(str(item) for item in processing_flow)
            + "."
        )

    return _dedupe_keep_order(rules)


# ------------------------------------------
# TABLE-BASED RULE AGGREGATION
# ------------------------------------------
def _get_table_specific_rules(tables: List[str]) -> List[str]:
    rules: List[str] = []
    for table in tables:
        rules.extend(TABLE_RULES.get(table, []))
    return _dedupe_keep_order(rules)


def _get_cross_table_rules(tables: List[str], intent: str) -> List[str]:
    selected = _table_set(tables)
    rules: List[str] = []

    if {"login_mast", "emp_leave_setting"}.issubset(selected):
        rules.append(
            "When login_mast and emp_leave_setting are both selected, compare attendance date and leave date before concluding whether leave explains an attendance outcome."
        )

    if {"Leave_detail", "leave_dates", "emp_leave_setting"}.issubset(selected):
        rules.append(
            "When Leave_detail, leave_dates, and emp_leave_setting are all selected, use leave_dates for day-wise validation, Leave_detail for request details, and emp_leave_setting for processed leave status."
        )

    if {"login_mast", "shift_details"}.issubset(selected):
        rules.append(
            "When login_mast and shift_details are both selected, compare actual login/logout times with shift timing before inferring late, shortfall, or shift mismatch."
        )

    if {"login_mast", "cl_detail"}.issubset(selected):
        rules.append(
            "When login_mast and cl_detail are both selected, use login_mast for date-level attendance evidence and cl_detail for monthly summary, LOP, permission, and leave balance interpretation."
        )

    if {"emp_default_shift", "trnEmployeeWeeklyShift", "shift_details"}.issubset(selected):
        rules.append(
            "When both default shift and weekly shift tables are selected, weekly shift assignments should take precedence for dates within their active range, and shift_details should provide timing interpretation."
        )

    if {"mstCLPolicyRule", "trnExceptionEmployeeCLPolicy"}.issubset(selected):
        rules.append(
            "Employee-specific CL policy exceptions should override the generic CL policy when both tables are selected and applicable."
        )

    if {"holiday_master", "login_mast"}.issubset(selected):
        rules.append(
            "Check whether the attendance date falls on a holiday before concluding absence or attendance penalty."
        )

    if intent == "attendance_explanation":
        rules.append(
            "For explanation queries, prefer evidence reconciliation across attendance, leave, shift, holiday, and monthly summary tables instead of relying on one table only."
        )

    if intent == "policy":
        rules.append(
            "For policy questions, distinguish between actual employee transactions and generic policy/reference definitions before answering."
        )

    return _dedupe_keep_order(rules)


# ------------------------------------------
# PUBLIC FUNCTION
# ------------------------------------------
def get_rules(
    intent: str,
    tables: List[str],
    policy_path: Optional[str] = None,
    include_policy_json: bool = True,
) -> List[str]:
    """
    Return business rules relevant to the current query intent and selected tables.

    Sources:
    1. Base intent rules
    2. Table-specific rules
    3. Cross-table reasoning rules
    4. Optional department policy JSON rules

    Args:
        intent:
            attendance / leave / attendance_explanation / policy / irrelevant
        tables:
            selected table names
        policy_path:
            optional override path for department policy JSON
        include_policy_json:
            whether to include uploaded department policy rules

    Returns:
        list[str]
    """
    safe_intent = _normalize_intent(intent)
    selected_tables = [str(table).strip() for table in tables if str(table).strip()]

    rules: List[str] = []
    rules.extend(COMMON_RULES)

    if safe_intent == "attendance":
        rules.extend(ATTENDANCE_RULES)
    elif safe_intent == "leave":
        rules.extend(LEAVE_RULES)
    elif safe_intent == "attendance_explanation":
        rules.extend(ATTENDANCE_RULES)
        rules.extend(LEAVE_RULES)
        rules.extend(EXPLANATION_RULES)
    elif safe_intent == "policy":
        rules.extend(POLICY_RULES)

    rules.extend(_get_table_specific_rules(selected_tables))
    rules.extend(_get_cross_table_rules(selected_tables, safe_intent))

    if include_policy_json:
        policy_data = _load_policy_json(policy_path=policy_path)
        rules.extend(_extract_software_policy_rules(policy_data))

    return _dedupe_keep_order(rules)