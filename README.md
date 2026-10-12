# Convertidor de video (TikTok / Facebook → MP4)

Un descargador de videos **simple y sin anuncios**. Pegas el link, le das a
**Descargar** y bajas el MP4. Pensado para que cualquiera lo use.

## ¿Cómo funciona?

Por debajo usa [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), la librería libre que
extrae el video real de cientos de sitios. Una función serverless en Vercel saca la
**URL directa del MP4** (sin descargar el archivo en el servidor) y tu navegador baja
el video directo desde el CDN de la plataforma. Así no se topa con los límites de
tiempo/tamaño de Vercel.

## Desplegar en Vercel (GitHub → Vercel)

1. Sube este repo a GitHub (ya está en `vluzzzzz/convertidor`).
2. Entra a [vercel.com](https://vercel.com) → **New Project** → importa `convertidor`.
3. Dale **Deploy**. Vercel detecta la función Python en `api/` automáticamente.
4. Abre la URL que te da Vercel y prueba con un link de TikTok o Facebook.

## Estructura

```
├── index.html        # La página (interfaz)
├── api/download.py   # Función serverless que extrae el MP4 con yt-dlp
├── requirements.txt  # Dependencia: yt-dlp
└── vercel.json       # Config de Vercel (runtime Python)
```

## Probar localmente

Con [Vercel CLI](https://vercel.com/docs/cli):

```bash
npm i -g vercel
vercel dev
```

Luego abre http://localhost:3000

## Plan B (si Vercel es bloqueado)

Las plataformas a veces bloquean las IP de datacenter de Vercel. Si en algún momento
deja de funcionar, puedes descargar directo desde tu PC con yt-dlp:

```bash
pip install yt-dlp
yt-dlp "PEGA_EL_LINK_AQUI"
```

## Notas

- **TikTok**: baja sin marca de agua.
- **Facebook**: videos y reels públicos.
- Contenido privado o que requiere login no es compatible.
