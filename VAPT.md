# VAPT (Vulnerability Assessment and Penetration Testing) Guide

## Objective

Define baseline security checks for the HR Attendance AI Assistant before production release.

## Scope

- Streamlit web interface
- LLM integration layer
- SQL connectivity and query execution pipeline
- Configuration and secret management

## Security Controls Checklist

### 1) Authentication & Access

- Enforce authentication at reverse proxy / SSO layer.
- Restrict access by role (HR/Admin).
- Disable anonymous public access in production.

### 2) Secret Management

- Store DB/LLM secrets in environment variables or secret manager.
- Do not commit `.env` values to Git.
- Rotate DB credentials periodically.

### 3) Input Validation

- Validate and sanitize user prompts before SQL execution.
- Keep SQL validation enabled in `sql/sql_validator.py`.
- Apply query allow-list patterns for sensitive operations.

### 4) Database Security

- Use least-privilege DB user with read-only access where possible.
- Restrict network path to DB from app host.
- Enable SQL Server audit logging.

### 5) LLM/API Security

- Restrict outbound traffic from host to approved endpoints only.
- Monitor prompt injection attempts and log suspicious patterns.
- Add request timeout and retry controls.

### 6) Transport Security

- Enforce HTTPS/TLS for all client-app and app-backend traffic.
- Use trusted certificates and disable weak ciphers.

### 7) Logging & Monitoring

- Centralize app logs.
- Mask PII and secrets in logs.
- Alert on repeated failures, auth anomalies, and query spikes.

## Suggested VAPT Execution Plan

1. **Automated scan** (dependency and container scan).
2. **Web app scan** (OWASP Top 10 checks).
3. **Manual penetration tests** (auth bypass, injection, privilege escalation).
4. **Remediation cycle** with severity-based SLA.
5. **Re-test** and signoff.

## Severity and SLA

- Critical: 24-48 hours
- High: 3-5 business days
- Medium: 10 business days
- Low: next planned release

## Deliverables

- VAPT report with PoC, CVSS scores, and remediation guidance
- Retest report and closure evidence
- Security signoff for release
