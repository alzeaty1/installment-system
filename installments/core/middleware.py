import os
import time
import logging

from .backup_utils import create_backup
from .models import Account

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
        except Exception as e:
            logger.error(f"Auto-backup error: {e}")


class AccountMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            account_id = request.session.get("account_id")
            if not account_id:
                account = Account.objects.first()
                if not account:
                    account = Account.objects.create(name="الحساب الرئيسي")
                request.session["account_id"] = account.id
                account_id = account.id
            request.current_account = Account.objects.get(id=account_id)
        else:
            request.current_account = None
        return self.get_response(request)
