"""
main.py
-------
The CLI entry point. Prompts for a question, hands it to agent.py, repeats
until the user types 'quit'. All the actual logic lives in agent.py — this
file is intentionally just a loop around it.
"""

from agent import answer_question

if __name__ == "__main__":
    print("Text-to-SQL assistant. Ask a question about the shop database, or type 'quit' to exit.\n")

    while True:
        question = input("> ").strip()
        if question.lower() == "quit":
            break
        if not question:
            continue
        answer_question(question)
