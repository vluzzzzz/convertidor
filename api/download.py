"""
Funcion serverless de Vercel.

Recibe un link de TikTok o Facebook y, usando yt-dlp, extrae la URL directa del
MP4 (sin descargar el archivo en el servidor). El navegador del usuario descarga
el video directo desde el CDN de la plataforma. Esto evita los limites de tiempo
y tamano de las funciones serverless de Vercel.
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import yt_dlp


def extraer_video(url: str) -> dict:
    """Devuelve titulo, miniatura y la URL directa del MP4 para el link dado."""
    # format: preferimos un MP4 progresivo (video+audio en un solo archivo), que
    # es lo que entregan TikTok y Facebook. Asi no hace falta ffmpeg para fusionar.
    opciones = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "best[ext=mp4]/best",
    }

    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)

    # Para playlists/colecciones nos quedamos con el primer item.
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]

    url_directa = info.get("url")

    # Si el formato elegido no trajo url directa, buscamos en la lista de formatos
    # el mejor mp4 progresivo (con audio y video).
    if not url_directa:
        formatos = info.get("formats", [])
        candidatos = [
            f for f in formatos
            if f.get("url")
            and f.get("vcodec") not in (None, "none")
            and f.get("acodec") not in (None, "none")
        ]
        if candidatos:
            # El ultimo suele ser el de mejor calidad.
            url_directa = candidatos[-1]["url"]

    if not url_directa:
        raise ValueError("No se pudo encontrar el video en ese link.")

    return {
        "titulo": info.get("title") or "video",
        "miniatura": info.get("thumbnail"),
        "url_directa": url_directa,
    }


class handler(BaseHTTPRequestHandler):
    def _enviar(self, codigo: int, cuerpo: dict):
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()
        self.wfile.write(json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self._enviar(204, {})

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        url = (params.get("url") or [""])[0].strip()

        if not url:
            self._enviar(400, {"error": "Falta el link del video."})
            return

        try:
            resultado = extraer_video(url)
            self._enviar(200, resultado)
        except Exception as e:  # noqa: BLE001 - devolvemos un mensaje claro al usuario
            mensaje = str(e)
            if "Private" in mensaje or "login" in mensaje.lower():
                mensaje = "Ese video es privado o necesita iniciar sesion."
            elif "Unsupported URL" in mensaje or "not a valid URL" in mensaje:
                mensaje = "Ese link no es valido o no esta soportado."
            else:
                mensaje = "No se pudo procesar el video. Revisa el link e intenta de nuevo."
            self._enviar(500, {"error": mensaje})
