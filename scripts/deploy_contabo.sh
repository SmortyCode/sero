#!/usr/bin/env bash
# SERO → Contabo: App-Code + Apex-Landing rsyncen.
# Mac Port 3000 / launchd NICHT anfassen.
#
# data.db, .env und collection_photos werden NICHT rsync’t.
# kv['dry_run'] bleibt daher unverändert. Default ist live/false.
# Dieses Skript darf dry_run nicht auf true setzen.
#
# Voraussetzung: SSH-Key geladen (ssh-add ~/.ssh/id_ed25519), dann:
#   sh scripts/deploy_contabo.sh
# Nur Landing:
#   sh scripts/deploy_contabo.sh --landing-only

set -euo pipefail
HOST="${SERO_CONTABO_HOST:-root@169.58.182.35}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LANDING_ONLY=0
[[ "${1:-}" == "--landing-only" ]] && LANDING_ONLY=1

echo "== SSH-Check =="
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" 'echo ok' >/dev/null 2>&1; then
  echo "SSH schlägt fehl (BatchMode). Auf dem Mac:"
  echo "  eval \$(ssh-agent -s)"
  echo "  ssh-add ~/.ssh/id_ed25519"
  echo "Dann dieses Skript erneut."
  exit 1
fi

echo "== Landing → /opt/sero-landing =="
ssh "$HOST" 'mkdir -p /opt/sero-landing'
rsync -az --delete   "$REPO/landing/" "$HOST:/opt/sero-landing/"

# nginx-Config immer mit SSL-Template aus dem Repo (scp, auch bei --landing-only)
scp -q "$REPO/deploy/nginx-seromunich-landing.conf" "$HOST:/etc/nginx/sites-available/seromunich-landing"

if [[ "$LANDING_ONLY" -eq 0 ]]; then
  echo "== App-Code → /opt/sero =="
  rsync -az --delete     --exclude '.venv/' --exclude '__pycache__/' --exclude '.git/'     --exclude 'data.db*' --exclude 'backups/' --exclude '.env'     --exclude 'collection_photos/' --exclude 'logs/' --exclude 'tmp/'     "$REPO/" "$HOST:/opt/sero/"
  echo "== sero-web neu starten =="
  ssh "$HOST" 'systemctl restart sero-web'
fi

ssh "$HOST" 'bash -s' <<'REMOTE'
set -e
ln -sf /etc/nginx/sites-available/seromunich-landing /etc/nginx/sites-enabled/seromunich-landing
nginx -t
systemctl reload nginx
echo "Landing-Root:"
ls /opt/sero-landing | head
echo "HTTPS check:"
curl -skI -H 'Host: seromunich.com' --resolve seromunich.com:443:127.0.0.1 https://seromunich.com/ | head -10
curl -sk -H 'Host: seromunich.com' --resolve seromunich.com:443:127.0.0.1 https://seromunich.com/ | head -5
REMOTE

echo "Fertig."
echo "App:     https://app.seromunich.com/app/"
echo "Landing: https://seromunich.com/  (nach DNS-Umstellung)"
echo "kv dry_run bleibt unangetastet (data.db ausgeschlossen). Darf hier nicht auf true gesetzt werden."
