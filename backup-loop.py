#!/usr/bin/env python3
import json, os, shutil, sqlite3, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError, HfHubHTTPError

DB_PATH = Path(os.environ.get('NEW_API_DB_PATH', '/data/one-api.db'))
REPO = os.environ.get('HF_DATASET_REPO', 'hoshisakihk/new-api-sqlite-backup')
TOKEN = os.environ.get('HF_TOKEN') or os.environ.get('HUGGINGFACE_HUB_TOKEN')
INTERVAL = int(os.environ.get('BACKUP_INTERVAL_SECONDS', '900'))


def log(*args):
    print('[sqlite-backup]', *args, flush=True)


def api():
    if not TOKEN:
        raise RuntimeError('HF_TOKEN/HUGGINGFACE_HUB_TOKEN is not set')
    return HfApi(token=TOKEN)


def restore():
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        log('local db exists, skip restore', DB_PATH, DB_PATH.stat().st_size)
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        path = hf_hub_download(repo_id=REPO, repo_type='dataset', filename='one-api.db', token=TOKEN, local_dir='/tmp/new-api-restore')
    except (EntryNotFoundError, RepositoryNotFoundError, HfHubHTTPError) as e:
        log('no remote backup available yet:', type(e).__name__, str(e)[:160])
        return
    shutil.copy2(path, DB_PATH)
    log('restored db from dataset', REPO, '->', DB_PATH, DB_PATH.stat().st_size)


def sqlite_backup_copy(src: Path, dst: Path):
    # Prefer SQLite online backup API for consistency.
    try:
        src_uri = f'file:{src}?mode=ro'
        con = sqlite3.connect(src_uri, uri=True, timeout=30)
        out = sqlite3.connect(str(dst), timeout=30)
        with out:
            con.backup(out)
        out.close(); con.close()
        return
    except Exception as e:
        log('sqlite backup API failed, fallback copy:', type(e).__name__, str(e)[:160])
    shutil.copy2(src, dst)


def backup_once():
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        log('db missing/empty, skip backup', DB_PATH)
        return False
    tmpdir = Path(tempfile.mkdtemp(prefix='new-api-backup-'))
    db_copy = tmpdir / 'one-api.db'
    sqlite_backup_copy(DB_PATH, db_copy)
    meta = {
        'source': 'render-new-api',
        'db_path': str(DB_PATH),
        'repo': REPO,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'size': db_copy.stat().st_size,
        'render_service_id': os.environ.get('RENDER_SERVICE_ID'),
        'render_external_url': os.environ.get('RENDER_EXTERNAL_URL'),
    }
    (tmpdir / 'backup-meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    a = api()
    a.upload_file(repo_id=REPO, repo_type='dataset', path_or_fileobj=str(db_copy), path_in_repo='one-api.db', commit_message='Backup new-api SQLite database')
    a.upload_file(repo_id=REPO, repo_type='dataset', path_or_fileobj=str(tmpdir / 'backup-meta.json'), path_in_repo='backup-meta.json', commit_message='Update backup metadata')
    log('backup uploaded', meta)
    return True


def loop():
    # initial delay gives new-api time to create DB on first boot
    time.sleep(int(os.environ.get('BACKUP_INITIAL_DELAY_SECONDS', '120')))
    while True:
        try:
            backup_once()
        except Exception as e:
            log('backup failed:', type(e).__name__, str(e)[:300])
        time.sleep(INTERVAL)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'once'
    if cmd == 'restore': restore()
    elif cmd == 'loop': loop()
    elif cmd == 'once': backup_once()
    else: raise SystemExit(f'unknown command: {cmd}')
