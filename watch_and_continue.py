#!/usr/bin/env python3
"""
Watcher: espera clip_09, ensambla, copia a Pi, arranca siguiente figura.
Uso: nohup python3 watch_and_continue.py > watch.log 2>&1 &
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time
from pathlib import Path

DIR = Path("/home/andreu/inspiring-factory")
PYTHON = "/home/andreu/miniconda3/bin/python"
PI = "andreu@192.168.1.60"
QUEUE_DIR = "/home/andreu/youtube_bot/queue/inspiring-factory"
CHANNEL = "config/channel_inspirational_science_es.json"
NEXT_FIGURE = "Katherine Johnson"

os.chdir(DIR)


def log(msg):
    print(f"[watch] {msg}", flush=True)


def wait_for_clip09(timeout_hours=3):
    clip = DIR / "video/clips/clip_09.mp4"
    log("Esperando clip_09.mp4...")
    deadline = time.time() + timeout_hours * 3600
    while time.time() < deadline:
        if clip.exists() and clip.stat().st_size > 100_000:
            log(f"clip_09.mp4 encontrado ({clip.stat().st_size // 1024} KB)")
            return True
        time.sleep(30)
    log("TIMEOUT esperando clip_09")
    return False


def assemble():
    log("Ensamblando video final...")
    r = subprocess.run(
        [PYTHON, "assemble_video.py", "--channel", CHANNEL],
        capture_output=True, text=True
    )
    print(r.stdout)
    if r.returncode != 0:
        log(f"ERROR assemble: {r.stderr}")
        sys.exit(1)
    log("Ensamblado OK")


def archive_locally(filename):
    archive = DIR / "publicados"
    archive.mkdir(exist_ok=True)
    dest = archive / filename
    import shutil
    shutil.copy2("output/final_short.mp4", dest)
    log(f"Archivado en 3090: publicados/{filename}")


def push_to_pi():
    story = json.load(open("stories/story.json"))
    name = story["figure"]["name"]
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    filename = slug + "_inspiring.mp4"
    title = story.get("title", name)
    hook = story.get("hook", "")
    ending = story.get("ending", "")
    description = f"{hook}\n\n{ending}\n\n#shorts #historia #ciencia #inspiracion"

    log(f"Copiando {filename} a Pi...")
    subprocess.run(
        ["scp", "output/final_short.mp4", f"{PI}:{QUEUE_DIR}/{filename}"],
        check=True
    )

    meta_script = f"""
import json
path = "{QUEUE_DIR}/meta.json"
try:
    meta = json.load(open(path))
except:
    meta = {{}}
meta["{filename}"] = {{"title": {json.dumps(title)}, "description": {json.dumps(description)}}}
open(path, "w").write(json.dumps(meta, ensure_ascii=False, indent=2))
print("meta.json OK")
"""
    subprocess.run(["ssh", PI, f"python3 -c '{meta_script}'"], check=True)
    log(f"OK: {filename} en cola Pi")


def run_next_figure():
    log(f"Limpiando y arrancando: {NEXT_FIGURE}")
    for f in ["images/generated/*.png", "video/clips/*.mp4", "output/final_short.mp4"]:
        subprocess.run(f"rm -f {DIR}/{f}", shell=True)
    subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
    time.sleep(2)
    subprocess.Popen(["ollama", "serve"], stdout=open("/tmp/ollama.log", "w"), stderr=subprocess.STDOUT)
    time.sleep(5)

    log(f"Generando historia para {NEXT_FIGURE}...")
    subprocess.run([PYTHON, "generate_and_save_story.py", "--channel", CHANNEL,
                    "--figure", NEXT_FIGURE], check=True)
    subprocess.run([PYTHON, "generate_voice.py", "--channel", CHANNEL], check=True)
    subprocess.run([PYTHON, "auto_generate_images.py", "--channel", CHANNEL], check=True)
    log("Lanzando WAN para Katherine Johnson (background)...")
    log_file = open(DIR / "katherine_johnson.log", "w")
    log_file.write(f"[pipeline] Iniciando Katherine Johnson\n")
    log_file.flush()
    subprocess.Popen(
        [PYTHON, "generate_video_wan.py", "--channel", CHANNEL],
        stdout=log_file, stderr=log_file
    )
    log("Katherine Johnson WAN en marcha. Este watcher termina.")


if __name__ == "__main__":
    if not wait_for_clip09():
        sys.exit(1)
    time.sleep(10)  # dar margen a que el archivo se cierre bien
    assemble()
    # Obtener filename antes de push_to_pi para archivar
    story = json.load(open("stories/story.json"))
    name = story["figure"]["name"]
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    filename = slug + "_inspiring.mp4"
    archive_locally(filename)
    push_to_pi()
    run_next_figure()
