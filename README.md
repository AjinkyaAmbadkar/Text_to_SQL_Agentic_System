# Text-to-SQL Agentic System

A small, fully local, offline assistant that turns plain-English questions into
SQLite queries, runs them, self-corrects on errors, and answers in plain
English. No cloud, no API keys — just Python, Ollama, and SQLite. A terminal
CLI and a Streamlit browser UI both sit on top of the same agent logic.

## How it works

1. You type a question in the terminal.
2. The app reads the live schema of `shop.db`.
3. The local LLM (`llama3.2` via [Ollama](https://ollama.com)) writes a SQLite
   query for your question.
4. The query runs against the database.
5. **Agentic step:** if the query errors, the error is fed back to the LLM,
   which tries to fix its own SQL — up to 5 attempts before giving up.
6. Once a query succeeds, the rows are handed back to the LLM one more time
   so it can phrase a short natural-language answer.

## Setup

1. Install [Ollama](https://ollama.com) and make sure it's running.
2. Pull the model this project uses:
   ```
   ollama pull llama3.2
   ```
3. Create a virtual environment and install dependencies:
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Build the sample database (customers, products, orders, order items):
   ```
   python setup_db.py
   ```

## Running it

```
source venv/bin/activate
python main.py
```

Ask a question, e.g. `Which 5 customers have spent the most in total?`.
Type `quit` to exit.

### Browser UI

```
source venv/bin/activate
streamlit run app.py
```

Opens at `http://localhost:8501`. Same agent, same self-correction — each
attempt (and any SQL errors) is shown in an expandable panel, followed by the
final answer and a results table.

## Files

- `setup_db.py` — creates `shop.db` with sample e-commerce data.
- `agent.py` — the self-correcting text-to-SQL loop. `answer_question()`
  prints progress for the CLI and returns a result dict for any frontend.
- `main.py` — the CLI: prompts for a question, calls `agent.py`, repeats.
- `app.py` — the Streamlit browser UI, built on the same `answer_question()`.
- `requirements.txt` — third-party dependencies (`ollama`, `streamlit`).
