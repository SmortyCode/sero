#!/usr/bin/env bash
# Alte Sammlungsfotos Mac → Contabo wiederherstellen.
# Mac-Originale und Mac-data.db bleiben unangetastet. Kein Cutout, kein eBay.
#
# Voraussetzung:
#   eval "$(ssh-agent -s)"
#   ssh-add ~/.ssh/id_ed25519
# Dann:
#   sh scripts/restore_photos_contabo.sh

set -euo pipefail
HOST="${SERO_CONTABO_HOST:-root@169.58.182.35}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
COL_SRC="$REPO/collection_photos"
REMOTE_ROOT="/opt/sero"

echo "== SSH-Check =="
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" 'echo ok' >/dev/null 2>&1; then
  echo "SSH schlägt fehl (BatchMode). Auf dem Mac:"
  echo "  eval \"\$(ssh-agent -s)\""
  echo "  ssh-add ~/.ssh/id_ed25519"
  echo "Dann dieses Skript erneut."
  exit 1
fi

if [[ ! -d "$COL_SRC" ]]; then
  echo "Fehlt lokal: $COL_SRC"
  exit 1
fi

MAC_FILES="$(find "$COL_SRC" -type f ! -path '*/_trash/*' | wc -l | tr -d ' ')"
MAC_SIZE="$(du -sh "$COL_SRC" | awk '{print $1}')"
echo "Mac collection_photos: $MAC_FILES Dateien (ohne _trash-Zählfilter in du), Größe gesamt $MAC_SIZE"

echo "== Contabo vorher =="
ssh "$HOST" bash -s <<'REMOTE'
set -e
ROOT=/opt/sero
echo "hostname=$(hostname)"
echo -n "collection_photos files: "
find "$ROOT/collection_photos" -type f 2>/dev/null | wc -l || echo 0
echo -n "collection_photos size: "
du -sh "$ROOT/collection_photos" 2>/dev/null || echo "(fehlt)"
echo -n "data.db: "
ls -la "$ROOT/data.db" 2>/dev/null || echo "(fehlt)"
if [[ -f "$ROOT/data.db" ]]; then
  python3 - <<'PY'
import sqlite3, json
from pathlib import Path
root = Path("/opt/sero")
db = root / "data.db"
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
items = conn.execute("SELECT id, data FROM collection_items").fetchall()
exist = miss = mac_path = opt_path = 0
sample_miss = []
for iid, raw in items:
    d = json.loads(raw)
    for p in (d.get("photos") or []):
        s = str(p)
        if s.startswith("/Users/smorty"):
            mac_path += 1
        elif s.startswith("/opt/sero"):
            opt_path += 1
        if Path(s).exists():
            exist += 1
        else:
            miss += 1
            if len(sample_miss) < 5:
                sample_miss.append(s)
print(f"items={len(items)} photo_refs_exist={exist} missing={miss}")
print(f"path_style mac_abs={mac_path} opt_abs={opt_path}")
print("sample_missing:", sample_miss)
print("mac_path_resolves:", Path("/Users/smorty/ebay-bot").exists())
PY
fi
REMOTE

echo "== Backup Contabo-DB auf dem Server (nur Remote, Mac unberührt) =="
ssh "$HOST" bash -s <<'REMOTE'
set -e
ROOT=/opt/sero
mkdir -p "$ROOT/backups"
TS=$(date +%Y%m%d-%H%M%S)
if [[ -f "$ROOT/data.db" ]]; then
  if command -v sqlite3 >/dev/null; then
    sqlite3 "$ROOT/data.db" ".backup '$ROOT/backups/data-pre-photo-restore-$TS.db'"
  else
    cp -a "$ROOT/data.db" "$ROOT/backups/data-pre-photo-restore-$TS.db"
    [[ -f "$ROOT/data.db-wal" ]] && cp -a "$ROOT/data.db-wal" "$ROOT/backups/data-pre-photo-restore-$TS.db-wal"
    [[ -f "$ROOT/data.db-shm" ]] && cp -a "$ROOT/data.db-shm" "$ROOT/backups/data-pre-photo-restore-$TS.db-shm"
  fi
  echo "Remote-Backup: $ROOT/backups/data-pre-photo-restore-$TS.db"
fi
REMOTE

echo "== rsync collection_photos (Mac → Contabo, Mac wird nicht gelöscht) =="
rsync -az --stats \
  "$COL_SRC/" "$HOST:$REMOTE_ROOT/collection_photos/"

echo "== Symlink für Mac-Absolutpfade in der Contabo-DB =="
ssh "$HOST" bash -s <<'REMOTE'
set -e
mkdir -p /Users/smorty
if [[ -e /Users/smorty/ebay-bot && ! -L /Users/smorty/ebay-bot ]]; then
  echo "FEHLER: /Users/smorty/ebay-bot existiert und ist kein Symlink — Abbruch."
  ls -la /Users/smorty/ebay-bot
  exit 1
fi
ln -sfn /opt/sero /Users/smorty/ebay-bot
ls -la /Users/smorty/ebay-bot
test -d /Users/smorty/ebay-bot/collection_photos
echo "Symlink OK"
REMOTE

echo "== Referenced Draft-tmp Ordner (falls vorhanden) =="
cd "$REPO"
TMP_LIST="$(python3 - <<'PY'
import sqlite3, json
from pathlib import Path
conn = sqlite3.connect("file:data.db?mode=ro", uri=True)
seen = set()
for _, raw in conn.execute("SELECT id, data FROM drafts"):
    d = json.loads(raw)
    for k in ("photos", "original_photos", "rendered_photos"):
        for p in d.get(k) or []:
            pp = Path(p)
            if "tmp" in pp.parts:
                i = pp.parts.index("tmp")
                if i + 1 < len(pp.parts):
                    name = pp.parts[i + 1]
                    local = Path("tmp") / name
                    if local.is_dir() and name not in seen:
                        seen.add(name)
                        print(name)
PY
)"
if [[ -n "$TMP_LIST" ]]; then
  ssh "$HOST" "mkdir -p $REMOTE_ROOT/tmp"
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    rsync -az "$REPO/tmp/$name/" "$HOST:$REMOTE_ROOT/tmp/$name/"
  done <<< "$TMP_LIST"
  echo "tmp-Ordner synchronisiert: $(echo "$TMP_LIST" | grep -c . || true)"
else
  echo "Keine lokalen Draft-tmp-Ordner zum Syncen."
fi

echo "== sero-web neu starten =="
ssh "$HOST" 'systemctl restart sero-web && systemctl is-active sero-web'

echo "== Contabo nachher (Spot-Check) =="
ssh "$HOST" bash -s <<'REMOTE'
set -e
ROOT=/opt/sero
echo -n "collection_photos files (ohne _trash): "
find "$ROOT/collection_photos" -type f ! -path '*/_trash/*' | wc -l
python3 - <<'PY'
import sqlite3, json
from pathlib import Path
root = Path("/opt/sero")
conn = sqlite3.connect(f"file:{root/'data.db'}?mode=ro", uri=True)
items = conn.execute("SELECT id, data FROM collection_items").fetchall()
exist = miss = 0
spot = None
for iid, raw in items:
    d = json.loads(raw)
    photos = d.get("photos") or []
    ok = all(Path(p).exists() for p in photos) if photos else False
    if photos and ok:
        exist += 1
        if spot is None:
            spot = (iid, d.get("title") or d.get("name"), photos[0])
    elif photos:
        miss += 1
print(f"items_with_all_photos_ok={exist} items_with_missing={miss}")
if spot:
    print(f"spot_ok id={spot[0]} title={spot[1]!r}")
    print(f"spot_file={spot[2]} size={Path(spot[2]).stat().st_size}")
p = Path("/Users/smorty/ebay-bot/collection_photos/35a64a879d80/00_cut.png")
print(f"known_35a64a879d80_exists={p.exists()} size={p.stat().st_size if p.exists() else 0}")
PY
REMOTE

echo
echo "Fertig. Mac-Fotos und Mac-DB wurden nicht gelöscht/überschrieben."
echo "Prüfen (eingeloggt): https://app.seromunich.com/app/"
echo "Bekanntes Stück z.B. Sammlung öffnen — Thumbnails müssen wieder die alten Freisteller sein."
