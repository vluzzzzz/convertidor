"""
Funcion serverless de Vercel (entrypoint unico).

Con el runtime Python nuevo de Vercel, TODAS las rutas llegan a este handler.
Segun la peticion hacemos:

  * Sin ?url=                     -> servimos la pagina (interfaz).
  * ?url=...                      -> devolvemos info (titulo/miniatura) en JSON.
  * ?dl=1&url=...                 -> proxy: bajamos el video MP4 y lo reenviamos.
  * ?dl=1&fmt=mp3&url=...         -> proxy: extraemos el audio a MP3 y lo reenviamos.

Usa yt-dlp (y ffmpeg via imageio-ffmpeg para el MP3). Bajar en el servidor
evita el 403 de las CDN de TikTok/Facebook y maneja la sesion de YouTube.
"""

import json
import os
import re
import tempfile
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

import yt_dlp


def ruta_ffmpeg():
    """Devuelve la ruta al binario ffmpeg (incluido via imageio-ffmpeg)."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def opciones_base() -> dict:
    """Opciones comunes de yt-dlp para TikTok y Facebook."""
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }


# ---------------------------------------------------------------------------
# La pagina (interfaz). Va embebida para que siempre se sirva.
# ---------------------------------------------------------------------------
PAGINA = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Descargar videos - TikTok y Facebook</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: #0f172a; color: #e2e8f0; margin: 0; min-height: 100vh;
      display: flex; align-items: center; justify-content: center; padding: 20px;
    }
    .caja {
      width: 100%; max-width: 520px; background: #1e293b; border-radius: 16px;
      padding: 32px 28px; box-shadow: 0 10px 40px rgba(0,0,0,.4);
    }
    h1 { font-size: 24px; margin: 0 0 6px; text-align: center; }
    p.sub { margin: 0 0 22px; text-align: center; color: #94a3b8; font-size: 14px; }
    .toggle { display: flex; gap: 8px; margin-bottom: 14px; }
    .toggle button {
      flex: 1; padding: 12px; font-size: 15px; font-weight: 600; border: 2px solid #334155;
      border-radius: 10px; background: #0f172a; color: #94a3b8; cursor: pointer;
    }
    .toggle button.activo { border-color: #38bdf8; color: #e2e8f0; background: #0b2534; }
    input {
      width: 100%; padding: 14px 16px; font-size: 16px; border: 2px solid #334155;
      border-radius: 10px; background: #0f172a; color: #e2e8f0; margin-bottom: 14px;
    }
    input:focus { outline: none; border-color: #38bdf8; }
    #btn {
      width: 100%; padding: 14px; font-size: 17px; font-weight: 600; border: none;
      border-radius: 10px; background: #38bdf8; color: #0f172a; cursor: pointer;
    }
    #btn:disabled { opacity: .6; cursor: not-allowed; }
    #estado { margin-top: 18px; text-align: center; font-size: 15px; min-height: 22px; }
    .error { color: #f87171; }
    #resultado { margin-top: 20px; text-align: center; }
    #resultado img { max-width: 100%; border-radius: 10px; margin-bottom: 14px; }
    #resultado .titulo { font-size: 14px; color: #cbd5e1; margin-bottom: 14px; }
    a.descargar {
      display: inline-block; padding: 13px 24px; background: #22c55e; color: #04240f;
      font-weight: 700; border-radius: 10px; text-decoration: none;
    }
    .nota { margin-top: 12px; font-size: 12px; color: #64748b; }
  </style>
</head>
<body>
  <div class="caja">
    <h1>&#11015;&#65039; Descargar</h1>
    <p class="sub">TikTok y Facebook. Sin anuncios.</p>
    <div class="toggle">
      <button id="btnVideo" class="activo" type="button">&#127916; Video MP4</button>
      <button id="btnAudio" type="button">&#127925; Audio MP3</button>
    </div>
    <input id="url" type="text" placeholder="Pega aqui el link de TikTok o Facebook..." autocomplete="off" />
    <button id="btn">Descargar</button>
    <div id="estado"></div>
    <div id="resultado"></div>
  </div>
  <script>
    const input = document.getElementById("url");
    const btn = document.getElementById("btn");
    const estado = document.getElementById("estado");
    const resultado = document.getElementById("resultado");
    const btnVideo = document.getElementById("btnVideo");
    const btnAudio = document.getElementById("btnAudio");
    let formato = "mp4";

    function elegir(f) {
      formato = f;
      btnVideo.classList.toggle("activo", f === "mp4");
      btnAudio.classList.toggle("activo", f === "mp3");
    }
    btnVideo.addEventListener("click", () => elegir("mp4"));
    btnAudio.addEventListener("click", () => elegir("mp3"));

    async function procesar() {
      const url = input.value.trim();
      resultado.innerHTML = ""; estado.className = "";
      if (!url) { estado.textContent = "Primero pega un link."; return; }
      if (/youtube\\.com|youtu\\.be/i.test(url)) {
        estado.className = "error";
        estado.textContent = "\\u26A0\\uFE0F Para YouTube usa la app NewPipe en el celular (YouTube bloquea las webs).";
        return;
      }
      btn.disabled = true; estado.textContent = "Procesando... \\u23F3";
      try {
        const resp = await fetch("/api/download?url=" + encodeURIComponent(url));
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || "No se pudo procesar.");
        estado.textContent = "\\u00A1Listo! \\u2705";
        const etiqueta = formato === "mp3" ? "Descargar MP3" : "Descargar MP4";
        const dl = "/api/download?dl=1&fmt=" + formato + "&url=" + encodeURIComponent(url);
        resultado.innerHTML =
          (data.miniatura ? '<img src="' + data.miniatura + '" alt="miniatura" />' : "") +
          '<div class="titulo">' + (data.titulo || "") + '</div>' +
          '<a class="descargar" href="' + dl + '">' + etiqueta + '</a>' +
          '<div class="nota">La descarga pasa por el servidor. Para MP3 puede tardar unos segundos mas.</div>';
      } catch (e) {
        estado.className = "error"; estado.textContent = "\\u26A0\\uFE0F " + e.message;
      } finally { btn.disabled = false; }
    }
    btn.addEventListener("click", procesar);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") procesar(); });
  </script>
</body>
</html>"""


def extraer_info(url: str) -> dict:
    """Devuelve titulo y miniatura del link (sin descargar)."""
    opciones = opciones_base()
    opciones["skip_download"] = True
    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]
    return {
        "titulo": info.get("title") or "video",
        "miniatura": info.get("thumbnail"),
    }


def nombre_archivo(titulo: str, extension: str) -> str:
    """Convierte un titulo en un nombre de archivo seguro con la extension dada."""
    limpio = re.sub(r"[^\w\s-]", "", titulo, flags=re.UNICODE).strip()
    limpio = re.sub(r"\s+", "_", limpio)
    return (limpio[:60] or "archivo") + "." + extension


class handler(BaseHTTPRequestHandler):
    def _enviar_json(self, codigo: int, cuerpo: dict):
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"))

    def _enviar_pagina(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGINA.encode("utf-8"))

    def _proxy_descarga(self, url: str, fmt: str):
        """yt-dlp baja el contenido a /tmp y lo reenviamos al navegador.

        fmt == 'mp3' -> extrae solo el audio y lo convierte a MP3 (usa ffmpeg).
        fmt == 'mp4' -> baja el video completo.
        """
        es_mp3 = fmt == "mp3"
        carpeta = tempfile.mkdtemp()
        plantilla = os.path.join(carpeta, "salida.%(ext)s")

        opciones = opciones_base()
        opciones["outtmpl"] = plantilla
        if es_mp3:
            ff = ruta_ffmpeg()
            if ff:
                opciones["ffmpeg_location"] = ff
            opciones["format"] = "bestaudio/best"
            opciones["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
            extension, content_type = "mp3", "audio/mpeg"
        else:
            opciones["format"] = "best[ext=mp4]/best"
            extension, content_type = "mp4", "video/mp4"

        try:
            with yt_dlp.YoutubeDL(opciones) as ydl:
                info = ydl.extract_info(url, download=True)
            if info.get("_type") == "playlist" and info.get("entries"):
                info = info["entries"][0]

            # Tras el postproceso, buscamos el archivo con la extension esperada.
            candidatos = [f for f in os.listdir(carpeta) if f.endswith("." + extension)]
            if not candidatos:
                candidatos = [f for f in os.listdir(carpeta) if f.startswith("salida.")]
            if not candidatos:
                raise RuntimeError("No se genero el archivo.")
            ruta = os.path.join(carpeta, candidatos[0])

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            nombre = nombre_archivo(info.get("title") or "archivo", extension)
            self.send_header(
                "Content-Disposition",
                "attachment; filename*=UTF-8''" + quote(nombre),
            )
            self.send_header("Content-Length", str(os.path.getsize(ruta)))
            self.end_headers()
            with open(ruta, "rb") as f:
                while True:
                    trozo = f.read(64 * 1024)
                    if not trozo:
                        break
                    self.wfile.write(trozo)
        finally:
            try:
                for f in os.listdir(carpeta):
                    os.remove(os.path.join(carpeta, f))
                os.rmdir(carpeta)
            except OSError:
                pass

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        url = (params.get("url") or [""])[0].strip()
        descargar = (params.get("dl") or [""])[0] == "1"
        fmt = (params.get("fmt") or ["mp4"])[0]

        # Sin ?url= -> mostramos la pagina.
        if not url:
            self._enviar_pagina()
            return

        # Con ?dl=1 -> proxy: bajamos y reenviamos el archivo.
        if descargar:
            try:
                self._proxy_descarga(url, fmt)
            except Exception:  # noqa: BLE001
                self._enviar_json(500, {"error": "No se pudo descargar."})
            return

        # Con ?url= (sin dl) -> devolvemos la info en JSON.
        try:
            self._enviar_json(200, extraer_info(url))
        except Exception as e:  # noqa: BLE001
            mensaje = str(e)
            if "Private" in mensaje or "login" in mensaje.lower() or "bot" in mensaje.lower():
                mensaje = "Ese contenido es privado, o la plataforma bloqueo la peticion."
            elif "Unsupported URL" in mensaje or "not a valid URL" in mensaje:
                mensaje = "Ese link no es valido o no esta soportado."
            else:
                mensaje = "No se pudo procesar. Revisa el link e intenta de nuevo."
            self._enviar_json(500, {"error": mensaje})
