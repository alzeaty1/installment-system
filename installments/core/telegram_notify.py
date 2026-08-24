"""إرسال النسخ الاحتياطية إلى تيليجرام (Bot API مباشر)."""
import logging
import os

import requests

logger = logging.getLogger(__name__)


def send_document(filepath, caption=""):
    """ابعت ملف كـ document لشات تيليجرام المضبوط في .env.

    يرجع (ok: bool, detail: str).
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_BACKUP_CHAT_ID")
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_BACKUP_CHAT_ID غير مضبوطين في .env"

    url = f"https://api.telegram.org/bot{token}/sendDocument"
    try:
        with open(filepath, "rb") as f:
            r = requests.post(
                url,
                data={"chat_id": str(chat_id), "caption": caption},
                files={"document": f},
                timeout=120,
            )
        if r.ok:
            return True, "sent"
        return False, r.text[:200]
    except Exception as exc:
        logger.error(f"telegram backup send failed: {exc}")
        return False, str(exc)
