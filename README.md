# HR Attendance AI Assistant

A Streamlit-based HR analytics assistant that answers attendance and leave questions using an agentic workflow, SQL tools, and LLM-assisted reasoning.

## Features

- Conversational HR assistant UI built with Streamlit.
- Attendance, leave, and explanatory query handling through agent routing.
- SQL generation, validation, execution, and result explanation pipeline.
- Schema-aware context builder for better query accuracy.
- Enterprise-style UI with topbar, sidebar history, prompt chips, and KPI cards.

## Tech Stack

- Python 3.10+
- Streamlit
- LangChain + LangGraph
- SQLAlchemy + pyodbc
- Ollama or Gemini (for LLM inference)
- Pandas

## Project Structure

```text
.
├── app.py
├── agents/
├── graph/
├── llm/
├── rag/
├── services/
├── sql/
├── tools/
├── ui/
├── assets/
└── requirements.txt
```

## Prerequisites

- Python 3.10 or 3.11
- Access to a SQL Server instance
- ODBC Driver 17 for SQL Server installed
- Ollama server running and models pulled

## Environment Variables

Create a `.env` file in the project root with:

```env
# LLM provider selection: ollama (default) or gemini
LLM_PROVIDER=ollama

# Ollama config (required when LLM_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_SQL=qwen2.5-coder:7b
OLLAMA_MODEL_Exp=llama3.1:8b

# Gemini config (required when LLM_PROVIDER=gemini)
GEMINI_API_KEY=XXX
GEMINI_MODEL=gemini-2.5-flash

DB_SERVER=<sql-server-host>
DB_NAME=<database-name>
DB_USER=<db-username>
DB_PASSWORD=<db-password>
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run the App

```bash
streamlit run app.py
```

Then open: `http://localhost:8501`

## Deployment (Recommended)

- Push code to GitHub.
- Deploy using Streamlit Community Cloud.
- Set environment variables/secrets in host settings.
- Use `app.py` as the entrypoint.

## Troubleshooting

- **Ollama connection error:** verify `OLLAMA_BASE_URL` and model names.
- **Gemini auth/model error:** verify `GEMINI_API_KEY`, `GEMINI_MODEL`, and that `LLM_PROVIDER=gemini`.
- **DB connection failure:** verify SQL credentials/network and ODBC driver.
- **UI loads but answers fail:** verify both DB and LLM services are reachable.

## License

Internal / Proprietary (update as per organization policy).
