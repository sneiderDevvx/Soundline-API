import re

import requests
import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{6,20}")


@app.get("/")
def root():
    return {"app": "Soundline API", "status": "online"}


def format_duration(seconds):
    if not seconds:
        return ""
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%d:%02d" % (m, s)


@app.get("/search")
def search(q: str):
    q = q.strip()
    if not q:
        return {"success": False, "results": [], "error": "consulta vacia"}
    try:
        opts = {
            "quiet": True,
            "extract_flat": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info("ytsearch10:" + q, download=False)

        results = []
        for e in info.get("entries", []):
            if not e or not e.get("id"):
                continue
            results.append(
                {
                    "videoId": e.get("id"),
                    "title": e.get("title") or "Sin título",
                    "artist": e.get("uploader") or e.get("channel") or "Artista desconocido",
                    "duration": format_duration(e.get("duration")),
                }
            )
        return {"success": True, "results": results}
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}


def get_audio_url(video_id):
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "quiet": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            "https://www.youtube.com/watch?v=" + video_id, download=False
        )
    return info["url"]


@app.get("/stream")
def stream(id: str, request: Request):
    if not VIDEO_ID_RE.fullmatch(id):
        raise HTTPException(status_code=400, detail="id invalido")
    try:
        url = get_audio_url(id)

        headers = {}
        if "range" in request.headers:
            headers["Range"] = request.headers["range"]

        r = requests.get(url, headers=headers, stream=True, timeout=20)

        out_headers = {}
        for h in ["Content-Length", "Content-Range", "Accept-Ranges"]:
            if h in r.headers:
                out_headers[h] = r.headers[h]

        return StreamingResponse(
            r.iter_content(65536),
            status_code=r.status_code,
            media_type=r.headers.get("Content-Type", "audio/mp4"),
            headers=out_headers,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
