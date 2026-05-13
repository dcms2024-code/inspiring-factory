#!/bin/bash
set -e
cd /home/andreu/inspiring-factory
PYTHON=/home/andreu/miniconda3/bin/python
CHANNEL=config/channel_inspirational_science_es.json

echo "=== START $(date) ==="

$PYTHON auto_generate_images.py --channel $CHANNEL

for f in images/generated/scene_*.png; do
  num=$(basename $f | sed 's/scene_//;s/.png//')
  padded=$(printf '%02d' $num)
  cp "$f" "/home/andreu/ai-tools/ComfyUI/input/inspiring_scene_${padded}.png"
done
echo "Imagenes copiadas"

rm -f video/clips/*.mp4
$PYTHON generate_video_wan.py --channel $CHANNEL

$PYTHON assemble_video.py --channel $CHANNEL

echo "=== DONE $(date) ==="
