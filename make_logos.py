#!/usr/bin/env python3
import json, time, uuid, urllib.request, http.client, io, numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

COMFY_URL  = "http://127.0.0.1:8188"
OUTDIR     = Path("/home/andreu/channel_art")
OUTDIR.mkdir(exist_ok=True)
TG_TOKEN   = "8352432640:AAGvqpzWiAaL-KiC1nrJH_zlmX-BMeeICPc"
TG_CHAT_ID = "618447835"
CHECKPOINT = "juggernaut.safetensors"

MYSTERY_PROMPT = (
    "dark mysterious landscape, ancient stone ruins with gothic arches on the left, "
    "pyramids of egypt on the right, ornate antique compass in the upper center, "
    "two mysterious silhouettes of people standing, magnifying glass in the bottom foreground, "
    "old parchment map texture in background, noir cinematic atmosphere, "
    "deep blue midnight and dark tones with golden accents, chiaroscuro, fog, 8k, square composition"
)
INSPIRING_PROMPT = (
    "golden sunrise over ancient library and observatory, telescope pointing to stars, "
    "glowing lightbulb surrounded by books and gears, silhouette of a scientist looking at the horizon, "
    "warm amber golden light rays, renaissance painting style, "
    "inspiring and uplifting atmosphere, warm tones amber and gold, 8k, square composition"
)
NEG_MYSTERY   = "bright, cheerful, text, watermark, modern, cartoon, anime, oversaturated, blurry, low quality"
NEG_INSPIRING = "dark, scary, horror, cold, text, watermark, cartoon, anime, blurry, low quality, night"

def load_font(size, bold=True):
    paths_bold = ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    paths_reg  = ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for p in (paths_bold if bold else paths_reg):
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def comfy_gen(prompt, neg, seed=42):
    import websocket
    client_id = str(uuid.uuid4())
    wf = {
        "3": {"class_type":"KSampler","inputs":{"model":["4",0],"positive":["6",0],"negative":["7",0],"latent_image":["5",0],"seed":seed,"steps":35,"cfg":7.5,"sampler_name":"dpmpp_2m","scheduler":"karras","denoise":1.0}},
        "4": {"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":CHECKPOINT}},
        "5": {"class_type":"EmptyLatentImage","inputs":{"width":896,"height":896,"batch_size":1}},
        "6": {"class_type":"CLIPTextEncode","inputs":{"text":prompt,"clip":["4",1]}},
        "7": {"class_type":"CLIPTextEncode","inputs":{"text":neg,"clip":["4",1]}},
        "8": {"class_type":"VAEDecode","inputs":{"samples":["3",0],"vae":["4",2]}},
        "9": {"class_type":"SaveImage","inputs":{"images":["8",0],"filename_prefix":"logo_bg"}}
    }
    payload = json.dumps({"prompt":wf,"client_id":client_id}).encode()
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=payload, headers={"Content-Type":"application/json"})
    pid = json.loads(urllib.request.urlopen(req,timeout=15).read())["prompt_id"]
    ws = websocket.WebSocket()
    ws.connect(f"ws://127.0.0.1:8188/ws?clientId={client_id}")
    try:
        while True:
            msg = ws.recv()
            if isinstance(msg,bytes): continue
            data = json.loads(msg)
            if data.get("type")=="executing" and data.get("data",{}).get("node") is None and data["data"].get("prompt_id")==pid:
                break
    finally:
        ws.close()
    resp = json.loads(urllib.request.urlopen(f"{COMFY_URL}/history/{pid}",timeout=15).read())
    for node_out in resp.get(pid,{}).get("outputs",{}).values():
        for img in node_out.get("images",[]):
            raw = urllib.request.urlopen(f"{COMFY_URL}/view?filename={img['filename']}&type=output",timeout=30).read()
            return Image.open(io.BytesIO(raw)).convert("RGB")

def make_circle_logo(bg, line1, line2_white, line2_color, line2_colorval, sub1, sub2, dark=True):
    SIZE = 800
    img = bg.resize((SIZE,SIZE), Image.LANCZOS)
    arr = np.array(img).astype(float)
    cx,cy = SIZE//2,SIZE//2
    Y,X = np.ogrid[:SIZE,:SIZE]
    dist = np.sqrt((X-cx)**2+(Y-cy)**2)
    vignette = np.clip(1-dist/(SIZE*0.62),0,1)**0.55
    arr = arr*vignette[:,:,np.newaxis]
    for y in range(SIZE//2, SIZE):
        f = (y-SIZE//2)/(SIZE//2)
        arr[y] *= (1-f*(0.55 if dark else 0.45))
    img = Image.fromarray(arr.astype(np.uint8))
    mask = Image.new("L",(SIZE,SIZE),0)
    ImageDraw.Draw(mask).ellipse([0,0,SIZE-1,SIZE-1],fill=255)
    result = Image.new("RGBA",(SIZE,SIZE),(0,0,0,0))
    result.paste(img,mask=mask)
    draw = ImageDraw.Draw(result)
    gold = (200,160,40,220)
    draw.ellipse([4,4,SIZE-5,SIZE-5], outline=gold, width=8)
    draw.ellipse([15,15,SIZE-16,SIZE-16], outline=(200,160,40,100), width=3)

    def ctext(text, y, font, fill, shadow=True):
        bb = draw.textbbox((0,0),text,font=font)
        w = bb[2]-bb[0]
        x = (SIZE-w)//2
        if shadow: draw.text((x+3,y+3),text,font=font,fill=(0,0,0,190))
        draw.text((x,y),text,font=font,fill=fill)

    f_big  = load_font(92, bold=True)
    f_sub  = load_font(30, bold=True)
    f_sub2 = load_font(26, bold=False)

    ctext(line1, 335, f_big, (255,255,255,255))
    al_bb  = draw.textbbox((0,0), line2_white+" ", font=f_big)
    col_bb = draw.textbbox((0,0), line2_color, font=f_big)
    total_w = (al_bb[2]-al_bb[0]) + (col_bb[2]-col_bb[0])
    x0 = (SIZE-total_w)//2
    y2 = 430
    draw.text((x0+3,y2+3), line2_white+" ", font=f_big, fill=(0,0,0,190))
    draw.text((x0,y2), line2_white+" ", font=f_big, fill=(255,255,255,255))
    x1 = x0+(al_bb[2]-al_bb[0])
    draw.text((x1+3,y2+3), line2_color, font=f_big, fill=(0,0,0,190))
    draw.text((x1,y2), line2_color, font=f_big, fill=line2_colorval)
    draw.rectangle([SIZE//2-140,543,SIZE//2+140,547], fill=(200,160,40,220))
    ctext(sub1, 556, f_sub,  (210,170,50,255))
    ctext(sub2, 594, f_sub2, (210,170,50,200))
    return result

def tg_send(path, caption):
    boundary = "----B"+uuid.uuid4().hex
    img_data = path.read_bytes()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{TG_CHAT_ID}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{path.name}\"\r\nContent-Type: image/png\r\n\r\n"
    ).encode()+img_data+f"\r\n--{boundary}--\r\n".encode()
    conn = http.client.HTTPSConnection("api.telegram.org")
    conn.request("POST",f"/bot{TG_TOKEN}/sendPhoto",body=body,
                 headers={"Content-Type":f"multipart/form-data; boundary={boundary}"})
    r = json.loads(conn.getresponse().read())
    print("TG OK" if r.get("ok") else f"TG ERR: {r}", flush=True)

def main():
    print("=== Logo Misterios al Dia ===", flush=True)
    bg = comfy_gen(MYSTERY_PROMPT, NEG_MYSTERY, seed=42)
    logo = make_circle_logo(bg, "MISTERIOS", "AL", "DIA", (200,30,30,255),
                            "UN RELATO DE MISTERIOS", "CADA DIA", dark=True)
    out = OUTDIR/"misterios_logo_v2.png"
    logo.save(str(out), "PNG")
    tg_send(out, "Misterios al Dia - Logo v2")

    print("=== Logo Inspiring al Dia ===", flush=True)
    time.sleep(5)
    bg2 = comfy_gen(INSPIRING_PROMPT, NEG_INSPIRING, seed=77)
    logo2 = make_circle_logo(bg2, "INSPIRING", "AL", "DIA", (255,200,0,255),
                             "UN PERSONAJE. CADA DIA.", "", dark=False)
    out2 = OUTDIR/"inspiring_logo_v1.png"
    logo2.save(str(out2), "PNG")
    tg_send(out2, "Inspiring al Dia - Logo v1")

    print("Listo.", flush=True)

if __name__ == "__main__":
    main()
