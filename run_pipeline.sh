#!/bin/bash
# Full pipeline: images → WAN I2V clips → assemble
# Usage: bash run_pipeline.sh [--channel config/channel_X.json]
set -e

PYTHON=/home/andreu/miniconda3/bin/python
CHANNEL_ARG="${@:---channel config/channel_inspirational_science_es.json}"

cd "$(dirname "$0")"

echo "=== START $(date) ==="

$PYTHON auto_generate_images.py $CHANNEL_ARG
rm -f video/clips/*.mp4
$PYTHON generate_video_wan.py $CHANNEL_ARG
$PYTHON assemble_video.py $CHANNEL_ARG

echo "=== DONE $(date) ==="
