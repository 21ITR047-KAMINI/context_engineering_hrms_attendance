# SonarQube Setup and Usage

## Goal

Run static code quality and security checks for this repository using SonarQube.

## Prerequisites

- SonarQube server access
- Sonar token
- SonarScanner CLI installed

## Minimal `sonar-project.properties`

Create a file in project root:

```properties
sonar.projectKey=hr-attendance-ai
sonar.projectName=HR Attendance AI Assistant
sonar.sourceEncoding=UTF-8
sonar.sources=.
sonar.exclusions=**/__pycache__/**,**/*.pyc,**/.venv/**
sonar.python.version=3.10
```

## Run Scan

```bash
sonar-scanner \
  -Dsonar.host.url=http://<sonarqube-host>:9000 \
  -Dsonar.token=<your-sonar-token>
```

## Quality Gate Recommendation

- Reliability Rating: A
- Security Rating: A
- Maintainability Rating: A
- Duplications: < 3%
- New code coverage: > 70%

## CI Integration Idea

In CI pipeline:

1. Install dependencies.
2. Run tests and lint.
3. Run SonarScanner.
4. Fail pipeline if Quality Gate fails.

## Common Fix Areas

- Remove dead code and unused imports.
- Add type hints and docstrings for public functions.
- Refactor long functions in `app.py` and orchestration layers.
- Ensure exception messages do not leak sensitive data.
