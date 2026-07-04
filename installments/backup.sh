#!/bin/bash
# Daily backup script for installment-system
# Saves DB + media to backups/ with date, keeps last 30 days

set -e

PROJECT_DIR="/home/alzeaty1/installment-system/installments"
BACKUP_DIR="$PROJECT_DIR/backups"
DATE=$(date +%Y-%m-%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# 1. Backup SQLite DB
echo "[$(date)] Backing up database..."
cp "$PROJECT_DIR/db.sqlite3" "$BACKUP_DIR/db_backup_$DATE.sqlite3"

# 2. Backup media folder (if exists)
if [ -d "$PROJECT_DIR/media" ]; then
    echo "[$(date)] Backing up media..."
    tar -czf "$BACKUP_DIR/media_backup_$DATE.tar.gz" -C "$PROJECT_DIR" media/
fi

# 3. Cleanup: keep only last 30 days
echo "[$(date)] Cleaning old backups..."
find "$BACKUP_DIR" -name "db_backup_*" -mtime +30 -delete
find "$BACKUP_DIR" -name "media_backup_*" -mtime +30 -delete

# 4. Summary
DB_COUNT=$(find "$BACKUP_DIR" -name "db_backup_*" | wc -l)
echo "[$(date)] ✅ Backup complete! Total backups: $DB_COUNT"
ls -lh "$BACKUP_DIR"/db_backup_$DATE.sqlite3 2>/dev/null
