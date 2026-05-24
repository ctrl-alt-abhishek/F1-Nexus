"""app/routers/auth.py - /auth/* endpoints."""

from fastapi import APIRouter, Depends
from app.firebase import get_current_user, get_firestore_client
from app.models.schemas import UserSyncRequest, UserProfileSchema, OKResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/sync", response_model=UserProfileSchema)
async def sync_user(
    body: UserSyncRequest,
    user: dict = Depends(get_current_user),
):
    """
    Called by the frontend immediately after Google sign-in.
    Creates the Firestore user document if it doesn't exist, or updates it.
    Returns the full user profile.
    """
    db = get_firestore_client()
    uid = user["uid"]
    email = user["email"]
    ref = db.collection("users").document(uid)
    doc = ref.get()

    if not doc.exists:
        profile = {
            "display_name": body.display_name or email.split("@")[0],
            "email": email,
            "followed_drivers": [],
            "followed_constructors": [],
            "notification_prefs": {
                "pit_alerts": True,
                "safety_car": True,
                "fastest_lap": False,
                "race_start": True,
            },
            "season_pred_profile": "balanced",
            "web_push_subscription": None,
            "telegram_chat_id": None,
        }
        ref.set(profile)
    else:
        # Update mutable fields from token claims on each login.
        ref.update({"email": email})
        profile = doc.to_dict()

    return UserProfileSchema(
        uid=uid,
        display_name=profile.get("display_name"),
        email=profile.get("email"),
        followed_drivers=profile.get("followed_drivers", []),
        followed_constructors=profile.get("followed_constructors", []),
        notification_prefs=profile.get("notification_prefs", {}),
        season_pred_profile=profile.get("season_pred_profile", "balanced"),
        telegram_chat_id=profile.get("telegram_chat_id"),
        has_web_push=profile.get("web_push_subscription") is not None,
    )
