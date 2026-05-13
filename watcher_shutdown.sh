#!/bin/bash
echo "[watcher] Esperando Hedy Lamarr en cola Pi..."
while true; do
    if ssh andreu@192.168.1.60 'ls /home/andreu/youtube_bot/queue/inspiring-factory/hedy_lamarr_inspiring.mp4' 2>/dev/null; then
        echo "[watcher] Hedy Lamarr lista. Parando autopilot..."
        pkill -f autopilot_inspiring.py
        sleep 10
        echo "[watcher] Apagando sistema..."
        echo '2611' | sudo -S shutdown -h now
        exit 0
    fi
    sleep 120
done
