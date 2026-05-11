import argparse
import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube"]
TOKEN_FILE = r"C:\Users\andre\youtube_bot\token.json"
CLIENT_SECRET = r"C:\Users\andre\youtube_bot\client_secrets.json"


def get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def build_metadata(story: dict, channel: dict) -> dict:
    figure = (story.get("figure") or {}).get("name", "Personaje histórico")
    title = story.get("title") or f"{figure} — Historia inspiradora"
    hook = story.get("hook", "")
    ending = story.get("ending", "")
    cta_lines = channel.get("cta", {}).get("lines", [])
    cta_text = " ".join(l for l in cta_lines if l)

    description = f"{hook}\n\n{ending}\n\n{cta_text}\n\n#shorts #{figure.replace(' ', '')} #historia #ciencia #inspiracion"

    return {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": [figure, "historia", "ciencia", "shorts", "inspiracion", "personajes historicos"],
            "categoryId": "27",  # Education
            "defaultLanguage": "es",
        },
        "status": {
            "privacyStatus": "private",  # private por defecto para revisar antes de publicar
            "selfDeclaredMadeForKids": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="output/final_short.mp4")
    parser.add_argument("--channel", default="config/channel_inspirational_science_es.json")
    parser.add_argument("--story", default="stories/story.json")
    parser.add_argument("--public", action="store_true", help="Publicar directamente (por defecto: privado)")
    args = parser.parse_args()

    with open(args.channel, encoding="utf-8") as f:
        channel = json.load(f)
    with open(args.story, encoding="utf-8") as f:
        story = json.load(f)

    metadata = build_metadata(story, channel)
    if args.public:
        metadata["status"]["privacyStatus"] = "public"

    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    print(f"Subiendo: {args.video}")
    print(f"Título: {metadata['snippet']['title']}")
    print(f"Privacidad: {metadata['status']['privacyStatus']}")

    media = MediaFileUpload(args.video, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)
    request = youtube.videos().insert(
        part="snippet,status",
        body=metadata,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Subiendo... {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"\nOK: https://www.youtube.com/watch?v={video_id}")
    print(f"Studio: https://studio.youtube.com/video/{video_id}/edit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
