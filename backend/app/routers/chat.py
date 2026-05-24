"""
app/routers/chat.py - /chat/* AI chat endpoints.

Spec §5.13:
  POST /chat/query        - Protected. RAG answer from natural language question
  GET  /chat/suggestions  - Protected. 6 example questions personalised by followed drivers

Both endpoints require Firebase authentication (Bearer token).
The LLM provider is controlled by settings.LLM_PROVIDER — default: groq.
All LLM calls are run in asyncio.to_thread() since groq/genai clients are synchronous.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.firebase import get_current_user
from app.models.schemas import ChatAnswerSchema, ChatQueryRequest, ChatSuggestionsSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Default suggestions shown to all users (unauthenticated fallback or no followed drivers)
_DEFAULT_SUGGESTIONS = [
    "Who had the fastest lap at Monaco 2023?",
    "Compare VER and NOR tyre degradation at Silverstone 2024",
    "Which circuit had the most safety car periods in 2023?",
    "What was LEC's average qualifying gap to pole in 2024?",
    "Which driver had the most pit stops in the 2024 season?",
    "What is the average lap time difference between SOFT and HARD compounds at Spa?",
]


# ── POST /chat/query ──────────────────────────────────────────────────────────

@router.post("/query", response_model=ChatAnswerSchema)
async def chat_query(
    body: ChatQueryRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Answer a natural language question about F1 data via RAG.

    Pipeline:
      1. LLM generates SQL from the question
      2. SQL is executed safely against Neon PostgreSQL
      3. Results are passed back to the LLM for a natural language answer

    Returns the answer, the generated SQL, row count, and raw data rows.
    """
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty")

    if len(question) > 500:
        raise HTTPException(400, "Question must be 500 characters or fewer")

    from app.ml.chat_rag.responder import answer_question

    try:
        result = await asyncio.to_thread(answer_question, question, db)
    except RuntimeError as exc:
        # RuntimeError is raised by llm_client when API key is missing
        raise HTTPException(503, str(exc))
    except ValueError as exc:
        # ValueError is raised by llm_client for unknown provider
        raise HTTPException(500, str(exc))
    except Exception as exc:
        logger.error("Chat query failed for user %s: %s", user["uid"], exc)
        raise HTTPException(500, f"Chat query failed: {exc}")

    return ChatAnswerSchema(
        answer=result["answer"],
        sql=result["sql"],
        row_count=result["row_count"],
        data=result["data"],
    )


# ── GET /chat/suggestions ─────────────────────────────────────────────────────

@router.get("/suggestions", response_model=ChatSuggestionsSchema)
async def get_suggestions(user: dict = Depends(get_current_user)):
    """
    Return 6 example questions personalised by the user's followed drivers.

    Fetches the user's Firestore profile to get followed_drivers, then injects
    those driver codes into the suggestion templates. Falls back to generic
    suggestions if Firestore is unavailable or the user follows no drivers.
    """
    followed_drivers: list[str] = []

    try:
        from app.firebase import get_firestore_client
        db_fs = get_firestore_client()
        doc = db_fs.collection("users").document(user["uid"]).get()
        if doc.exists:
            followed_drivers = doc.to_dict().get("followed_drivers", [])
    except Exception as exc:
        logger.warning("Could not fetch followed drivers for suggestions: %s", exc)

    suggestions = _build_suggestions(followed_drivers)
    return ChatSuggestionsSchema(suggestions=suggestions)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_suggestions(followed: list[str]) -> list[str]:
    """
    Build personalised suggestion chips.

    If the user follows at least 2 drivers, replace the first two generic
    suggestions with driver-specific ones. Always returns exactly 6 suggestions.
    """
    if len(followed) >= 2:
        d1, d2 = followed[0], followed[1]
        personalised = [
            f"How many points has {d1} scored in the 2024 season?",
            f"Compare {d1} and {d2} sector times at the last race",
        ] + _DEFAULT_SUGGESTIONS[2:]
        return personalised[:6]

    if len(followed) == 1:
        d1 = followed[0]
        personalised = [
            f"What is {d1}'s average lap time on SOFT tyres in 2024?",
        ] + _DEFAULT_SUGGESTIONS[1:]
        return personalised[:6]

    return _DEFAULT_SUGGESTIONS
