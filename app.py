import os
import re
import shutil
import subprocess

import requests
import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{6,20}")

# yt-dlp ahora necesita un runtime de JavaScript (node o deno) para YouTube
JS_RUNTIMES = {"node": {}, "deno": {}}

# Si subes un archivo secreto "cookies.txt" en Render, se usa automaticamente
COOKIES_PATH = "/etc/secrets/cookies.txt"


def base_opts():
    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "js_runtimes": JS_RUNTIMES,
        "remote_components": ["ejs:github"],
    }
    if os.path.exists(COOKIES_PATH):
        # Se copia a /tmp porque yt-dlp intenta escribir en el archivo
        tmp = "/tmp/cookies.txt"
        if not os.path.exists(tmp):
            shutil.copy(COOKIES_PATH, tmp)
        opts["cookiefile"] = tmp
    return opts


@app.get("/")
def root():
    return {"app": "Soundline API", "status": "online"}


@app.get("/debug")
def debug():
    """Borra este endpoint cuando todo funcione."""
    info = {
        "yt_dlp_version": yt_dlp.version.__version__,
        "node_path": shutil.which("node"),
        "deno_path": shutil.which("deno"),
        "cookies": os.path.exists(COOKIES_PATH),
    }
    try:
        info["node_version"] = subprocess.check_output(
            ["node", "--version"], text=True, timeout=5
        ).strip()
    except Exception as e:
        info["node_version"] = "no disponible: " + str(e)
    try:
        import yt_dlp_ejs  # noqa: F401
        info["yt_dlp_ejs"] = "instalado"
    except Exception:
        info["yt_dlp_ejs"] = "NO instalado"
    return info


class ListLogger:
    def __init__(self):
        self.lines = []

    def debug(self, msg):
        self.lines.append(str(msg))

    def info(self, msg):
        self.lines.append(str(msg))

    def warning(self, msg):
        self.lines.append("WARNING: " + str(msg))

    def error(self, msg):
        self.lines.append("ERROR: " + str(msg))


@app.get("/diag")
def diag(id: str = "dQw4w9WgXcQ"):
    """Muestra el log completo de yt-dlp para ver la causa real. Borralo despues."""
    if not VIDEO_ID_RE.fullmatch(id):
        raise HTTPException(status_code=400, detail="id invalido")
    logger = ListLogger()
    opts = base_opts()
    opts["quiet"] = False
    opts["verbose"] = True
    opts["logger"] = logger
    result = "ok"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info("https://www.youtube.com/watch?v=" + id, download=False)
    except Exception as e:
        result = "fallo: " + str(e)
    return {"result": result, "log": logger.lines[-60:]}


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
    with yt_dlp.YoutubeDL(base_opts()) as ydl:
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
