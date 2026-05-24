"""
app/services/notifications.py - Web Push and Telegram notification dispatcher.

Spec §7.1:
  send_web_push()   - VAPID-signed Web Push to browser PushSubscription
  send_telegram()   - Telegram message via python-telegram-bot async API
  notify_user()     - Fetch Firestore profile and dispatch to all active channels
  notify_broadcast()- Send to all users with a given notification preference

Dependencies:
  pywebpush         - pip-installable, FOSS Web Push implementation
  python-telegram-bot - async Telegram bot API wrapper

Both channels are optional — if a user hasn't set up one, the other still fires.
If neither channel is configured for a user, the call is a no-op.
"""

import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


# ── Web Push ──────────────────────────────────────────────────────────────────

async def send_web_push(subscription: dict, title: str, body: str, url: str = "/") -> None:
    """
    Send a Web Push notification to a single browser subscription.

    Args:
        subscription: The PushSubscription object stored in Firestore.
                      Must have keys: endpoint, keys.p256dh, keys.auth.
        title:        Notification title (displayed in browser notification panel).
        body:         Notification body text.
        url:          URL to open when notification is clicked.

    Side effect:
        If the subscription returns HTTP 410 (Gone), deletes it from Firestore
        so we don't keep sending to dead subscriptions.
    """
    if not settings.VAPID_PRIVATE_KEY:
        logger.debug("VAPID keys not configured — skipping Web Push")
        return

    try:
        from pywebpush import webpush, WebPushException  # lazy import

        endpoint = subscription.get("endpoint", "")
        keys = subscription.get("keys", {})

        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": keys.get("p256dh", ""),
                    "auth": keys.get("auth", ""),
                },
            },
            data=json.dumps({"title": title, "body": body, "url": url}),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}",
            },
        )
        logger.debug("Web Push sent to %s…", endpoint[:50])

    except Exception as exc:
        # Check for 410 Gone — subscription expired or user revoked permission
        exc_str = str(exc)
        if "410" in exc_str or "Gone" in exc_str:
            logger.info("Subscription expired (410) — will be cleaned from Firestore")
            await _delete_push_subscription(subscription.get("endpoint", ""))
        else:
            logger.warning("Web Push failed: %s", exc)


async def send_telegram(chat_id: str, message: str) -> None:
    """
    Send a Telegram message to a user's chat.

    Args:
        chat_id: Telegram chat ID stored in Firestore (user.telegram_chat_id).
        message: Message text to send.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.debug("TELEGRAM_BOT_TOKEN not configured — skipping Telegram")
        return

    try:
        from telegram import Bot  # lazy import — python-telegram-bot

        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML",
        )
        logger.debug("Telegram message sent to chat %s", chat_id)
    except Exception as exc:
        logger.warning("Telegram send failed for chat %s: %s", chat_id, exc)


async def notify_user(uid: str, title: str, body: str, url: str = "/") -> None:
    """
    Send a notification to a specific user via all their configured channels.

    Fetches the user's Firestore document to find:
      - web_push_subscription (dict or None)
      - telegram_chat_id (str or None)

    Both channels fire independently — if one fails, the other still runs.
    If neither channel is configured, this is a no-op.
    """
    try:
        from app.firebase import get_firestore_client
        db_fs = get_firestore_client()
        doc = db_fs.collection("users").document(uid).get()
        if not doc.exists:
            return
        data = doc.to_dict()
    except Exception as exc:
        logger.warning("Could not fetch Firestore user %s: %s", uid, exc)
        return

    # Web Push
    push_sub = data.get("web_push_subscription")
    if push_sub:
        await send_web_push(push_sub, title, body, url)

    # Telegram
    telegram_id = data.get("telegram_chat_id")
    if telegram_id:
        await send_telegram(telegram_id, f"<b>{title}</b>\n{body}")


async def notify_broadcast(
    title: str,
    body: str,
    notification_pref: str,
    url: str = "/",
) -> None:
    """
    Send a notification to all Firestore users who have a specific preference enabled.

    Args:
        title:             Notification title.
        body:              Notification body.
        notification_pref: Firestore preference key to filter on.
                           e.g. 'safety_car', 'race_start', 'fastest_lap'
        url:               Click-through URL.

    This is used for global events (safety car, race start) that affect all users.
    For driver-specific events (pit stops, fastest lap), use live_timing._notify_followed_driver_users().
    """
    try:
        from app.firebase import get_firestore_client
        db_fs = get_firestore_client()

        # Firestore doesn't support querying nested map fields directly.
        # Fetch all users and filter in Python (acceptable for free tier user counts).
        docs = db_fs.collection("users").stream()

        for doc in docs:
            data = doc.to_dict()
            prefs = data.get("notification_prefs", {})
            if not prefs.get(notification_pref, False):
                continue
            await notify_user(doc.id, title, body, url)

    except Exception as exc:
        logger.warning("notify_broadcast failed for pref '%s': %s", notification_pref, exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _delete_push_subscription(endpoint: str) -> None:
    """
    Remove an expired Web Push subscription from Firestore.
    Called when we receive HTTP 410 from the push service.
    """
    try:
        from app.firebase import get_firestore_client
        from google.cloud.firestore_v1 import DELETE_FIELD

        db_fs = get_firestore_client()
        # Find the user with this endpoint
        docs = db_fs.collection("users").stream()
        for doc in docs:
            data = doc.to_dict()
            sub = data.get("web_push_subscription", {})
            if sub and sub.get("endpoint") == endpoint:
                db_fs.collection("users").document(doc.id).update({
                    "web_push_subscription": DELETE_FIELD
                })
                logger.info("Deleted expired push subscription for user %s", doc.id)
                break
    except Exception as exc:
        logger.debug("Could not delete push subscription: %s", exc)
