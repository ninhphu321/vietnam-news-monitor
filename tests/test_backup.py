import time

from backup import backup_database


def test_backup_database_creates_timestamped_copy(tmp_path):
    db_path = tmp_path / "news.db"
    db_path.write_bytes(b"fake sqlite content")
    backup_dir = tmp_path / "backup"

    dest = backup_database(db_path, backup_dir, keep_days=14)

    assert dest.exists()
    assert dest.read_bytes() == b"fake sqlite content"
    assert dest.parent == backup_dir
    assert dest.name.startswith("news-")
    assert dest.suffix == ".db"


def test_backup_database_prunes_backups_older_than_keep_days(tmp_path):
    db_path = tmp_path / "news.db"
    db_path.write_bytes(b"content")
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()

    old_backup = backup_dir / "news-20250101-000000.db"
    old_backup.write_bytes(b"old")
    old_time = time.time() - 30 * 86400  # 30 days ago
    import os

    os.utime(old_backup, (old_time, old_time))

    backup_database(db_path, backup_dir, keep_days=14)

    assert not old_backup.exists()


def test_backup_database_keeps_recent_backups(tmp_path):
    db_path = tmp_path / "news.db"
    db_path.write_bytes(b"content")
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()

    recent_backup = backup_dir / "news-20260913-000000.db"
    recent_backup.write_bytes(b"recent")

    backup_database(db_path, backup_dir, keep_days=14)

    assert recent_backup.exists()
