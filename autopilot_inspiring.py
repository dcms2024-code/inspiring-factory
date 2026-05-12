#!/usr/bin/env python3
"""
Autopilot inspiring-factory: genera un personaje tras otro sin intervención manual.
Uso: nohup python3 autopilot_inspiring.py >> autopilot.log 2>&1 &
"""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

DIR = Path("/home/andreu/inspiring-factory")
PYTHON = "/home/andreu/miniconda3/bin/python"
PI = "andreu@192.168.1.60"
QUEUE_DIR = "/home/andreu/youtube_bot/queue/inspiring-factory"
CHANNEL = "config/channel_inspirational_science_es.json"
STATE_FILE = DIR / "autopilot_state.json"

FIGURES = [
    "Ada Lovelace",        # 1 ✓ publicada
    "Alan Turing",         # 2 ✓ en cola Pi
    "Grace Hopper",        # 3 ✓ en cola Pi
    "Katherine Johnson",   # 4 ← en curso
    "Margaret Hamilton",
    "Hedy Lamarr",
    "Tim Berners-Lee",
    "Vint Cerf",
    "Robert Kahn",
    "Claude Shannon",
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
    "Nikola Tesla",        # 26 ✓ publicado
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
]

DONE = {"Nikola Tesla", "Ada Lovelace", "Alan Turing", "Grace Hopper"}


def log(msg):
    print(f"[autopilot] {msg}", flush=True)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"done": list(DONE), "current": None}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def wait_for_clip09(timeout_hours=5):
    clip = DIR / "video/clips/clip_09.mp4"
    log("Esperando clip_09.mp4...")
    deadline = time.time() + timeout_hours * 3600
    while time.time() < deadline:
        if clip.exists() and clip.stat().st_size > 100_000:
            log(f"clip_09 listo ({clip.stat().st_size // 1024} KB)")
            return True
        time.sleep(60)
    return False


def run_pipeline(figure):
    log(f"=== Iniciando: {figure} ===")
    os.chdir(DIR)

    # Limpiar
    for pattern in ["images/generated/*.png", "video/clips/*.mp4",
                     "audio/*", "output/final_short.mp4"]:
        subprocess.run(f"rm -f {DIR}/{pattern}", shell=True)

    # Ollama
    subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
    time.sleep(3)
    subprocess.Popen(["ollama", "serve"],
                     stdout=open("/tmp/ollama.log", "w"), stderr=subprocess.STDOUT)
    time.sleep(8)

    # Historia + voz + imágenes
    for script in ["generate_and_save_story.py", "generate_voice.py", "auto_generate_images.py"]:
        r = subprocess.run([PYTHON, script, "--channel", CHANNEL,
                            "--figure", figure] if script == "generate_and_save_story.py"
                           else [PYTHON, script, "--channel", CHANNEL],
                           capture_output=True, text=True)
        print(r.stdout)
        if r.returncode != 0:
            log(f"ERROR en {script}: {r.stderr}")
            return False

    # WAN (background)
    log("Lanzando WAN...")
    wan_log = open(DIR / f"{slug(figure)}.log", "a")
    subprocess.Popen([PYTHON, "generate_video_wan.py", "--channel", CHANNEL],
                     stdout=wan_log, stderr=wan_log)

    # Esperar clip_09
    if not wait_for_clip09():
        log("TIMEOUT en WAN")
        return False

    time.sleep(15)  # margen para que el archivo se cierre

    # Ensamblar
    log("Ensamblando...")
    r = subprocess.run([PYTHON, "assemble_video.py", "--channel", CHANNEL],
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        log(f"ERROR assemble: {r.stderr}")
        return False

    # Archivar en 3090
    filename = slug(figure) + "_inspiring.mp4"
    archive = DIR / "publicados"
    archive.mkdir(exist_ok=True)
    shutil.copy2("output/final_short.mp4", archive / filename)
    log(f"Archivado: publicados/{filename}")

    # Copiar a Pi
    story = json.load(open("stories/story.json"))
    title = story.get("title", figure)
    hook = story.get("hook", "")
    ending = story.get("ending", "")
    description = f"{hook}\n\n{ending}\n\n#shorts #historia #ciencia #inspiracion"

    log(f"Copiando {filename} a Pi...")
    r = subprocess.run(["scp", "output/final_short.mp4", f"{PI}:{QUEUE_DIR}/{filename}"])
    if r.returncode != 0:
        log("ERROR copiando a Pi")
        return False

    meta_update = (
        f"import json\n"
        f"path='{QUEUE_DIR}/meta.json'\n"
        f"try:\n    meta=json.load(open(path))\nexcept:\n    meta={{}}\n"
        f"meta[{json.dumps(filename)}]={{'title':{json.dumps(title)},"
        f"'description':{json.dumps(description)}}}\n"
        f"open(path,'w').write(json.dumps(meta,ensure_ascii=False,indent=2))\n"
        f"print('meta.json OK')\n"
    )
    subprocess.run(["ssh", PI, f"python3 -c {json.dumps(meta_update)}"])
    log(f"OK: {filename} en cola Pi")
    return True


def main():
    state = load_state()
    done_set = set(state.get("done", []))

    for figure in FIGURES:
        if figure in done_set:
            log(f"Saltando (ya hecho): {figure}")
            continue

        # Si Katherine Johnson ya tiene imágenes/clips, continuar desde donde está
        if figure == "Katherine Johnson":
            clip09 = DIR / "video/clips/clip_09.mp4"
            clips_exist = list((DIR / "video/clips").glob("clip_*.mp4"))
            images_exist = list((DIR / "images/generated").glob("*.png"))
            if images_exist and not clips_exist:
                log("Katherine Johnson: imágenes listas, lanzando WAN...")
                wan_log = open(DIR / "katherine_johnson.log", "a")
                subprocess.Popen([PYTHON, "generate_video_wan.py", "--channel", CHANNEL],
                                 stdout=wan_log, stderr=wan_log)
            if (clips_exist or images_exist) and not clip09.exists():
                log("Katherine Johnson WAN en curso — esperando clip_09...")
                if not wait_for_clip09():
                    log("ERROR esperando Katherine WAN")
                    sys.exit(1)
                time.sleep(15)
                # Ensamblar y pushear sin regenerar historia/imágenes
                r = subprocess.run([PYTHON, "assemble_video.py", "--channel", CHANNEL],
                                   capture_output=True, text=True, cwd=DIR)
                print(r.stdout)
                filename = slug(figure) + "_inspiring.mp4"
                archive = DIR / "publicados"
                archive.mkdir(exist_ok=True)
                shutil.copy2(DIR / "output/final_short.mp4", archive / filename)
                story = json.load(open(DIR / "stories/story.json"))
                title = story.get("title", figure)
                hook = story.get("hook", "")
                ending = story.get("ending", "")
                description = f"{hook}\n\n{ending}\n\n#shorts #historia #ciencia #inspiracion"
                subprocess.run(["scp", str(DIR / "output/final_short.mp4"),
                                f"{PI}:{QUEUE_DIR}/{filename}"])
                meta_update = (
                    f"import json\npath='{QUEUE_DIR}/meta.json'\n"
                    f"try:\n    meta=json.load(open(path))\nexcept:\n    meta={{}}\n"
                    f"meta[{json.dumps(filename)}]={{'title':{json.dumps(title)},"
                    f"'description':{json.dumps(description)}}}\n"
                    f"open(path,'w').write(json.dumps(meta,ensure_ascii=False,indent=2))\n"
                    f"print('meta.json OK')\n"
                )
                subprocess.run(["ssh", PI, f"python3 -c {json.dumps(meta_update)}"])
                log(f"OK: {filename} en cola Pi")
                done_set.add(figure)
                state["done"] = list(done_set)
                save_state(state)
                continue

        success = run_pipeline(figure)
        if success:
            done_set.add(figure)
            state["done"] = list(done_set)
            save_state(state)
            log(f"=== {figure} completado. Pausa 60s antes del siguiente ===")
            time.sleep(60)
        else:
            log(f"ERROR con {figure} — deteniendo autopilot")
            sys.exit(1)

    log("=== Todos los personajes completados ===")


if __name__ == "__main__":
    main()
