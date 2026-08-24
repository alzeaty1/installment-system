import os
import time
import logging

from .backup_utils import create_backup
from .models import Account, Contract, Customer, Supplier

logger = logging.getLogger(__name__)

BACKUP_INTERVAL = 24 * 60 * 60  # 24 hours


class AutoBackupMiddleware:
    """
    Middleware that creates a SQLite database backup at most once every 24 hours
    by copying db.sqlite3 to the backups/ directory via Python (no bash required).
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._maybe_backup()

    def __call__(self, request):
        self._maybe_backup()
        return self.get_response(request)

    def _maybe_backup(self):
        try:
            from django.conf import settings
            ts_file = os.path.join(settings.BASE_DIR, "backups", ".last_backup")
            os.makedirs(os.path.dirname(ts_file), exist_ok=True)

            now = time.time()
            try:
                last = os.path.getmtime(ts_file) if os.path.exists(ts_file) else 0
            except OSError:
                last = 0

            if now - last < BACKUP_INTERVAL:
                return

            name = create_backup()
            with open(ts_file, "w") as f:
                f.write(str(now))
            logger.info(f"Auto-backup completed: {name}")

            # إرسال النسخة على تيليجرام (fail-soft)
            try:
                from datetime import datetime
                from django.conf import settings as _s
                from .telegram_notify import send_document
                dest = os.path.join(_s.BASE_DIR, "backups", name)
                ok, detail = send_document(
                    dest,
                    caption=f"🗄️ نسخة احتياطية — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n{name}",
                )
                tg_file = os.path.join(_s.BASE_DIR, "backups", ".last_telegram")
                with open(tg_file, "w", encoding="utf-8") as f:
                    f.write(f"{now}|{'ok' if ok else 'fail'}|{detail[:100]}")
                if ok:
                    logger.info("Backup sent to telegram")
                else:
                    logger.warning(f"Telegram backup send failed: {detail}")
            except Exception as te:
                logger.error(f"telegram backup error: {te}")
        except Exception as e:
            logger.error(f"Auto-backup error: {e}")


class AccountMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _default_account(self):
        """Pick the real working account instead of an empty/test account."""
        accounts = list(Account.objects.order_by("id"))
        if not accounts:
            return Account.objects.create(name="الحساب الرئيسي")

        def score(account):
            return (
                Contract.objects.filter(account=account).count()
                + Customer.objects.filter(account=account).count()
                + Supplier.objects.filter(account=account).count()
            )

        return max(accounts, key=lambda account: (score(account), -account.id))

    def _is_empty_account(self, account):
        return not (
            Contract.objects.filter(account=account).exists()
            or Customer.objects.filter(account=account).exists()
            or Supplier.objects.filter(account=account).exists()
        )

    def __call__(self, request):
        if request.user.is_authenticated:
            account_id = request.session.get("account_id")
            default_account = self._default_account()
            account = Account.objects.filter(id=account_id).first() if account_id else None

            # Existing sessions may point to an old empty test account. Prefer the
            # account that actually has data so links like /suppliers/<id>/ work.
            if account is None or (self._is_empty_account(account) and default_account.id != account.id):
                account = default_account
                request.session["account_id"] = account.id

            request.current_account = account
        else:
            request.current_account = None
        return self.get_response(request)
