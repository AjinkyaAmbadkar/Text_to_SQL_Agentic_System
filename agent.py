"""
agent.py
--------
The "brain" of the assistant: turns a plain-English question into a SQLite
query, runs it, and prints what came back.

THIS IS STEP 2 OF THE BUILD: a single attempt, no self-correction yet.
No retry loop, no final natural-language answer step — those come next.
The goal right now is just to prove text-to-SQL works end to end:
question in -> SQL out -> rows out.
"""

import sqlite3
import ollama

DB_FILE = "shop.db"
MODEL = "llama3.2"


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


def build_prompt(schema: str, question: str) -> str:
    """
    The system prompt. WHY these specific instructions:
    - Giving the LLM the live schema means it knows exact table/column names
      instead of guessing (guessing is the #1 cause of bad SQL from LLMs).
    - "ONLY raw SQL" keeps the output easy to run directly — no parsing out
      an explanation paragraph before we can execute anything.
    - We still strip markdown fences defensively below, because models
      sometimes ignore this instruction and wrap SQL in ```sql ... ``` anyway.
    """
    return f"""You are a SQLite expert. Given this database schema:

{schema}

Write a single SQLite query that answers the question below.
Return ONLY the raw SQL — no markdown code fences, no explanation, no comments.

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


def ask_llm_for_sql(schema: str, question: str) -> str:
    """One round-trip to the local LLM: question -> SQL string."""
    prompt = build_prompt(schema, question)
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_sql = response["message"]["content"]
    return strip_code_fences(raw_sql)


def answer_question(question: str) -> None:
    """
    Single-attempt version: generate SQL once, run it once. If it fails, we
    just report the error and stop — no retry yet (that's step 3).
    """
    conn = sqlite3.connect(DB_FILE)
    schema = get_schema(conn)

    sql = ask_llm_for_sql(schema, question)
    print(f"\n[Generated SQL]\n{sql}\n")

    try:
        cur = conn.execute(sql)
        rows = cur.fetchall()
        columns = [description[0] for description in cur.description]
        print(f"[Columns] {columns}")
        print(f"[Rows] {rows}")
    except sqlite3.Error as e:
        print(f"[SQL Error] {e}")

    conn.close()


if __name__ == "__main__":
    # Quick manual test while we build this out — main.py will replace this
    # with a proper CLI loop in step 5.
    print("Which 5 customers have spent the most in total?")
    answer_question("Which 5 customers have spent the most in total?")
