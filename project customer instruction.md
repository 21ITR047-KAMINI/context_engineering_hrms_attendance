# Project Customer Instructions

## Overview

This application provides AI-assisted attendance and leave insights for HR teams.

## What You Can Ask

- Attendance summary for a date range
- Employees on leave today/this week
- Department absenteeism comparisons
- Leave trend analysis

## Expected Input Style

Use natural language questions, for example:

- "Show attendance summary for the last 30 days"
- "Who is on leave this week in Engineering?"
- "Compare absenteeism between Q1 and Q2"

## Output Types

The assistant may return:

- Plain text explanation
- Summary cards with key metrics
- Tabular data results

## Customer Responsibilities

- Provide valid database connectivity details.
- Provide required model endpoint details.
- Validate generated insights before policy decisions.

## Data and Privacy

- Do not expose employee PII outside authorized HR users.
- Follow internal data retention and access policies.
- Review audit logs periodically.

## Known Limitations

- Accuracy depends on source data quality and completeness.
- Model responses may require human verification.
- Complex policy interpretation should be reviewed by HR/legal.

## Support Workflow

1. Capture issue screenshot and query text.
2. Share timestamp and affected module.
3. Attach logs/errors (without secrets).
4. Contact support owner/team.

## Change Request Process

- Raise enhancement request with:
  - business objective
  - sample expected output
  - priority and deadline
- UAT signoff required before production rollout.
