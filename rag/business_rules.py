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


def _table_set(tables: List[str]) -> set[str]:
    return {str(table).strip() for table in tables if str(table).strip()}


def _load_policy_json(policy_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load optional department policy JSON.
    If missing, return empty dict without breaking RAG flow.
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


# ------------------------------------------
# CORE CROSS-CUTTING RULES
# ------------------------------------------
COMMON_RULES = [
    "Use database records as the source of truth; do not assume facts not supported by retrieved schema and query results.",
    "Prefer the minimum business interpretation required by the question. Do not over-explain unless the user explicitly asks why or asks for a rule/policy explanation.",
    "Prefer the minimum number of tables required to answer the query correctly.",
    "Prefer operational status tables over descriptive or reference tables when multiple tables overlap in meaning.",
    "Do not invent columns, table names, joins, status meanings, or business rules that are not supported by schema metadata and known domain rules.",
    "If a query can be answered from a single table, avoid joins.",
    "For SQL generation, assume SQL Server semantics unless explicitly configured otherwise.",
]

HRMS_DAY_STATUS_RULES = [
    "emp_leave_setting is the processed employee-date status layer and should be treated as the primary source for final leave/day-status interpretation.",
    "For many day-status queries, no row in emp_leave_setting for an employee on a date may indicate a normal working day rather than missing data.",
    "leave_status code W should be interpreted as Week Off when supported by operational records.",
    "leave_status code P should be interpreted as Permission when supported by operational records.",
    "leave_status code F should usually be interpreted as Full Day Leave when supported by operational records.",
    "leave_remark can contain business meaning that is not fully captured in leave_status alone.",
    "leave_remark text containing 'No Balance' should be treated as a strong signal of Loss of Pay (LOP) reasoning when relevant.",
    "login_mast is the attendance event truth for login, logout, and worked-time calculations.",
]


# ------------------------------------------
# INTENT-SPECIFIC RULES
# ------------------------------------------
ATTENDANCE_RULES = [
    "Attendance lookup queries should usually start from login_mast.",
    "For login/logout, working minutes, working hours, and punch-based attendance queries, login_mast is usually sufficient.",
    "For simple attendance lookup queries, do not join leave tables unless the user explicitly asks for leave-related interpretation.",
    "Use emp_id and login_date as the natural business keys for day-level attendance lookup in login_mast.",
    "When calculating worked time, use login_time and logoff_time from login_mast.",
    "Worked time calculations should ignore rows where login_time or logoff_time is null unless the user explicitly asks to inspect incomplete punches.",
    "If login_mast has both login_time and logoff_time, the day can generally be treated as worked unless stronger operational evidence says otherwise.",
    "If only one of login_time or logoff_time is present, interpret as partial/incomplete punch rather than automatically assuming leave or absence.",
    "Use shift tables only when the user asks about shift timing, late coming, expected hours, or shift-based explanations.",
]

LEAVE_RULES = [
    "Leave queries should usually start from emp_leave_setting for final processed leave status.",
    "Use Leave_detail only when the user asks for leave reason, leave type, apply date, or application-level detail.",
    "Use leave_dates only when the user asks about day-wise leave coverage, half-day splits, or approval workflow at the date level.",
    "For basic leave/day-status queries, emp_leave_setting can be sufficient without joining Leave_detail or leave_dates.",
    "Use leave_id as the primary join key between emp_leave_setting, Leave_detail, and leave_dates when joins are required.",
    "For employee-date leave lookup, emp_id + leave_date is the important operational lookup pattern.",
    "If the user asks only whether the employee was on leave on a date, do not over-join.",
    "If the user asks for exact leave type, reason, or applied date, then Leave_detail becomes relevant.",
    "If the user asks about approval state on a specific leave date or half-day value, then leave_dates becomes relevant.",
]

EXPLANATION_RULES = [
    "Explanation queries should combine evidence from attendance, processed leave/day status, shift timing, holiday applicability, and monthly summary only when required by the question.",
    "Do not claim a causal reason such as absent, half-day, late, or LOP unless supporting evidence exists in operational tables.",
    "For why-questions, prefer evidence in this general order: processed day-status -> attendance punches -> shift expectations -> monthly summaries -> policy/reference data.",
    "If emp_leave_setting and login_mast disagree, prefer the operational interpretation that best matches the user question, while noting ambiguity when necessary.",
    "Absence or LOP explanations may require combining emp_leave_setting with cl_detail and optionally shift or holiday context.",
    "Holiday and weekoff context can override naive absence interpretation if the date is not a normal working day.",
    "Permission reasoning may require both emp_leave_setting day-status evidence and cl_detail monthly summary evidence.",
    "Half-day reasoning may require leave_dates.leave_day when the question is explicitly about day fraction or approval split.",
]

POLICY_RULES = [
    "Policy questions should prefer policy/reference tables and optional department policy JSON instead of transactional tables alone.",
    "Employee-specific exception tables should override generic policy tables when both are applicable.",
    "Reference tables should explain allowed rules and category/policy meaning, not prove that an actual attendance event occurred.",
    "Use mstCLPolicyRule to interpret generic casual leave policy counts.",
    "Use trnExceptionEmployeeCLPolicy to interpret employee-specific CL policy overrides.",
    "Use mstWeekoffType to interpret weekoff naming and type meaning.",
    "Use pay_mst_category and mstRestrictLeaveMarkingCategory when category-based attendance or leave restrictions are relevant.",
]


# ------------------------------------------
# TABLE-SPECIFIC RULES
# ------------------------------------------
TABLE_RULES: Dict[str, List[str]] = {
    "login_mast": [
        "login_mast is the primary attendance fact table for employee login/logout activity.",
        "Key business fields in login_mast include emp_id, login_date, login_time, logoff_time, shift_code, and Logintype.",
        "Use login_mast first for login/logout queries, worked-hours queries, working-minutes queries, and punch-based attendance details.",
        "Do not join login_mast to leave tables unless the query explicitly needs leave interpretation or explanation.",
        "actualWorkingMinutes and shiftWorkingMinutes, when available, can support attendance analytics but raw punch times remain authoritative attendance evidence.",
        "Logintype may distinguish biometric, WFH, or leave-shift style logging and can be useful when the user asks how attendance was marked.",
    ],
    "emp_leave_setting": [
        "emp_leave_setting should be treated as the processed final day-status table for leave, permission, weekoff, and operational leave outcomes.",
        "Key business fields include leave_id, emp_id, leave_date, leave_status, leave_remark, LopCount, isEmployeeCL, EmpLop, markedby, isApproval, previousStatus, previousMarkedBy, and HODComments.",
        "For simple employee-date leave status questions, prefer emp_leave_setting first.",
        "A missing row in emp_leave_setting may indicate a normal working day for many daily attendance/leave queries.",
        "Use leave_remark together with leave_status for better interpretation of LOP, permission, and operational marking logic.",
        "Use LopCount and EmpLop as strong LOP-related evidence when present.",
    ],
    "Leave_detail": [
        "Leave_detail stores leave application details such as leav_type, reason, comp_date, frmtime, totime, and apply_date.",
        "Use Leave_detail when the user asks for leave type, leave reason, leave application details, leave duration intent, or applied date.",
        "Leave_detail is not required for every day-status query.",
        "Join Leave_detail through leave_id when leave application context is needed.",
    ],
    "leave_dates": [
        "leave_dates stores date-level leave workflow and leave_day split information.",
        "Use leave_dates when the question asks about half-day values, per-day approval flow, or whether a particular date was part of a leave application.",
        "leave_day is important for half-day or partial-day interpretation.",
        "manager_appr and hr_appr in leave_dates are relevant for workflow and approval reasoning.",
        "Do not join leave_dates unless day-wise approval or split detail is necessary.",
    ],
    "shift_details": [
        "shift_details is the authoritative reference for expected shift timing.",
        "Key business fields include shift_code, shift_name, shift_intime, shift_outtime, shift_restinterval, BreakTimeMin, ShiftSeconds, weekoff, and isNextDay.",
        "Use shift_details when the user asks about late coming, expected working time, shift comparison, weekoff logic, or shift-based explanation.",
        "Do not use shift_details for simple login/logout lookup unless shift meaning is explicitly needed.",
    ],
    "emp_default_shift": [
        "emp_default_shift stores the employee's default assigned shift.",
        "Use emp_default_shift when shift assignment is needed and there is no better date-range override.",
        "Join via emp_id to relate employees to assigned shift_code.",
    ],
    "trnEmployeeWeeklyShift": [
        "trnEmployeeWeeklyShift stores temporary or date-range shift assignments and should take precedence over default shift when the date falls within fromDate and toDate.",
        "Use trnEmployeeWeeklyShift for temporary shift override reasoning.",
        "This table is mainly relevant for explanation or shift-specific queries, not simple attendance lookup.",
    ],
    "cl_detail": [
        "cl_detail is the monthly attendance/leave summary layer used for CL balance, LOP, holidays, permissions, working day counts, and payroll-related reasoning.",
        "Key business fields include emp_id, emp_year, emp_month, CLavailed, CLbalance, LOP, holidays, Permission, company_workingdays, cl_Eligible, and isOBCL.",
        "Use cl_detail for monthly summary queries, CL balance questions, LOP questions, permission totals, and payroll-oriented attendance reasoning.",
        "Do not use cl_detail for raw login/logout facts; use login_mast for those.",
    ],
    "emp_compoff": [
        "emp_compoff should be used for comp-off requests, comp-off approval, comp-off availability, and compensatory-off reasoning.",
        "Use manager_appr, avail_stat, compoff_reas, and compoff_day when answering comp-off questions.",
    ],
    "mstEmployeeStatutoryLeave": [
        "mstEmployeeStatutoryLeave stores employee statutory leave entries and is relevant when the user explicitly asks about statutory/special leave dates.",
    ],
    "mstLeaveStatusStatutory": [
        "mstLeaveStatusStatutory defines statutory leave types and annual allocation; it is a policy/reference table rather than a day-status fact table.",
    ],
    "mstCLPolicyRule": [
        "mstCLPolicyRule defines generic casual leave policy counts and should be used for policy explanation rather than transactional proof.",
    ],
    "trnExceptionEmployeeCLPolicy": [
        "trnExceptionEmployeeCLPolicy contains employee-specific CL policy overrides and should override generic CL policy when applicable.",
    ],
    "mstWeekoffType": [
        "mstWeekoffType is a reference table for weekoff type naming and interpretation.",
    ],
    "holiday_master": [
        "holiday_master defines organization holidays and should be used to determine whether a date is a configured holiday before concluding absence or penalty.",
    ],
    "trnCandidateHolidayMapping": [
        "trnCandidateHolidayMapping should be checked when holiday applicability differs by employee or category.",
    ],
    "pay_mst_category": [
        "pay_mst_category controls category-level attendance, permission, holiday, leave policy, and LOP behavior.",
        "Use pay_mst_category when the question is category-based or when policy behavior depends on employee category.",
    ],
    "mstRestrictLeaveMarkingCategory": [
        "mstRestrictLeaveMarkingCategory defines category-level restriction on leave marking and should be used when the question is about whether leave marking is restricted.",
    ],
    "mstShiftNameAndTime": [
        "mstShiftNameAndTime is a reference table for standardized shift naming and timing display.",
    ],
}


# ------------------------------------------
# POLICY JSON -> RULES
# ------------------------------------------
def _extract_software_policy_rules(policy_data: Dict[str, Any]) -> List[str]:
    """
    Convert optional department policy JSON into plain business rules.
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
            rules.append(f"Standard employees have an annual casual leave quota of {annual_quota} days.")
        if monthly_limit is not None:
            rules.append(f"Standard employees have a monthly casual leave limit of {monthly_limit} day.")

    if external:
        annual_quota = external.get("annual_quota")
        if annual_quota is not None:
            rules.append(f"External QSecure employees have an annual casual leave quota of {annual_quota} days.")

    eligibility = casual_leave.get("eligibility", {})
    if eligibility:
        if eligibility.get("interns") is False:
            rules.append("Interns are not eligible for casual leave.")
        if eligibility.get("standard_employees") is True:
            rules.append("Standard employees are eligible for casual leave.")
        if eligibility.get("external_qsecure") is True:
            rules.append("External QSecure employees are eligible for casual leave.")

    carry_forward = casual_leave.get("carry_forward", {})
    if carry_forward.get("allowed") is True:
        rules.append("Casual leave carry forward is allowed on a monthly basis only and cannot be carried to the next year.")

    # Permission policy
    if permission_policy:
        allowed = permission_policy.get("allowed_per_month")
        duration = permission_policy.get("duration_hours_per_permission")
        if allowed is not None:
            rules.append(f"Permission is allowed {allowed} times per month.")
        if duration is not None:
            rules.append(f"Each permission is limited to {duration} hours.")

    # Leave penalty
    if leave_penalty:
        unapproved = leave_penalty.get("unapproved_leave", {})
        uninformed = leave_penalty.get("uninformed_leave", {})

        if unapproved.get("penalty_multiplier") is not None:
            rules.append(
                f"Unapproved leave may be penalized at {unapproved['penalty_multiplier']} times the leave duration."
            )

        if uninformed.get("penalty_multiplier") is not None:
            rules.append(
                f"Uninformed leave may be penalized at {uninformed['penalty_multiplier']} times the leave duration."
            )

    # Attendance behavior
    if attendance_behavior_rules:
        limit = attendance_behavior_rules.get("late_and_permission_combined_limit")
        action = attendance_behavior_rules.get("exceed_limit_action")
        grace = attendance_behavior_rules.get("grace_time_allowed")

        if limit is not None and action:
            rules.append(
                f"If late coming and permission combined exceed {limit}, the action may become {action}."
            )
        if grace is False:
            rules.append("Grace time is not allowed for attendance behavior evaluation.")

    # Weekend policy
    if weekend_policy:
        rules_map = weekend_policy.get("rules", {})
        less_than_1_year = rules_map.get("less_than_1_year", {})
        greater_equal_1_year = rules_map.get("greater_than_or_equal_1_year", {})

        if less_than_1_year:
            working_days = less_than_1_year.get("working_days")
            if working_days:
                rules.append(
                    f"For employees with less than 1 year experience, the following Saturdays may be working days: {working_days}."
                )

        if greater_equal_1_year:
            saturday_rule = greater_equal_1_year.get("saturday")
            if saturday_rule:
                rules.append(
                    f"For employees with 1 year or more experience, Saturday rule may be: {saturday_rule}."
                )

    # Special leaves
    if special_leaves:
        for leave_name, details in special_leaves.items():
            days = details.get("days")
            if days is not None:
                readable_name = leave_name.replace("_", " ")
                rules.append(f"{readable_name.title()} may allow {days} day(s), subject to its conditions.")

    # Holiday policy
    if holiday_policy:
        sandwich = holiday_policy.get("sandwich_rule")
        if sandwich is True:
            rules.append("Sandwich holiday rule may apply depending on adjacent leave configuration.")

    # Attendance integration
    if attendance_integration:
        for key, value in attendance_integration.items():
            if isinstance(value, (str, int, float, bool)):
                readable_key = str(key).replace("_", " ")
                rules.append(f"Attendance integration rule - {readable_key}: {value}")

    return _dedupe_keep_order(rules)


# ------------------------------------------
# INTERNAL BUILDERS
# ------------------------------------------
def _rules_for_intent(intent: str) -> List[str]:
    if intent == "attendance":
        return COMMON_RULES + HRMS_DAY_STATUS_RULES + ATTENDANCE_RULES

    if intent == "leave":
        return COMMON_RULES + HRMS_DAY_STATUS_RULES + LEAVE_RULES

    if intent == "attendance_explanation":
        return COMMON_RULES + HRMS_DAY_STATUS_RULES + ATTENDANCE_RULES + LEAVE_RULES + EXPLANATION_RULES

    if intent == "policy":
        return COMMON_RULES + HRMS_DAY_STATUS_RULES + POLICY_RULES

    return COMMON_RULES + HRMS_DAY_STATUS_RULES


def _rules_for_tables(tables: List[str]) -> List[str]:
    rules: List[str] = []
    for table in tables:
        rules.extend(TABLE_RULES.get(table, []))
    return rules


def _build_join_guidance(tables: List[str]) -> List[str]:
    table_set = _table_set(tables)
    rules: List[str] = []

    if "login_mast" in table_set and "emp_leave_setting" in table_set:
        rules.append("Join login_mast and emp_leave_setting by emp_id and aligned employee-date only when attendance and processed leave status must be reconciled.")

    if "emp_leave_setting" in table_set and "Leave_detail" in table_set:
        rules.append("Join emp_leave_setting and Leave_detail using leave_id when leave application details are required.")

    if "emp_leave_setting" in table_set and "leave_dates" in table_set:
        rules.append("Join emp_leave_setting and leave_dates using leave_id when date-level approval or leave_day split is required.")

    if "Leave_detail" in table_set and "leave_dates" in table_set:
        rules.append("Join Leave_detail and leave_dates using leave_id when both leave application and day-wise leave details are required.")

    if "login_mast" in table_set and "shift_details" in table_set:
        rules.append("Join login_mast and shift_details using shift_code when shift timing or expected-hours interpretation is required.")

    if "login_mast" in table_set and "emp_default_shift" in table_set:
        rules.append("Join login_mast and emp_default_shift using emp_id only when assigned default shift matters.")

    if "login_mast" in table_set and "trnEmployeeWeeklyShift" in table_set:
        rules.append("Use trnEmployeeWeeklyShift only when temporary/date-range shift assignment matters for the attendance date.")

    if "holiday_master" in table_set and ("login_mast" in table_set or "emp_leave_setting" in table_set):
        rules.append("Use holiday_master only when holiday applicability is needed before concluding absence, late, or penalty.")

    if "cl_detail" in table_set and ("emp_leave_setting" in table_set or "login_mast" in table_set):
        rules.append("Use cl_detail only for monthly summary, LOP, CL balance, permission count, or payroll-style reasoning, not for raw punch facts.")

    return rules


# ------------------------------------------
# PUBLIC FUNCTION
# ------------------------------------------
def get_rules(
    intent: Optional[str],
    tables: List[str],
    include_policy_json: bool = True,
    policy_path: Optional[str] = None,
) -> List[str]:
    """
    Return production-ready business rules for the selected intent and tables.

    This function is designed to feed context_builder.py
    with strong HR-aware semantics so the agent avoids hallucination and uses
    the minimum correct tables.

    Args:
        intent:
            attendance / leave / attendance_explanation / policy / irrelevant
        tables:
            Selected tables for the current query
        include_policy_json:
            Whether to load optional department policy JSON
        policy_path:
            Optional override for policy JSON path

    Returns:
        list[str]
    """
    safe_intent = _normalize_intent(intent)
    clean_tables = _dedupe_keep_order([str(table).strip() for table in tables if str(table).strip()])

    rules: List[str] = []
    rules.extend(_rules_for_intent(safe_intent))
    rules.extend(_rules_for_tables(clean_tables))
    rules.extend(_build_join_guidance(clean_tables))

    if include_policy_json:
        policy_data = _load_policy_json(policy_path=policy_path)
        rules.extend(_extract_software_policy_rules(policy_data))

    return _dedupe_keep_order(rules)