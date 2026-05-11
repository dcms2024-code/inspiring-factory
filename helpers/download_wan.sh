#!/bin/bash
#
# Downloads WAN I2V model files for ComfyUI (Kijai repos on Hugging Face).
#
# Usage:
#   export HF_TOKEN=hf_xxx
#   export COMFY_MODELS_BASE=/path/to/ComfyUI/models
#   ./helpers/download_wan.sh
#
# Notes:
# - Files are very large (T5 ~9.5GB, WAN model ~14GB).
# - This script is intended for Linux.

set -euo pipefail

if [ -z "${HF_TOKEN:-}" ] && [ -f "${HOME}/.hf_token" ]; then
  HF_TOKEN="$(cat "${HOME}/.hf_token")"
fi

if [ -z "${HF_TOKEN:-}" ]; then
  echo "ERROR: HF_TOKEN is not set. Export HF_TOKEN or create ~/.hf_token"
  exit 1
fi

COMFY_MODELS_BASE="${COMFY_MODELS_BASE:-}"
if [ -z "$COMFY_MODELS_BASE" ]; then
  echo "ERROR: COMFY_MODELS_BASE is not set (e.g. /home/user/ComfyUI/models)"
  exit 1
fi

HF="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main"
HF_FP8="https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main"

download() {
  local url="$1" dest="$2" name="$3"
  mkdir -p "$(dirname "$dest")"
  local size
  size="$(stat -c%s "$dest" 2>/dev/null || echo 0)"
  if [ "$size" -gt "1000000" ]; then
    echo "$name exists ($(stat -c%s "$dest") bytes), skipping."
    return 0
  fi
  echo "Downloading $name ..."
  wget -c --retry-connrefused --tries=5 --waitretry=5 -q --show-progress \
    --header="Authorization: Bearer $HF_TOKEN" \
    -O "$dest" "$url"
  echo "$name OK - $(stat -c%s "$dest") bytes"
}

download "$HF/Wan2_1_VAE_bf16.safetensors" \
  "$COMFY_MODELS_BASE/vae/Wan2_1_VAE_bf16.safetensors" "VAE (bf16)"

download "$HF/open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors" \
  "$COMFY_MODELS_BASE/clip_vision/open-clip-vit-huge_fp16.safetensors" "CLIP vision"

download "$HF/umt5-xxl-enc-bf16.safetensors" \
  "$COMFY_MODELS_BASE/text_encoders/umt5-xxl-enc-bf16.safetensors" "T5 encoder"

download "$HF_FP8/I2V/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors" \
  "$COMFY_MODELS_BASE/diffusion_models/Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors" "WAN I2V 14B fp8"

echo "DONE: WAN models downloaded."
