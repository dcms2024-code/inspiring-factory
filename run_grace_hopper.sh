#!/bin/bash
set -e
PYTHON=/home/andreu/miniconda3/bin/python
DIR=/home/andreu/inspiring-factory
PI=andreu@192.168.1.60
QUEUE=/home/andreu/youtube_bot/queue/inspiring-factory
CHANNEL=config/channel_inspirational_science_es.json
FIGURE="Grace Hopper"
FILENAME="grace_hopper_inspiring.mp4"

cd $DIR

echo "[grace] Limpiando archivos anteriores..."
rm -f images/generated/*.png video/clips/*.mp4 audio/* stories/story.json output/final_short.mp4

echo "[grace] Arrancando Ollama..."
pkill -f ollama 2>/dev/null || true
sleep 2
nohup ollama serve > /tmp/ollama.log 2>&1 &
sleep 5

echo "[grace] Generando historia..."
$PYTHON generate_and_save_story.py --figure "$FIGURE" --channel $CHANNEL
pkill -f ollama 2>/dev/null || true
sleep 3

echo "[grace] Generando imagenes..."
$PYTHON auto_generate_images.py --channel $CHANNEL

echo "[grace] Generando voz..."
$PYTHON generate_voice.py --channel $CHANNEL

echo "[grace] Generando clips WAN..."
$PYTHON generate_video_wan.py --channel $CHANNEL

echo "[grace] Ensamblando video..."
$PYTHON assemble_video.py --channel $CHANNEL

echo "[grace] Copiando a Pi..."
scp output/final_short.mp4 $PI:$QUEUE/$FILENAME
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
meta['$FILENAME']={'title':'$TITLE','description':'$HOOK\n\n$ENDING\n\n#shorts #historia #ciencia #inspiracion'}
open(path,'w').write(json.dumps(meta,ensure_ascii=False,indent=2))
\""
echo "[grace] === Grace Hopper DONE ==="
