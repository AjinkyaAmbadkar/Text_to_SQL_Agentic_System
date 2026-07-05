"""
app.py
------
A browser front end for the same assistant `main.py` exposes on the CLI.
No new logic lives here — this just renders the dict that answer_question()
already returns, so the terminal and the browser stay in sync automatically.

Run with: streamlit run app.py
"""

import streamlit as st

from agent import answer_question

st.title("Text-to-SQL Assistant")
st.caption("Ask a question about the shop database in plain English.")

question = st.text_input("Your question", placeholder="Which 5 customers have spent the most in total?")

if st.button("Ask", type="primary") and question:
    with st.spinner("Thinking..."):
        result = answer_question(question)

    for i, attempt in enumerate(result["attempts"], start=1):
        with st.expander(f"Attempt {i}", expanded=(attempt["error"] is not None or i == len(result["attempts"]))):
            st.code(attempt["sql"], language="sql")
            if attempt["error"]:
                st.error(attempt["error"])
            else:
                st.success("Ran successfully")

    if result["gave_up"]:
        st.error(f"Gave up after {len(result['attempts'])} attempts — could not produce a working query.")
    else:
        st.subheader("Answer")
        st.write(result["answer"])
        st.subheader("Raw results")
        st.dataframe([dict(zip(result["columns"], row)) for row in result["rows"]])
