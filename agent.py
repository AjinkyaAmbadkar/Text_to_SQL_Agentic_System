"""
agent.py
--------
The "brain" of the assistant: turns a plain-English question into a SQLite
query, runs it, and prints what came back.

THIS IS STEP 4 OF THE BUILD: adds the final natural-language answer step.
Once a query runs successfully, the raw rows are handed back to the LLM once
more so it can phrase a short plain-English answer instead of leaving the
user to read a list of tuples.
"""

import sqlite3
import ollama

DB_FILE = "shop.db"
MODEL = "llama3.2"
MAX_TRIES = 5


def get_schema(conn: sqlite3.Connection) -> str:
    """
    Reads the CREATE TABLE statements straight out of SQLite's own catalog
    (the `sqlite_master` table), instead of hand-typing the schema here.
    WHY: if setup_db.py ever changes the schema, this stays correct
    automatically — there's only one source of truth.
    """
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table'"
    )
    return "\n\n".join(row[0] for row in cur.fetchall())


def build_prompt(schema: str, question: str, attempts: list[tuple[str, str]]) -> str:
    """
    The system prompt. WHY these specific instructions:
    - Giving the LLM the live schema means it knows exact table/column names
      instead of guessing (guessing is the #1 cause of bad SQL from LLMs).
    - "ONLY raw SQL" keeps the output easy to run directly — no parsing out
      an explanation paragraph before we can execute anything.
    - We still strip markdown fences defensively below, because models
      sometimes ignore this instruction and wrap SQL in ```sql ... ``` anyway.

    `attempts` is the list of (sql, error) pairs from earlier failed tries in
    this same question. WHY pass the whole history and not just the last
    error: it stops the model from cycling back to a query it already tried
    and already saw fail.
    """
    history = ""
    for i, (bad_sql, error) in enumerate(attempts, start=1):
        history += f"""
Attempt {i} — this SQL failed:
{bad_sql}
Error it raised:
{error}
"""

    retry_instructions = ""
    if history:
        retry_instructions = f"""
Previous attempts failed. Learn from them and do not repeat the same mistake.
{history}
"""

    return f"""You are a SQLite expert. Given this database schema:

{schema}

Write a single SQLite query that answers the question below.
Return ONLY the raw SQL — no markdown code fences, no explanation, no comments.
{retry_instructions}
Question: {question}
SQL:"""


def strip_code_fences(text: str) -> str:
    """
    Defensive cleanup: some models wrap SQL in ```sql ... ``` even when told
    not to. We remove any ``` fences so the string below is executable SQL
    and nothing else.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # drop the opening ``` (and any language tag like ```sql)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # drop the closing ```
        text = "\n".join(lines).strip()
    return text


def ask_llm_for_sql(schema: str, question: str, attempts: list[tuple[str, str]]) -> str:
    """One round-trip to the local LLM: question (+ any failed history) -> SQL string."""
    prompt = build_prompt(schema, question, attempts)
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_sql = response["message"]["content"]
    return strip_code_fences(raw_sql)


def ask_llm_for_answer(question: str, columns: list[str], rows: list[tuple]) -> str:
    """
    Final round-trip: hand the raw query results back to the LLM and ask for
    a short plain-English answer. WHY a separate call instead of just
    printing the rows: the user asked a natural-language question and a list
    of tuples isn't an answer to it — this turns e.g.
    [('Olivia Martin', 15285.06)] into "Olivia Martin spent the most, $15285.06."
    """
    prompt = f"""You answer questions about a database using only the query
results below. Be concise — one or two sentences, plain English, no SQL.

Question: {question}
Columns: {columns}
Rows: {rows}

Answer:"""
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"].strip()


def answer_question(question: str) -> None:
    """
    Self-correcting loop: generate SQL, try to run it. If it errors, hand the
    SQL and the error back to the LLM and ask it to fix its own mistake, up
    to MAX_TRIES times. Once a query runs successfully, the rows go back to
    the LLM one more time for a plain-English answer.
    """
    conn = sqlite3.connect(DB_FILE)
    schema = get_schema(conn)
    attempts: list[tuple[str, str]] = []  # (sql, error) from each failed try

    for attempt_num in range(1, MAX_TRIES + 1):
        sql = ask_llm_for_sql(schema, question, attempts)
        print(f"\n[Attempt {attempt_num}] Generated SQL:\n{sql}\n")

        try:
            cur = conn.execute(sql)
            rows = cur.fetchall()
            columns = [description[0] for description in cur.description]
            print(f"[Columns] {columns}")
            print(f"[Rows] {rows}")

            answer = ask_llm_for_answer(question, columns, rows)
            print(f"\n[Answer] {answer}")

            conn.close()
            return
        except sqlite3.Error as e:
            print(f"[SQL Error] {e}")
            attempts.append((sql, str(e)))

    print(f"\n[Gave up] Could not produce a working query after {MAX_TRIES} attempts.")
    conn.close()


if __name__ == "__main__":
    # This module is meant to be imported by main.py, which provides the
    # actual CLI loop. Run `python main.py` to use the assistant.
    print("Run 'python main.py' to use the assistant.")
