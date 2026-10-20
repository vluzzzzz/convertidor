"""
Recorta un archivo cookies.txt para dejar SOLO las cookies de YouTube y Google.

Asi el archivo pesa poco (unos KB) y cabe en una variable de entorno de Vercel
(limite de 64 KB).

Uso:
    python filtrar_cookies.py cookies.txt

Genera "cookies_youtube.txt" al lado. Abre ese archivo, copia TODO su contenido
y pegalo en la variable YT_COOKIES de Vercel.

El script NO envia nada a internet: todo ocurre en tu computadora.
"""

import sys
import os

DOMINIOS = (".youtube.com", ".google.com", ".ytimg.com")


def main():
    if len(sys.argv) < 2:
        print("Uso: python filtrar_cookies.py <ruta_a_cookies.txt>")
        sys.exit(1)

    entrada = sys.argv[1]
    if not os.path.isfile(entrada):
        print("No se encontro el archivo:", entrada)
        sys.exit(1)

    salida = os.path.join(os.path.dirname(os.path.abspath(entrada)), "cookies_youtube.txt")

    guardadas = 0
    with open(entrada, "r", encoding="utf-8", errors="ignore") as f_in, \
         open(salida, "w", encoding="utf-8") as f_out:
        for linea in f_in:
            # Mantenemos comentarios/cabeceras y las lineas de dominios de YouTube.
            if linea.startswith("#"):
                f_out.write(linea)
                continue
            if any(dom in linea for dom in DOMINIOS):
                f_out.write(linea)
                guardadas += 1

    tam = os.path.getsize(salida)
    print("Listo. Cookies de YouTube guardadas:", guardadas)
    print("Archivo:", salida)
    print("Tamano:", tam, "bytes", "(OK)" if tam < 65535 else "(AUN MUY GRANDE)")


if __name__ == "__main__":
    main()
