# inspiring-factory

Pipeline local-first para crear shorts verticales inspiradores sobre ciencia, ideas y personajes historicos.

El proyecto esta separado del pipeline `local-3090`. Este repo guarda el codigo, la configuracion y las preferencias; los renders generados quedan ignorados por git para no subir videos pesados.

## Objetivo

- Shorts de unos 60 segundos.
- Narracion en espanol con voz masculina grave.
- Estetica de dibujo realista/cinematografica.
- Subtitulos pequenos, abajo, sin tapar la imagen.
- Imagenes generadas con ComfyUI.
- Movimiento mediante WAN image-to-video en la RTX 3090.

## Estructura

- `config/channel_inspirational_science_es.json`: perfil principal en espanol para ciencia/ideas y RTX 3090.
- `config/figures_inspirational.json`: lista de personajes de ciencia.
- `config/figures_arts_ideas.json`: lista secundaria de arte e ideas.
- `generate_and_save_story.py`: crea `stories/story.json`.
- `auto_generate_images.py`: genera imagenes en ComfyUI.
- `generate_voice.py`: crea voz y subtitulos con Edge TTS.
- `generate_video_wan.py`: genera clips animados WAN desde las imagenes.
- `assemble_video.py`: monta audio, video y subtitulos.
- `run_full_pipeline.py`: ejecuta el pipeline completo.
- `render_ada_lovelace_3090_preview.py`: demo directa de Ada sin WAN final.
- `render_ada_lovelace_3090_motion.py`: demo directa de Ada con WAN.

## Requisitos

- Python 3.10+
- `ffmpeg` y `ffprobe`
- Ollama para generacion/validacion de historias
- ComfyUI en la maquina de render
- Para movimiento real: `ComfyUI-WanVideoWrapper`, `ComfyUI-KJNodes` y `ComfyUI-VideoHelperSuite`
- Modelos WAN en la 3090:
  - `Wan2_1-I2V-14B-480p_fp8_e4m3fn_scaled_KJ.safetensors`
  - `Wan2_1_VAE_bf16.safetensors`
  - `umt5-xxl-enc-bf16.safetensors`

## Instalacion

Windows:

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

Ubuntu/3090:

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Perfil Principal

Usa este perfil para el canal:

```text
config/channel_inspirational_science_es.json
```

Preferencias importantes:

- `language`: `es`
- `voice.name`: `es-ES-AlvaroNeural`
- `voice.postprocess_filter`: baja pitch y normaliza volumen
- `subtitles.font_size`: pequeno
- `subtitles.margin_v`: bajo en pantalla
- `video.use_wan_i2v`: `true`
- `video.fps`: fps de clips WAN
- `video.output_fps`: fps del render final
- `video.frames`: frames por clip WAN
- `video.steps`: pasos WAN por escena

Para un preview rapido baja `video.frames` y `video.steps`.
Para un final mas fluido sube `video.frames`, `video.fps` y `video.steps`.

## Uso

Pipeline completo:

```bash
python run_full_pipeline.py --channel config/channel_inspirational_science_es.json --figures config/figures_inspirational.json
```

Un personaje concreto:

```bash
python run_full_pipeline.py --channel config/channel_inspirational_science_es.json --figure "Ada Lovelace"
```

Demo directa de Ada con WAN:

```bash
python render_ada_lovelace_3090_motion.py
```

## Notas De Calidad

La fluidez no debe arreglarse solo interpolando despues. Para que el movimiento no vaya a tirones:

- Generar mas frames por escena en WAN.
- Usar fps mas alto en el clip base.
- Evitar estirar clips cortos para cubrir narraciones largas.
- Mantener subtitulos pequenos y abajo.

La interpolacion con `ffmpeg minterpolate` en CPU es lenta y puede crear artefactos. Es mejor generar el movimiento correcto desde WAN o usar interpolacion GPU dedicada.

## Artefactos Ignorados

Git ignora:

- `audio/`
- `stories/`
- `images/generated/`
- `video/`
- `output/`
- `renders/`
- `*.mp4`, `*.mp3`, `*.wav`, `*.srt`, `*.log`

Esto mantiene GitHub limpio con codigo y configuracion, no con renders temporales.

