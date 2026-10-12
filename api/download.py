"""
Funcion serverless de Vercel (entrypoint unico).

Con el runtime Python nuevo de Vercel, TODAS las rutas llegan a este handler.
Por eso aqui hacemos dos cosas segun la peticion:

  * Si viene el parametro ?url=...  -> extraemos el MP4 y devolvemos JSON.
  * Si no                            -> servimos la pagina (index.html).

Usa yt-dlp para sacar la URL directa del MP4 (sin descargar el archivo en el
servidor); el navegador del usuario descarga el video directo desde el CDN.
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import yt_dlp


# ---------------------------------------------------------------------------
# La pagina (interfaz). Va embebida para que siempre se sirva, sin depender de
# como Vercel maneje los archivos estaticos con el entrypoint Python.
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
    p.sub { margin: 0 0 24px; text-align: center; color: #94a3b8; font-size: 14px; }
    input {
      width: 100%; padding: 14px 16px; font-size: 16px; border: 2px solid #334155;
      border-radius: 10px; background: #0f172a; color: #e2e8f0; margin-bottom: 14px;
    }
    input:focus { outline: none; border-color: #38bdf8; }
    button {
      width: 100%; padding: 14px; font-size: 17px; font-weight: 600; border: none;
      border-radius: 10px; background: #38bdf8; color: #0f172a; cursor: pointer;
    }
    button:disabled { opacity: .6; cursor: not-allowed; }
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
    <h1>&#11015;&#65039; Descargar video</h1>
    <p class="sub">Pega el link de TikTok o Facebook. Sin anuncios.</p>
    <input id="url" type="text" placeholder="Pega aqui el link del video..." autocomplete="off" />
    <button id="btn">Descargar</button>
    <div id="estado"></div>
    <div id="resultado"></div>
  </div>
  <script>
    const input = document.getElementById("url");
    const btn = document.getElementById("btn");
    const estado = document.getElementById("estado");
    const resultado = document.getElementById("resultado");

    async function procesar() {
      const url = input.value.trim();
      resultado.innerHTML = ""; estado.className = "";
      if (!url) { estado.textContent = "Primero pega un link."; return; }
      btn.disabled = true; estado.textContent = "Procesando... \\u23F3";
      try {
        const resp = await fetch("/api/download?url=" + encodeURIComponent(url));
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || "No se pudo procesar.");
        estado.textContent = "\\u00A1Listo! \\u2705";
        resultado.innerHTML =
          (data.miniatura ? '<img src="' + data.miniatura + '" alt="miniatura" />' : "") +
          '<div class="titulo">' + (data.titulo || "") + '</div>' +
          '<a class="descargar" href="' + data.url_directa + '" download target="_blank" rel="noopener">Descargar MP4</a>' +
          '<div class="nota">Si el video se abre en vez de bajar, clic derecho sobre el y elige "Guardar video".</div>';
      } catch (e) {
        estado.className = "error"; estado.textContent = "\\u26A0\\uFE0F " + e.message;
      } finally { btn.disabled = false; }
    }
    btn.addEventListener("click", procesar);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") procesar(); });
  </script>
</body>
</html>"""


def extraer_video(url: str) -> dict:
    """Devuelve titulo, miniatura y la URL directa del MP4 para el link dado."""
    opciones = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "best[ext=mp4]/best",
    }
    with yt_dlp.YoutubeDL(opciones) as ydl:
        info = ydl.extract_info(url, download=False)

    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]

    url_directa = info.get("url")
    if not url_directa:
        candidatos = [
            f for f in info.get("formats", [])
            if f.get("url")
            and f.get("vcodec") not in (None, "none")
            and f.get("acodec") not in (None, "none")
        ]
        if candidatos:
            url_directa = candidatos[-1]["url"]

    if not url_directa:
        raise ValueError("No se pudo encontrar el video en ese link.")

    return {
        "titulo": info.get("title") or "video",
        "miniatura": info.get("thumbnail"),
        "url_directa": url_directa,
    }


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

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        url = (params.get("url") or [""])[0].strip()

        # Sin ?url= -> mostramos la pagina.
        if not url:
            self._enviar_pagina()
            return

        # Con ?url= -> procesamos el video.
        try:
            self._enviar_json(200, extraer_video(url))
        except Exception as e:  # noqa: BLE001
            mensaje = str(e)
            if "Private" in mensaje or "login" in mensaje.lower():
                mensaje = "Ese video es privado o necesita iniciar sesion."
            elif "Unsupported URL" in mensaje or "not a valid URL" in mensaje:
                mensaje = "Ese link no es valido o no esta soportado."
            else:
                mensaje = "No se pudo procesar el video. Revisa el link e intenta de nuevo."
            self._enviar_json(500, {"error": mensaje})
