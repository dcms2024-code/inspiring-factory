# Inspiring Factory — Setup & Estado

## Máquinas
| Máquina | IP local | Tailscale | Rol |
|---------|----------|-----------|-----|
| enpc (local 3090) | 192.168.1.107 | — | Inspiring-factory autopilot |
| despacho (ms-7c02) | 192.168.1.66 | 100.108.14.124 | Mystery autopilot |
| Pi (Raspberry Pi) | 192.168.1.60 | 100.106.161.14 | Publisher YouTube/Instagram |

SSH pass todas: `2611`, user: `andreu`

## Canales YouTube
- **Inspiring Factory** — cuenta principal (dcms2024@gmail.com)
  - Playlist: `PLcp9YbWGEoaABkQWl9mvwb1fOOFXVF-Fv`
  - Publisher Pi: `queue_publisher_inspiring.py` — cron 5AM diario
- **Misterios al Día** — segunda cuenta (andreualonsotorrents@gmail.com)
  - Playlist: `PLzQeAntwV5QiZA44uylCUJ5pA_wCJZtkV`
  - Publisher Pi: `queue_publisher_mystery.py` — cron 17:00 diario
  - Google Cloud proyecto: `youtube-bot-496219`

## Repos GitHub (dcms2024-code)
- `inspiring-factory` — pipeline principal (scripts, configs, autopilots)
- `youtube` — Pi publisher scripts

## Pipeline inspiring-factory
1. **Historia**: Ollama `qwen2.5:14b` → `generate_and_save_story.py`
2. **Voz**: EdgeTTS `es-ES-AlvaroNeural` → `generate_voice.py`
3. **Imágenes**: ComfyUI + `juggernaut.safetensors` (768×1344) → `generate_images_comfy.py`
4. **Animación**: WAN I2V 14B fp8 en 3090 (~25-35 min/clip × 9 clips) → `generate_video_wan.py`
5. **Montaje**: ffmpeg → `assemble_video.py`
6. **Cola Pi**: SSH copia mp4 + actualiza `meta.json`
7. **Publicación**: Pi publisher → YouTube + Instagram

## Autopilots
```bash
# Inspiring (enpc)
cd /home/andreu/inspiring-factory
nohup python3 autopilot_inspiring.py >> autopilot.log 2>&1 &
tail -f autopilot.log

# Mystery (despacho)
cd /home/andreu/inspiring-factory
nohup python3 autopilot_mystery.py >> mystery.log 2>&1 &
tail -f mystery.log
```

## Configuración local despacho (NO commitear)
```python
# autopilot_inspiring.py y autopilot_mystery.py en despacho:
PI = "andreu@100.106.161.14"          # Tailscale Pi
# config/channel_inspirational_science_es.json:
# comfy_url: http://localhost:8188
```

## ComfyUI
- Python: `/home/andreu/miniconda3/envs/comfyui/bin/python` (conda env, Python 3.10)
- Start: `bash /home/andreu/start_comfyui.sh`
- Log: `/home/andreu/comfyui.log`

## Sync Windows
- Script: `windows/sync_publicados.ps1` (en este repo)
- Copiar a: `C:\Users\andre\Documents\YouTube\sync_publicados.ps1`
- Destinos: `E:\INSPIRING PUBLICADOS\` y `E:\MISTERIOS PUBLICADOS\`
- Tarea Windows: `SyncPublicadosInspiring` — 6AM diario
- Descarga mp4 nuevos del 3090 y los borra del servidor

## Estado personajes inspiring (2026-05-13)
- ✅ Tesla, Ada, Alan Turing, Grace Hopper, Katherine Johnson, Margaret Hamilton, Hedy Lamarr
- 🔄 Tim Berners-Lee (#7) — enpc, en curso
- 🔄 Vint Cerf (#8) — despacho, en curso (último inspiring en despacho)
- ⏳ Robert Kahn (#9) en adelante — enpc solo

## Tokens OAuth
- Inspiring/principal: `token.json` en Pi `/home/andreu/youtube_bot/`
- Mystery/segunda cuenta: `token_mystery.json` en Pi `/home/andreu/youtube_bot/`
- Para regenerar token mystery: `auth_mystery.py` en `C:\Users\andre\Documents\`
