"""app/routers/users.py - /users/* user preferences endpoints."""

from fastapi import APIRouter, Depends
from app.firebase import get_current_user, get_firestore_client
from app.models.schemas import (
    UserProfileSchema, UserPreferencesRequest, WebPushSubscriptionRequest, OKResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


def _get_profile(uid: str) -> dict:
    """Fetch user document from Firestore. Returns empty dict if not found."""
    db = get_firestore_client()
    doc = db.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else {}


@router.get("/me", response_model=UserProfileSchema)
async def get_me(user: dict = Depends(get_current_user)):
    """Return the current user's preferences from Firestore."""
    profile = _get_profile(user["uid"])
    return UserProfileSchema(
        uid=user["uid"],
        display_name=profile.get("display_name"),
        email=profile.get("email"),
        followed_drivers=profile.get("followed_drivers", []),
        followed_constructors=profile.get("followed_constructors", []),
        notification_prefs=profile.get("notification_prefs", {}),
        season_pred_profile=profile.get("season_pred_profile", "balanced"),
        telegram_chat_id=profile.get("telegram_chat_id"),
        has_web_push=profile.get("web_push_subscription") is not None,
    )


@router.put("/me/preferences", response_model=OKResponse)
async def update_preferences(
    body: UserPreferencesRequest,
    user: dict = Depends(get_current_user),
):
    """
    Update user preferences in Firestore.
    Only updates fields that are present in the request body (partial update).
    """
    db = get_firestore_client()
    updates: dict = {}

    if body.followed_drivers is not None:
        updates["followed_drivers"] = body.followed_drivers
    if body.followed_constructors is not None:
        updates["followed_constructors"] = body.followed_constructors
    if body.notification_prefs is not None:
        updates["notification_prefs"] = body.notification_prefs
    if body.season_pred_profile is not None:
        updates["season_pred_profile"] = body.season_pred_profile
    if body.telegram_chat_id is not None:
        updates["telegram_chat_id"] = body.telegram_chat_id

    if updates:
        db.collection("users").document(user["uid"]).update(updates)

    return OKResponse()


@router.post("/me/push-subscription", response_model=OKResponse)
async def save_push_subscription(
    body: WebPushSubscriptionRequest,
    user: dict = Depends(get_current_user),
):
    """
    Saves the browser Web Push subscription object to Firestore.
    Called by the frontend after the user grants notification permission.
    The subscription is later used by notifications.py -> send_web_push().
    """
    db = get_firestore_client()
    db.collection("users").document(user["uid"]).update({
        "web_push_subscription": {
            "endpoint": body.endpoint,
            "keys": body.keys,
            "expiration_time": body.expiration_time,
        }
    })
    return OKResponse()
