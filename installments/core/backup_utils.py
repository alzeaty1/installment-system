import os
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings

MAX_BACKUPS = 15


def _backup_dir():
    d = Path(settings.BASE_DIR) / "backups"
    d.mkdir(exist_ok=True)
    return d


def _is_backup_file(name):
    return name.startswith("db_backup_") and name.endswith(".sqlite3")


def create_backup():
    db_path = settings.DATABASES["default"]["NAME"]
    backup_dir = _backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"db_backup_{timestamp}.sqlite3"
    dest = backup_dir / name

    if os.path.exists(db_path):
        shutil.copy2(db_path, dest)

    backups = sorted(
        [f for f in backup_dir.iterdir() if _is_backup_file(f.name)],
        key=lambda f: f.name,
    )
    while len(backups) > MAX_BACKUPS:
        old = backups.pop(0)
        try:
            old.unlink()
        except OSError:
            pass

    return name


def list_backups():
    backup_dir = _backup_dir()
    result = []
    for f in sorted(backup_dir.iterdir(), key=lambda f: f.name, reverse=True):
        if _is_backup_file(f.name):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            result.append(
                {
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    "size_display": _human_size(f.stat().st_size),
                }
            )
    return result


def delete_backup(name):
    backup_dir = _backup_dir()
    path = backup_dir / name
    if path.exists() and _is_backup_file(name):
        path.unlink()
        return True
    return False


def restore_backup(name):
    backup_dir = _backup_dir()
    backup_path = backup_dir / name
    db_path = settings.DATABASES["default"]["NAME"]
    if backup_path.exists() and _is_backup_file(name):
        shutil.copy2(backup_path, db_path)
        return True
    return False


def _human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
