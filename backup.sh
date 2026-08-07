#!/bin/sh
# Stündliches SERO-Backup: 24 rotierende DB-Slots + täglicher Foto-Spiegel
cd /Users/smorty/ebay-bot || exit 1
H=$(date +%H)
/usr/bin/sqlite3 data.db ".backup backups/data-$H.db"
mkdir -p backups/photos
# Fotos täglich um 03 Uhr spiegeln — OHNE --delete: gelöschte Originale
# bleiben im Spiegel erhalten (Datenverlust 02.08. wäre so heilbar gewesen)
if [ "$H" = "03" ]; then rsync -a collection_photos/ backups/photos/; fi
