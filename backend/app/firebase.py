"""
app/firebase.py - Firebase Admin SDK initialization and auth dependencies.

Initializes once at startup via init_firebase(). All Firebase Admin SDK calls
(token verification, Firestore access) go through this module.
"""

import firebase_admin
from firebase_admin import auth, credentials, firestore
from fastapi import Header, HTTPException, status

from app.config import settings

# Module-level reference to the Firestore client, set after init_firebase() runs.
_firestore_client = None


def init_firebase() -> None:
    """
    Initialize Firebase Admin SDK using service account credentials from settings.
    Called once in app/main.py lifespan handler on startup.
    Safe to call multiple times - no-ops if already initialized.
    """
    if firebase_admin._apps:
        return

    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": settings.FIREBASE_PROJECT_ID,
        "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
        "client_email": settings.FIREBASE_CLIENT_EMAIL,
        "token_uri": "https://oauth2.googleapis.com/token",
    })

    firebase_admin.initialize_app(cred)

    global _firestore_client
    _firestore_client = firestore.client()


def verify_token(token: str) -> dict:
    """
    Verify a Firebase ID token and return the decoded claims.

    Raises:
        firebase_admin.auth.InvalidIdTokenError - if token is malformed or expired.
        firebase_admin.auth.RevokedIdTokenError - if token has been revoked.
    """
    return auth.verify_id_token(token)


def get_firestore_client():
    """
    Return the Firestore client. Must be called after init_firebase().
    Raises RuntimeError if Firebase has not been initialized yet.
    """
    if _firestore_client is None:
        raise RuntimeError("Firebase not initialized. Call init_firebase() first.")
    return _firestore_client


async def get_current_user(authorization: str = Header(...)) -> dict:
    """
    FastAPI dependency for protecting endpoints with Firebase auth.

    Extracts the Bearer token from the Authorization header, verifies it with
    Firebase Admin SDK, and returns the decoded token claims.

    Dev mode: if the token is exactly 'dummy_dev_token', returns a mock user
    to allow the frontend to function without real Firebase client credentials.

    Returns:
        dict with at minimum {"uid": str, "email": str}

    Raises:
        HTTPException(401) - if token is missing, malformed, or expired.

    Usage:
        @router.get("/protected")
        async def endpoint(user: dict = Depends(get_current_user)):
            uid = user["uid"]
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be 'Bearer <token>'",
        )

    token = authorization.removeprefix("Bearer ").strip()

    # Dev bypass: accept dummy token for local development
    if token == "dummy_dev_token":
        return {
            "uid": "local_dev_user",
            "email": "dev@f1nexus.local",
        }

    try:
        decoded = verify_token(token)
        return {
            "uid": decoded["uid"],
            "email": decoded.get("email", ""),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Firebase token: {exc}",
        )
