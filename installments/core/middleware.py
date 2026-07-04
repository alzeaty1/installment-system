import os
import time
import logging
from django.core.exceptions import MiddlewareNotUsed

logger = logging.getLogger(__name__)

# Path to a timestamp file that records the last backup time
BACKUP_TIMESTAMP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups', '.last_backup')
BACKUP_INTERVAL = 24 * 60 * 60  # 24 hours in seconds


class AutoBackupMiddleware:
    """
    Middleware that runs the backup script at most once every 24 hours.
    Triggered by the first request after the interval expires.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Run a backup on startup if interval has passed
        self._maybe_backup()

    def __call__(self, request):
        self._maybe_backup()
        return self.get_response(request)

    def _maybe_backup(self):
        now = time.time()
        try:
            os.makedirs(os.path.dirname(BACKUP_TIMESTAMP), exist_ok=True)
            last = os.path.getmtime(BACKUP_TIMESTAMP) if os.path.exists(BACKUP_TIMESTAMP) else 0
        except OSError:
            last = 0

        if now - last < BACKUP_INTERVAL:
            return  # Too soon

        # Run backup script
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backup.sh')
        try:
            import subprocess
            result = subprocess.run(
                ['bash', script],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                # Touch timestamp file
                with open(BACKUP_TIMESTAMP, 'w') as f:
                    f.write(str(now))
                logger.info(f"Auto-backup completed successfully: {result.stdout.strip()}")
            else:
                logger.error(f"Auto-backup failed (exit {result.returncode}): {result.stderr.strip()}")
        except Exception as e:
            logger.error(f"Auto-backup error: {e}")