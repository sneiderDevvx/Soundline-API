
from fastapi import FastAPI, Query
from ytmusicapi import YTMusic

app = FastAPI(title="Soundline API")

music = YTMusic()

@app.get("/")
def home():
    return {
        "app": "Soundline API",
        "status": "online"
    }

@app.get("/search")
def search(q: str = Query(min_length=1, max_length=100)):

    try:
        results = music.search(
            q,
            filter="songs",
            limit=20
        )

        songs = []

        for item in results:

            artists = item.get("artists") or []

            artist_names = [
                artist.get("name", "")
                for artist in artists
                if isinstance(artist, dict)
            ]

            thumbnails = item.get("thumbnails") or []

            artwork = (
                thumbnails[-1].get("url", "")
                if thumbnails else ""
            )

            songs.append({
                "videoId": item.get("videoId", ""),
                "title": item.get("title", ""),
                "artist": ", ".join(artist_names),
                "album": (item.get("album") or {}).get("name", ""),
                "duration": item.get("duration", ""),
                "thumbnail": artwork
            })

        return {
            "success": True,
            "query": q,
            "results": songs
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
            "results": []
        }
      
