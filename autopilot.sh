#!/bin/bash
# Autopilot: cuando el WAN de Ada acabe, copia a Pi y arranca Alan Turing
set -e
PYTHON=/home/andreu/miniconda3/bin/python
DIR=/home/andreu/inspiring-factory
PI=andreu@192.168.1.60
QUEUE=/home/andreu/youtube_bot/queue/inspiring-factory
CHANNEL=config/channel_inspirational_science_es.json

cd $DIR

push_to_pi() {
    local figure=$1
    local filename=$2
    echo "[autopilot] Copiando $figure a Pi..."
    scp output/final_short.mp4 $PI:$QUEUE/$filename
    TITLE=$($PYTHON -c "import json; d=json.load(open('stories/story.json')); print(d.get('title',''))")
    HOOK=$($PYTHON -c "import json; d=json.load(open('stories/story.json')); print(d.get('hook',''))")
    ENDING=$($PYTHON -c "import json; d=json.load(open('stories/story.json')); print(d.get('ending',''))")
    ssh $PI "python3 -c \"
import json
path='/home/andreu/youtube_bot/queue/inspiring-factory/meta.json'
try:
    meta=json.load(open(path))
except:
    meta={}
meta['$filename']={'title':'$TITLE','description':'$HOOK\n\n$ENDING\n\n#shorts #historia #ciencia #inspiracion'}
open(path,'w').write(json.dumps(meta,ensure_ascii=False,indent=2))
\""
    echo "[autopilot] $figure en cola Pi OK"
}

run_figure() {
    local figure=$1
    local filename=$2
    echo "[autopilot] === Iniciando: $figure ==="
    rm -f images/generated/*.png video/clips/*.mp4 audio/* stories/story.json output/final_short.mp4
    pkill -f ollama 2>/dev/null || true
    sleep 2
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 5
    $PYTHON generate_and_save_story.py --figure "$figure" --channel $CHANNEL
    pkill -f ollama 2>/dev/null || true
    sleep 3
    $PYTHON auto_generate_images.py --channel $CHANNEL
    $PYTHON generate_voice.py --channel $CHANNEL
    $PYTHON generate_video_wan.py --channel $CHANNEL
    $PYTHON assemble_video.py --channel $CHANNEL
    push_to_pi "$figure" "$filename"
    echo "[autopilot] === $figure DONE ==="
}

# Esperar a que Ada acabe (ya está corriendo)
echo "[autopilot] Esperando fin de Ada Lovelace..."
while ! grep -q 'OK: output/final_short.mp4' pipeline_wan_ada.log 2>/dev/null; do
    sleep 60
done
push_to_pi "Ada Lovelace" "ada_lovelace_inspiring.mp4"

# Alan Turing
run_figure "Alan Turing" "alan_turing_inspiring.mp4"

echo "[autopilot] Todo listo. Notificando Telegram..."
$PYTHON -c "
import sys; sys.path.insert(0,'/home/andreu/youtube_bot')
from telegram_bot import send_message
send_message('✅ Inspiring Factory autopilot: Ada Lovelace + Alan Turing en cola Pi.')
"
