#!/bin/bash
#
# Minimal ComfyUI launcher (Linux).
# Adjust COMFYUI_DIR and python/venv activation to your setup.

set -euo pipefail

COMFYUI_DIR="${COMFYUI_DIR:-}"
if [ -z "$COMFYUI_DIR" ]; then
  echo "ERROR: set COMFYUI_DIR to your ComfyUI folder"
  exit 1
fi

cd "$COMFYUI_DIR"
nohup python main.py --listen 0.0.0.0 --port 8188 > comfyui.log 2>&1 &
echo "ComfyUI PID: $!"
echo "Log: $COMFYUI_DIR/comfyui.log"
echo "URL: http://127.0.0.1:8188"
