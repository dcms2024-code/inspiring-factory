#!/usr/bin/env python3
"""
Autopilot inspiring-factory — versión robusta.
Uso: nohup python3 autopilot_inspiring.py >> autopilot.log 2>&1 &

Mejoras vs versión anterior:
- WAN corre SÍNCRONAMENTE (subprocess.run, no Popen) — no más timeouts falsos
- 3 reintentos WAN sin borrar clips existentes entre intentos
- Limpieza DESPUÉS de archivar+copiar, nunca antes
- rsync con verificación de tamaño en lugar de scp
- Fallos saltan al siguiente personaje en vez de sys.exit(1)
- Detección de ComfyUI caído + reinicio automático
- Pre-staging corre en thread daemon paralelo a WAN síncrono
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, threading, time, urllib.request
from pathlib import Path

DIR          = Path("/home/andreu/inspiring-factory")
PYTHON       = "/home/andreu/miniconda3/bin/python"
PI           = "andreu@192.168.1.60"
QUEUE_DIR    = "/home/andreu/youtube_bot/queue/inspiring-factory"
CHANNEL      = "config/channel_inspirational_science_es.json"
STATE_FILE   = DIR / "autopilot_state.json"
STAGING_DIR  = DIR / "staging"
COMFYUI_URL  = "http://127.0.0.1:8188"
COMFYUI_BIN  = "/home/andreu/ai-tools/ComfyUI/main.py"
COMFYUI_VENV = "/home/andreu/miniconda3/envs/comfyui/bin/python"

WAN_TIMEOUT_H  = 7      # 9 clips × ~45min worst case = 6.75h
WAN_MAX_RETRIES = 3
QUEUE_MAX      = 5      # no generar si Pi tiene ≥5 videos en cola

FIGURES = [
    "Ada Lovelace",
    "Alan Turing",
    "Grace Hopper",
    "Katherine Johnson",
    "Margaret Hamilton",
    "Hedy Lamarr",
    "Tim Berners-Lee",
    "Vint Cerf",
    "Dennis Ritchie",
    "Ken Thompson",
    "Linus Torvalds",
    "Richard Stallman",
    "Guido van Rossum",
    "Donald Knuth",
    "Radia Perlman",
    "Barbara Liskov",
    "Sophie Wilson",
    "Douglas Engelbart",
    "Susan Kare",
    "Steve Jobs",
    "Steve Wozniak",
    "Bill Gates",
    "Paul Allen",
    "Nikola Tesla",
    "Thomas Edison",
    "Alexander Graham Bell",
    "Guglielmo Marconi",
    "Johannes Gutenberg",
    "Marie Curie",
    "Pierre Curie",
    "Albert Einstein",
    "Isaac Newton",
    "Galileo Galilei",
    "Nicolas Copernicus",
    "Johannes Kepler",
    "Rosalind Franklin",
    "James Watson",
    "Francis Crick",
    "Jennifer Doudna",
    "Emmanuelle Charpentier",
    "Katalin Kariko",
    "Drew Weissman",
    "Jonas Salk",
    "Alexander Fleming",
    "Florence Nightingale",
    "Ignaz Semmelweis",
    "Edward Jenner",
    "Louis Pasteur",
    "Jane Goodall",
    "Rachel Carson",
    "Wangari Maathai",
    "Sylvia Earle",
    "Jacques Cousteau",
    "Amelia Earhart",
    "Wright Brothers",
    "Yuri Gagarin",
    "Valentina Tereshkova",
    "Mae Jemison",
    "Sally Ride",
    "Mary Jackson",
    "Dorothy Vaughan",
    "Chien-Shiung Wu",
    "Lise Meitner",
    "Vera Rubin",
    "Cecilia Payne-Gaposchkin",
    "Henrietta Leavitt",
    "Subrahmanyan Chandrasekhar",
    "Hypatia of Alexandria",
    "Leonardo da Vinci",
    "Mary Shelley",
    "George Orwell",
    "Hannah Arendt",
    "Simone de Beauvoir",
    "Virginia Woolf",
    "Frida Kahlo",
    "Pablo Picasso",
    "Vincent van Gogh",
    "Ludwig van Beethoven",
    "Wolfgang Amadeus Mozart",
    "Bob Dylan",
    "Nina Simone",
    "Maya Angelou",
    "Malala Yousafzai",
    "Nelson Mandela",
    "Mahatma Gandhi",
    "Rosa Parks",
    "Martin Luther King Jr",
    "Claudette Colvin",
    "Harriet Tubman",
    "Irena Sendler",
    "Oskar Schindler",
    "Chiune Sugihara",
    "Nicholas Winton",
    "Temple Grandin",
    "Muhammad Yunus",
    "Norman Borlaug",
    "Boyan Slat",
    "Robert Kahn",
    "Claude Shannon",
]


# ── helpers ────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [autopilot] {msg}", flush=True)

def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"done": [], "current": None}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def clips_dir() -> Path:
    return DIR / "video/clips"

def count_clips() -> int:
    return len(list(clips_dir().glob("clip_*.mp4")))

def n_scenes() -> int:
    try:
        cfg = json.loads((DIR / CHANNEL).read_text())
        return int(cfg.get("scenes_count", 9))
    except Exception:
        return 9

def queue_size() -> int:
    r = subprocess.run(
        ["ssh", PI, f"ls {QUEUE_DIR}/*.mp4 2>/dev/null | wc -l"],
        capture_output=True, text=True, timeout=15
    )
    try:
        return int(r.stdout.strip())
    except Exception:
        return 0

def wait_for_queue_space():
    while True:
        try:
            n = queue_size()
        except Exception:
            n = 0
        if n < QUEUE_MAX:
            log(f"Cola Pi: {n} videos — OK para generar")
            return
        log(f"Cola Pi llena ({n}/{QUEUE_MAX}) — esperando...")
        time.sleep(1800)


# ── ComfyUI ───────────────────────────────────────────────────────────────────

_comfyui_proc = None

def comfyui_running() -> bool:
    try:
        urllib.request.urlopen(f"{COMFYUI_URL}/system_stats", timeout=5)
        return True
    except Exception:
        return False

def ensure_comfyui():
    global _comfyui_proc
    if comfyui_running():
        return
    log("ComfyUI no responde — arrancando...")
    python_bin = COMFYUI_VENV if Path(COMFYUI_VENV).exists() else PYTHON
    _comfyui_proc = subprocess.Popen(
        [python_bin, COMFYUI_BIN, "--listen", "0.0.0.0", "--port", "8188",
         "--disable-auto-launch"],
        stdout=open("/tmp/comfyui.log", "a"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(60):
        time.sleep(5)
        if comfyui_running():
            log("ComfyUI listo")
            return
    raise RuntimeError("ComfyUI no arrancó en 5 minutos")

def free_vram():
    try:
        req = urllib.request.Request(
            f"{COMFYUI_URL}/free",
            data=b'{"unload_models":true,"free_memory":true}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        log("VRAM liberada")
        time.sleep(60)
    except Exception as e:
        log(f"ComfyUI /free: {e}")


# ── WAN (síncrono con reintentos) ─────────────────────────────────────────────

def run_wan_with_retry(figure: str) -> bool:
    wan_log_path = DIR / f"{slug(figure)}.log"
    expected = n_scenes()

    for attempt in range(1, WAN_MAX_RETRIES + 1):
        existing = count_clips()
        log(f"WAN intento {attempt}/{WAN_MAX_RETRIES} — clips: {existing}/{expected}")

        if existing >= expected:
            log("Todos los clips ya existen — skip WAN")
            return True

        subprocess.run(["pkill", "-f", "ComfyUI/main.py"], capture_output=True)
        time.sleep(5)
        ensure_comfyui()
        log("VRAM liberada")

        try:
            with open(wan_log_path, "a") as wl:
                r = subprocess.run(
                    [PYTHON, "generate_video_wan.py", "--channel", CHANNEL],
                    stdout=wl, stderr=wl,
                    timeout=WAN_TIMEOUT_H * 3600,
                    cwd=DIR,
                )
        except subprocess.TimeoutExpired:
            log(f"WAN timeout ({WAN_TIMEOUT_H}h) en intento {attempt}")
            r = None

        done = count_clips()
        log(f"WAN intento {attempt} terminó — clips: {done}/{expected}")

        if done >= expected:
            return True

        if attempt < WAN_MAX_RETRIES:
            log(f"WAN incompleto — reintentando en 60s (clips actuales: {done})")
            time.sleep(60)

    return False


# ── Copia a Pi (rsync + verificación) ────────────────────────────────────────

def copy_to_pi(local_path: Path, filename: str, title: str, description: str) -> bool:
    local_size = local_path.stat().st_size
    remote = f"{PI}:{QUEUE_DIR}/{filename}"

    for attempt in range(1, 4):
        log(f"rsync a Pi intento {attempt}/3 — {filename}")
        r = subprocess.run(
            ["rsync", "-avP", "--inplace", str(local_path), remote],
            timeout=600,
        )
        if r.returncode != 0:
            log(f"rsync falló (rc={r.returncode})")
            time.sleep(30)
            continue

        # Verificar tamaño remoto
        check = subprocess.run(
            ["ssh", PI, f"stat -c%s {QUEUE_DIR}/{filename}"],
            capture_output=True, text=True, timeout=15,
        )
        try:
            remote_size = int(check.stdout.strip())
        except Exception:
            remote_size = 0

        if remote_size >= local_size * 0.99:
            log(f"Copia OK ({remote_size // 1024 // 1024} MB en Pi)")
            break
        log(f"Tamaño remoto incorrecto ({remote_size} vs {local_size}) — reintentando")
        time.sleep(30)
    else:
        log(f"ERROR: no se pudo copiar {filename} a Pi tras 3 intentos")
        return False

    # Actualizar meta.json en Pi
    meta_code = (
        "import json\n"
        f"path='{QUEUE_DIR}/meta.json'\n"
        "try:\n    meta=json.load(open(path))\nexcept:\n    meta={}\n"
        f"meta[{json.dumps(filename)}]={{'title':{json.dumps(title)},"
        f"'description':{json.dumps(description)}}}\n"
        "open(path,'w').write(json.dumps(meta,ensure_ascii=False,indent=2))\n"
        "print('meta.json OK')\n"
    )
    subprocess.run(["ssh", PI, "python3"], input=meta_code.encode(), timeout=30)
    return True


# ── Pre-staging (paralelo a WAN) ──────────────────────────────────────────────

def launch_prestage(next_figure: str):
    next_staging = STAGING_DIR / slug(next_figure)
    if (next_staging / "story.json").exists() and (next_staging / "narration.mp3").exists():
        log(f"Staging de '{next_figure}' ya existe — skip prestage")
        return

    log(f"Prestage de '{next_figure}' en background...")

    def _run():
        r = subprocess.run(
            [PYTHON, "prestage.py", "--figure", next_figure, "--channel", CHANNEL],
            cwd=DIR,
            stdout=open(DIR / f"prestage_{slug(next_figure)}.log", "w"),
            stderr=subprocess.STDOUT,
            timeout=600,
        )
        log(f"Prestage '{next_figure}' terminó (rc={r.returncode})")

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ── Pipeline de un personaje ───────────────────────────────────────────────────

def run_figure(figure: str, next_figure: str | None) -> bool:
    log(f"=== Iniciando: {figure} ===")
    os.chdir(DIR)

    state_file = STATE_FILE
    state = load_state()
    state["current"] = figure
    save_state(state)

    clips_count = count_clips()
    images = list((DIR / "images/generated").glob("*.png"))
    has_story = (DIR / "stories/story.json").exists()

    # Solo limpiar si estamos desde cero (no hay clips ni imágenes)
    if clips_count == 0 and not images:
        log("Limpiando artefactos de sesión anterior...")
        for p in ["audio/narration.mp3", "audio/subtitles.srt",
                  "output/final_short.mp4", "stories/story.json"]:
            (DIR / p).unlink(missing_ok=True)

    # Usar staging si está listo
    staging = STAGING_DIR / slug(figure)
    staged_story = staging / "story.json"
    staged_narration = staging / "narration.mp3"
    staged_srt = staging / "subtitles.srt"
    use_staging = staged_story.exists() and staged_narration.exists()

    if use_staging:
        log(f"Usando staging para historia+voz de {figure}")
        (DIR / "stories").mkdir(exist_ok=True)
        (DIR / "audio").mkdir(exist_ok=True)
        shutil.copy2(staged_story, DIR / "stories/story.json")
        shutil.copy2(staged_narration, DIR / "audio/narration.mp3")
        if staged_srt.exists():
            shutil.copy2(staged_srt, DIR / "audio/subtitles.srt")
    elif not has_story:
        # Generar historia + voz
        subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
        time.sleep(3)
        subprocess.Popen(["ollama", "serve"],
                         stdout=open("/tmp/ollama.log", "w"), stderr=subprocess.STDOUT)
        time.sleep(8)
        for script, extra_args in [
            ("generate_and_save_story.py", ["--figure", figure]),
            ("generate_voice.py", []),
        ]:
            r = subprocess.run(
                [PYTHON, script, "--channel", CHANNEL] + extra_args,
                capture_output=True, text=True, cwd=DIR,
            )
            if r.returncode != 0:
                log(f"ERROR en {script}:\n{r.stderr[-2000:]}")
                return False
            print(r.stdout[-1000:])

    # Generar imágenes (ComfyUI SDXL) — skip si ya existen
    if not images:
        ensure_comfyui()
        r = subprocess.run(
            [PYTHON, "auto_generate_images.py", "--channel", CHANNEL],
            capture_output=True, text=True, cwd=DIR, timeout=1800,
        )
        if r.returncode != 0:
            log(f"ERROR en auto_generate_images:\n{r.stderr[-2000:]}")
            return False
        print(r.stdout[-500:])
    else:
        log(f"{len(images)} imágenes ya existen — skip SDXL")

    # Pre-staging del siguiente personaje arranca aquí (paralelo a WAN)
    if next_figure:
        launch_prestage(next_figure)

    # WAN síncrono con reintentos
    if not run_wan_with_retry(figure):
        log(f"WAN falló tras {WAN_MAX_RETRIES} intentos — saltando a siguiente")
        return False

    time.sleep(15)

    # Ensamblar
    log("Ensamblando vídeo final...")
    r = subprocess.run(
        [PYTHON, "assemble_video.py", "--channel", CHANNEL],
        capture_output=True, text=True, cwd=DIR, timeout=600,
    )
    if r.returncode != 0:
        log(f"ERROR assemble:\n{r.stderr[-2000:]}")
        return False
    print(r.stdout[-500:])

    final_mp4 = DIR / "output/final_short.mp4"
    if not final_mp4.exists() or final_mp4.stat().st_size < 1_000_000:
        log("ERROR: final_short.mp4 no existe o es demasiado pequeño")
        return False

    # Archivar en local
    filename = slug(figure) + "_inspiring.mp4"
    archive = DIR / "publicados"
    archive.mkdir(exist_ok=True)
    archived = archive / filename
    shutil.copy2(final_mp4, archived)
    log(f"Archivado: publicados/{filename}")

    # Título y descripción
    try:
        story = json.loads((DIR / "stories/story.json").read_text())
        title = story.get("title", figure)
        hook = story.get("hook", "")
        ending = story.get("ending", "")
    except Exception:
        title = figure
        hook = ""
        ending = ""
    description = f"{hook}\n\n{ending}\n\n#shorts #historia #ciencia #inspiracion"

    # Copiar a Pi (rsync + verificación)
    if not copy_to_pi(final_mp4, filename, title, description):
        return False

    # Limpiar clips e imágenes SOLO si copia fue OK
    log("Limpiando clips e imágenes (copia verificada)...")
    subprocess.run(f"rm -f {DIR}/video/clips/*.mp4 {DIR}/images/generated/*.png", shell=True)
    if use_staging and staging.exists():
        shutil.rmtree(staging, ignore_errors=True)

    log(f"=== {figure} completado ===")
    return True


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    log("Autopilot arrancando")
    state = load_state()
    done_set = set(state.get("done", []))

    for i, figure in enumerate(FIGURES):
        if figure in done_set:
            continue

        remaining_after = [f for f in FIGURES[i+1:] if f not in done_set]
        next_figure = remaining_after[0] if remaining_after else None

        wait_for_queue_space()

        if (DIR / "STOP").exists():
            log("Fichero STOP detectado — saliendo limpiamente.")
            break

        success = run_figure(figure, next_figure)

        state = load_state()
        done_set = set(state.get("done", []))

        if success:
            done_set.add(figure)
            state["done"] = list(done_set)
            state["current"] = None
            save_state(state)
            log(f"Estado guardado. Pausa 60s antes del siguiente.")
            time.sleep(60)
        else:
            log(f"FALLO en '{figure}' — guardando estado y saltando al siguiente")
            state["current"] = None
            save_state(state)
            time.sleep(30)

    log("=== Todos los personajes completados ===")


if __name__ == "__main__":
    main()
