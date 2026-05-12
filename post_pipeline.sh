#!/bin/bash
# Espera a que el pipeline acabe y copia el video a la cola de la Pi
LOG=/home/andreu/inspiring-factory/pipeline_wan_ada.log
VIDEO=/home/andreu/inspiring-factory/output/final_short.mp4
FIGURE="Ada Lovelace"

echo "[post] Esperando a que acabe el pipeline..."
while ! grep -q 'OK: output/final_short.mp4' "$LOG" 2>/dev/null; do
    sleep 60
done

echo "[post] Pipeline acabado. Copiando a Pi..."
FILENAME="ada_lovelace_inspiring.mp4"
sshpass -p 2611 scp -o StrictHostKeyChecking=no "$VIDEO" andreu@192.168.1.60:/home/andreu/youtube_bot/queue/inspiring-factory/"$FILENAME"

# Leer titulo del story.json
TITLE=$(python3 -c "import json; d=json.load(open('/home/andreu/inspiring-factory/stories/story.json')); print(d.get('title','Ada Lovelace — Historia inspiradora'))")
HOOK=$(python3 -c "import json; d=json.load(open('/home/andreu/inspiring-factory/stories/story.json')); print(d.get('hook',''))")
ENDING=$(python3 -c "import json; d=json.load(open('/home/andreu/inspiring-factory/stories/story.json')); print(d.get('ending',''))")

# Actualizar meta.json en la Pi
sshpass -p 2611 ssh -o StrictHostKeyChecking=no andreu@192.168.1.60 "python3 -c ""
import json, sys
path = '/home/andreu/youtube_bot/queue/inspiring-factory/meta.json'
try:
    meta = json.loads(open(path).read())
except:
    meta = {}
meta[''] = {
    'title': '',
    'description': '\n\n\n\n#shorts #AdaLovelace #historia #ciencia #inspiracion'
}
open(path, 'w').write(json.dumps(meta, ensure_ascii=False, indent=2))
print('meta.json OK')
"""

echo "[post] Done: $FILENAME en cola Pi"
