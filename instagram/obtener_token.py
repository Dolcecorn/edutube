#!/usr/bin/env python3
"""Convierte el token corto del Explorador de la API Graph en un token de página que no vence,
y busca el id de la cuenta de Instagram. Se corre una sola vez en tu computador:

    python3 instagram/obtener_token.py

Pide el id y la clave secreta de la app (Configuración de la app → Básica) y el token corto.
No guarda nada: muestra los dos valores para copiarlos a los secretos de GitHub.
"""
import getpass
import json
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.facebook.com/v23.0"


def get(ruta, **params):
    url = f"{API}/{ruta}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Error de Meta: {e.read().decode(errors='replace')}")


app_id = input("Identificador de la app: ").strip()
secreto = getpass.getpass("Clave secreta de la app (no se muestra): ").strip()
corto = getpass.getpass("Token del Explorador (no se muestra): ").strip()

largo = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
            client_secret=secreto, fb_exchange_token=corto)["access_token"]
paginas = get("me/accounts", fields="name,access_token,instagram_business_account{username}",
              access_token=largo).get("data", [])
con_ig = [p for p in paginas if p.get("instagram_business_account")]
if not con_ig:
    raise SystemExit("Ninguna página tuya tiene una cuenta de Instagram vinculada. "
                     "Revisa la vinculación y que hayas elegido la página al generar el token.")
for p in con_ig:
    ig = p["instagram_business_account"]
    print(f"\nPágina: {p['name']}  ->  Instagram @{ig.get('username', '?')}")
    print(f"IG_USER_ID      = {ig['id']}")
    print(f"IG_ACCESS_TOKEN = {p['access_token']}")
print("\nCopia esos dos valores a GitHub (Settings → Secrets and variables → Actions). Este token no vence "
      "mientras no cambies tu contraseña de Facebook ni quites la app.")
