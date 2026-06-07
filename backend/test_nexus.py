import asyncio
import os
import sys

from app.database import get_db_context
from app.ml.chat_rag.responder import answer_question

def main():
    questions = [
        "Who won the 2024 Monaco Grand Prix?",
        "Compare VER and NOR tyre degradation at Silverstone 2024",
        "Which driver had the most consistent qualifying performance across all 2024 races?",
    ]
    with get_db_context() as db:
        for q in questions:
            print(f"Question: {q}")
            try:
                # call the sync version or run async loop since answer_question is sync?
                # wait, answer_question is not async, it's a normal def!
                res = answer_question(q, db)
                print(f"Answer: {res.get('answer')}")
            except Exception as e:
                print(f"Failed: {e}")
            print("-" * 40)

if __name__ == "__main__":
    main()
