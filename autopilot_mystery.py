#!/usr/bin/env python3
"""
Autopilot mystery channel — personajes misteriosos + misterios sin resolver.
Corre en despacho (192.168.1.66).
Uso: nohup python3 autopilot_mystery.py >> mystery.log 2>&1 &
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, threading, time, urllib.request
from pathlib import Path

DIR          = Path("/home/andreu/inspiring-factory")
PYTHON       = "/home/andreu/miniconda3/bin/python"
PI           = "andreu@192.168.1.60"
QUEUE_DIR    = "/home/andreu/youtube_bot/queue/mystery"
CHANNEL      = "config/channel_mystery_es.json"
STATE_FILE   = DIR / "autopilot_mystery_state.json"
STAGING_DIR  = DIR / "staging_mystery"
COMFYUI_URL  = "http://127.0.0.1:8188"
COMFYUI_BIN  = "/home/andreu/ai-tools/ComfyUI/main.py"
COMFYUI_VENV = "/home/andreu/miniconda3/envs/comfyui/bin/python"
ARCHIVE_DIR  = DIR / "publicados/mystery"

WAN_TIMEOUT_H   = 7
WAN_MAX_RETRIES = 3
QUEUE_MAX       = 5

# ── Lista de contenido ─────────────────────────────────────────────────────────
# Alternamos personajes misteriosos y misterios sin resolver para variedad

TOPICS = [
    # Interleado: personaje, misterio, personaje, misterio...
    "Kaspar Hauser",
    "El Paso Dyatlov",
    "Conde de Saint Germain",
    "El Zumbido de Taos",
    "Nicolas Flamel",
    "La Señal Wow!",
    "Fulcanelli",
    "El Sonido Bloop",
    "Rasputin",
    "El Manuscrito Voynich",
    "La Papisa Juana",
    "Proyecto MK-Ultra",
    "El Hombre de Somerton",
    "El Codigo Kryptos",
    "D.B. Cooper",
    "La Estacion UVB-76",
    "Roanoke",
    "El Faro de Flannan Isles",
    "Ettore Majorana",
    "El Experimento Filadelfia",
    "The Isdal Woman",
    "Max Headroom",
    "El Hombre de Taured",
    "Mary Celeste",
    "Anastasia Romanov",
    "Las Caras de Belmez",
    "Grigori Perelman",
    "Incidente Vela",
    "Edward Mordrake",
    "Lago Anjikuni",
    "Ambrose Bierce",
    "Skinwalker Ranch",
    "Belle Gunness",
    "Area 51",
    "H.H. Holmes",
    "La Isla Sentinel Norte",
    "Aleister Crowley",
    "El Triangulo de Bennington",
    "Jack el Destripador",
    "La Colonia Roanoke",
    "La Condesa Sangrienta",
    "Cicada 3301",
    "Paracelso",
    "El Caso Tunguska",
    "Cagliostro",
    "La Anomalia del Mar Baltico",
    "Baba Vanga",
    "El Vuelo MH370",
    "El Rey Arturo",
    "Proyecto Montauk",
    "Billy the Kid",
    "HAARP",
    "Mata Hari",
    "Las Trompetas del Cielo",
    "Howard Hughes",
    "Los Numeros Estacion",
    "Alan Turing",
    "El Caso Cash-Landrum",
    "Virginia Hall",
    "El Incidente Roswell",
    "Tycho Brahe",
    "Black Knight",
    "Michael Malloy",
    "La Zona del Silencio",
    "The Green Children of Woolpit",
    "Hinterkaifeck",
    "El Monje Negro de Pontefract",
    "El Hotel Cecil",
    "Jeanne des Anges",
    "La Casa Winchester",
    "Gilles de Rais",
    "El Bosque Aokigahara",
    "Elizabeth Bathory",
    "La Maldicion de Tutankamon",
    "El Flautista de Hamelin",
    "Las Lineas de Nazca",
    "Guy Fawkes",
    "El Triangulo de las Bermudas",
    "El Hombre Polilla",
    "La Puerta del Infierno",
    "Spring-Heeled Jack",
    "El Proyecto Blue Book",
    "El Asesino del Zodiaco",
    "El Incidente Rendlesham",
    "Black Dahlia",
    "El Caso Elisa Lam",
    "El Hombre del Gancho",
    "El Experimento Gateway",
    "El Monstruo de Flatwoods",
    "Los Hombres de Negro",
    "Ludwig II de Baviera",
    "El Caso Travis Walton",
    "Harry Houdini",
    "La Desaparicion de Flight 19",
    "Edgar Cayce",
    "Las Luces de Hessdalen",
    "Leonardo da Vinci",
    "El Incidente Kecksburg",
    "El Baron Rojo",
    "La Biblioteca Vaticana Secreta",
    "Yuri Gagarin",
    "El Caso Oakville Blobs",
    "Nostradamus",
    "La Habitacion 39",
    "La Reina de Saba",
    "El Fenomeno Shadow People",
    "El Doctor Fausto",
    "Paralisis del Sueno",
    "John Dee",
    "El Incidente Aurora",
    "Merlin",
    "El Manuscrito Rohonc",
    "Vlad Tepes",
    "La Maquina de Anticitera",
    "Caligula",
    "El Caso Lead Masks",
    "Percy Fawcett",
    "El Valle Sin Cabeza",
    "Amelia Earhart",
    "La Ciudad Perdida de Atlantis",
    "El Dorado",
    "La Isla de las Munecas",
    "Maria Antonieta",
    "El Experimento Bell",
    "Joseph Merrick",
    "La Operacion Highjump",
    "Nikola Tesla",
    "La Base Dulce",
    "Annie Chapman",
    "El Proyecto Serpo",
    "The Axeman of New Orleans",
    "El Incidente Falcon Lake",
    "Billy Milligan",
    "El Satelite Caballero Negro",
    "La Bestia de Gevaudan",
    "El Caso Phoenix Lights",
    "Miyamoto Musashi",
    "El Misterio de Oak Island",
    "El Hombre de Piltdown",
    "El Templo Submarino Yonaguni",
    "La Familia Bender",
    "La Maldicion del Diamante Hope",
    "El Fantasma de la Opera real",
    "El Caso Pollock Twins",
    "La Dama de Blanco",
    "La Mano Peluda",
    "Tupac Amaru",
    "La Frecuencia 4625",
    "El Principe de los Lirios",
    "El Incidente Flatwoods",
    "La Mujer del Triangulo",
    "La Ciudad Subterranea Derinkuyu",
    "La Isla de Pascua",
    "El Caso Devil's Kettle",
    "El Rey Mono",
    "El Proyecto Stargate",
    "Qin Shi Huang",
    "El Misterio de Coral Castle",
    "Proyecto Montauk",
    "La Carretera Clinton Road",
    "Experimento Filadelfia",
    "El Experimento Scole",
    "Dyatlov",
    "La Desaparicion del Vuelo 914",
    "Tunguska",
    "El Caso Mothman",
    "Mary Celeste",
    "El Caso Enfield",
    "Voynich",
    "El Pueblo Fantasma Centralia",
    "La Señal Wow!",
    "The Watcher",
    "El Bloop",
    "Hinterkaifeck",
    "MK-Ultra",
    "Annabelle",
    "El Monstruo del Lago Ness",
    "Robert el Muneco",
    "Mothman",
    "El Gigante de Kandahar",
    "El Triangulo de las Bermudas",
    "El Tunel de Shanghai",
    "El Caso Roswell",
    "El Proyecto Rainbow",
    "El Caso Phoenix Lights",
    "El Caso Bridgewater Triangle",
]


# ── helpers ────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [mystery] {msg}", flush=True)

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
    try:
        r = subprocess.run(
            ["ssh", PI, f"ls {QUEUE_DIR}/*.mp4 2>/dev/null | wc -l"],
            capture_output=True, text=True, timeout=15,
        )
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
            log(f"Cola Pi mystery: {n} videos — OK para generar")
            return
        log(f"Cola Pi mystery llena ({n}/{QUEUE_MAX}) — esperando...")
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
        stdout=open("/tmp/comfyui_mystery.log", "a"),
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


# ── WAN síncrono con reintentos ───────────────────────────────────────────────

def run_wan_with_retry(topic: str) -> bool:
    wan_log_path = DIR / f"mystery_{slug(topic)}.log"
    expected = n_scenes()

    for attempt in range(1, WAN_MAX_RETRIES + 1):
        existing = count_clips()
        log(f"WAN intento {attempt}/{WAN_MAX_RETRIES} — clips: {existing}/{expected}")

        if existing >= expected:
            log("Todos los clips ya existen — skip WAN")
            return True

        ensure_comfyui()
        free_vram()

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

    subprocess.run(["ssh", PI, f"mkdir -p {QUEUE_DIR}"], timeout=15)

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
        log(f"Tamaño remoto incorrecto — reintentando")
        time.sleep(30)
    else:
        log(f"ERROR: no se pudo copiar {filename} a Pi tras 3 intentos")
        return False

    meta_code = (
        "import json\n"
        f"path='{QUEUE_DIR}/meta.json'\n"
        "try:\n    meta=json.load(open(path))\nexcept:\n    meta={}\n"
        f"meta[{json.dumps(filename)}]={{'title':{json.dumps(title)},"
        f"'description':{json.dumps(description)}}}\n"
        "open(path,'w').write(json.dumps(meta,ensure_ascii=False,indent=2))\n"
        "print('meta.json OK')\n"
    )
    subprocess.run(["ssh", PI, f"python3 -c {json.dumps(meta_code)}"], timeout=30)
    return True


# ── Pre-staging ───────────────────────────────────────────────────────────────

def launch_prestage(next_topic: str):
    next_staging = STAGING_DIR / slug(next_topic)
    if (next_staging / "story.json").exists() and (next_staging / "narration.mp3").exists():
        log(f"Staging de '{next_topic}' ya existe — skip")
        return

    log(f"Prestage de '{next_topic}' en background...")

    def _run():
        env = os.environ.copy()
        env["STAGING_DIR"] = str(STAGING_DIR)
        r = subprocess.run(
            [PYTHON, "prestage.py", "--figure", next_topic, "--channel", CHANNEL],
            cwd=DIR,
            stdout=open(DIR / f"prestage_mystery_{slug(next_topic)}.log", "w"),
            stderr=subprocess.STDOUT,
            timeout=600,
            env=env,
        )
        log(f"Prestage '{next_topic}' terminó (rc={r.returncode})")

    threading.Thread(target=_run, daemon=True).start()


# ── Pipeline de un tema ────────────────────────────────────────────────────────

def run_topic(topic: str, next_topic: str | None) -> bool:
    log(f"=== Iniciando: {topic} ===")
    os.chdir(DIR)

    state = load_state()
    state["current"] = topic
    save_state(state)

    clips_count = count_clips()
    images = list((DIR / "images/generated").glob("*.png"))
    has_story = (DIR / "stories/story.json").exists()

    if clips_count == 0 and not images:
        log("Limpiando artefactos de sesión anterior...")
        for p in ["audio/narration.mp3", "audio/subtitles.srt",
                  "output/final_short.mp4", "stories/story.json"]:
            (DIR / p).unlink(missing_ok=True)

    # Staging
    staging = STAGING_DIR / slug(topic)
    staged_story = staging / "story.json"
    staged_narration = staging / "narration.mp3"
    staged_srt = staging / "subtitles.srt"
    use_staging = staged_story.exists() and staged_narration.exists()

    if use_staging:
        log(f"Usando staging para {topic}")
        (DIR / "stories").mkdir(exist_ok=True)
        (DIR / "audio").mkdir(exist_ok=True)
        shutil.copy2(staged_story, DIR / "stories/story.json")
        shutil.copy2(staged_narration, DIR / "audio/narration.mp3")
        if staged_srt.exists():
            shutil.copy2(staged_srt, DIR / "audio/subtitles.srt")
    elif not has_story:
        subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
        time.sleep(3)
        subprocess.Popen(["ollama", "serve"],
                         stdout=open("/tmp/ollama_mystery.log", "w"),
                         stderr=subprocess.STDOUT)
        time.sleep(8)
        for script, extra_args in [
            ("generate_and_save_story.py", ["--figure", topic]),
            ("generate_voice.py", []),
        ]:
            r = subprocess.run(
                [PYTHON, script, "--channel", CHANNEL] + extra_args,
                capture_output=True, text=True, cwd=DIR,
            )
            if r.returncode != 0:
                log(f"ERROR en {script}:\n{r.stderr[-2000:]}")
                return False
            print(r.stdout[-500:])

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

    if next_topic:
        launch_prestage(next_topic)

    if not run_wan_with_retry(topic):
        log(f"WAN falló tras {WAN_MAX_RETRIES} intentos — saltando")
        return False

    time.sleep(15)

    log("Ensamblando vídeo final...")
    r = subprocess.run(
        [PYTHON, "assemble_video.py", "--channel", CHANNEL],
        capture_output=True, text=True, cwd=DIR, timeout=600,
    )
    if r.returncode != 0:
        log(f"ERROR assemble:\n{r.stderr[-2000:]}")
        return False

    final_mp4 = DIR / "output/final_short.mp4"
    if not final_mp4.exists() or final_mp4.stat().st_size < 1_000_000:
        log("ERROR: final_short.mp4 no existe o es demasiado pequeño")
        return False

    filename = "mystery_" + slug(topic) + ".mp4"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final_mp4, ARCHIVE_DIR / filename)
    log(f"Archivado: publicados/mystery/{filename}")

    try:
        story = json.loads((DIR / "stories/story.json").read_text())
        title = story.get("title", topic)
        hook = story.get("hook", "")
        ending = story.get("ending", "")
    except Exception:
        title = topic
        hook = ""
        ending = ""
    description = f"{hook}\n\n{ending}\n\n#shorts #misterio #historia #misteriosinresolver"

    if not copy_to_pi(final_mp4, filename, title, description):
        return False

    log("Limpiando clips e imágenes...")
    subprocess.run(f"rm -f {DIR}/video/clips/*.mp4 {DIR}/images/generated/*.png", shell=True)
    if use_staging and staging.exists():
        shutil.rmtree(staging, ignore_errors=True)

    log(f"=== {topic} completado ===")
    return True


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    log("Autopilot mystery arrancando")
    STAGING_DIR.mkdir(exist_ok=True)

    state = load_state()
    done_set = set(state.get("done", []))

    for i, topic in enumerate(TOPICS):
        if topic in done_set:
            continue

        remaining_after = [t for t in TOPICS[i+1:] if t not in done_set]
        next_topic = remaining_after[0] if remaining_after else None

        wait_for_queue_space()

        success = run_topic(topic, next_topic)

        state = load_state()
        done_set = set(state.get("done", []))

        if success:
            done_set.add(topic)
            state["done"] = list(done_set)
            state["current"] = None
            save_state(state)
            log(f"Estado guardado. Pausa 60s.")
            time.sleep(60)
        else:
            log(f"FALLO en '{topic}' — saltando al siguiente")
            state["current"] = None
            save_state(state)
            time.sleep(30)

    log("=== Todos los temas completados ===")


if __name__ == "__main__":
    main()
