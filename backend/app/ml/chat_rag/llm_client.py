"""
app/ml/chat_rag/llm_client.py - Provider-agnostic LLM wrapper.

Controlled entirely by settings.LLM_PROVIDER. To swap provider:
  change LLM_PROVIDER env var → zero code changes needed.

Supported providers:
  groq      → uses GROQ_API_KEY + GROQ_MODEL (default: llama-3.1-70b-versatile)
  gemini    → uses GEMINI_API_KEY + GEMINI_MODEL (default: gemini-1.5-flash)
  anthropic → uses ANTHROPIC_API_KEY + ANTHROPIC_MODEL (paid — leave blank unless upgrading)

All other modules import only from here — never import groq/anthropic/genai directly.
Providers are imported lazily inside each branch so unused packages don't need to be installed.
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def chat_completion(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1000,
    temperature: float = 0.1,
) -> str:
    """
    Send a chat completion request to the configured LLM provider.

    Args:
        system_prompt: Instruction/context for the model.
        user_message:  The user's question or request.
        max_tokens:    Maximum tokens in the response.
        temperature:   Sampling temperature (0.1 = focused/deterministic).

    Returns:
        Plain text response string from the LLM.

    Raises:
        ValueError:    If LLM_PROVIDER is not recognized.
        RuntimeError:  If the required API key is not set.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "groq":
        return _groq(system_prompt, user_message, max_tokens, temperature)
    elif provider == "gemini":
        return _gemini(system_prompt, user_message, max_tokens, temperature)
    elif provider == "anthropic":
        return _anthropic(system_prompt, user_message, max_tokens, temperature)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. "
            "Valid values: groq | gemini | anthropic"
        )


# ── Provider implementations ──────────────────────────────────────────────────

def _groq(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Groq API — default provider. Free tier: 14,400 req/day."""
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key at console.groq.com"
        )

    from groq import Groq  # lazy import — only if groq provider is selected

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


def _gemini(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Google Gemini — free fallback via AI Studio."""
    if not settings.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at aistudio.google.com"
        )

    import google.generativeai as genai  # lazy import

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        settings.GEMINI_MODEL,
        system_instruction=system_prompt,
    )
    response = model.generate_content(
        user_message,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    return response.text


def _anthropic(
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Anthropic Claude — paid tier only."""
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env to use the Anthropic provider."
        )

    import anthropic  # lazy import

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text
