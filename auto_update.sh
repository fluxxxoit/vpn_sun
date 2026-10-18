#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"
echo "[$(date)] Auto-update start" >> auto.log
echo "1" | python3 vpn.py >> auto.log 2>&1
echo "[$(date)] Auto-update done" >> auto.log
