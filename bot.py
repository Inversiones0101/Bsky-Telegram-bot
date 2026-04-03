#!/usr/bin/env python3
"""
Bsky-Telegram Bot - VISOR FINANCIERO v2.3
Mejora: GestorHistorialBsky usa JSON con cabeceras por cuenta
        Guarda las ultimas 15 URLs por cuenta en last_id_bsky.json
"""
import os
import sys
import json
import feedparser
import requests
import time
import re
import yfinance as yf
from datetime import datetime
import pytz

try:
    from deep_translator import GoogleTranslator
    TRADUCTOR_DISPONIBLE = True
except ImportError:
    TRADUCTOR_DISPONIBLE = False
    print("⚠️ deep-translator no instalado")

# ============= CONFIGURACIÓN =============

FEEDS_BSKY = {
    "TRENDSPIDER_BSKY": "https://bsky.app/profile/trendspider.com/rss",
    "BARCHART_BSKY": "https://bsky.app/profile/barchart.com/rss",
    "QUANTHUSTLE": "https://bsky.app/profile/quanthustle.bsky.social/rss",
    "EARNINGS_FORESIGHT": "https://bsky.app/profile/earningsforesight.bsky.social/rss",
    "GITHUB_TRENDING": "https://bsky.app/profile/github-trending.bsky.social/rss"
}

FEEDS_ESPECIALES = {
    "AMBITO_DOLAR": {
        "url": "https://bsky.app/profile/ambitodolar.bsky.social/rss",
        "filtros_exactos": ["Apertura de jornada", "Cierre de jornada"],
        "emoji": "💵"
    }
}

FEEDS_SPOTIFY = {
    "BLOOMBERG_LINEA": {
        "nombre": "🎧 Bloomberg Línea Argentina",
        "url_rss": "https://anchor.fm/s/7ce84050/podcast/rss",
        "url_base": "https://podcasters.spotify.com/pod/show/bloomberg-linea-argentina",
        "imagen_default": "https://is1-ssl.mzstatic.com/image/thumb/Podcasts116/v4/b6/26/1b/b6261b6d-74f2-b8af-fece-58d41c2e712e/mza_15124749693889878680.jpg/600x600bb.jpg",
        "emoji": "🎙️"
    }
}

MARKETS = {
    "WALL_STREET": {
        "^SPX": ("S&P 500", "🇺🇸"),
        "^DJI": ("Dow Jones", "🏭"),
        "^IXIC": ("NASDAQ", "💻"),
        "^VIX": ("VIX", "⚡"),
        "^TNX": ("Tasa 10Y", "📜")
    },
    "COMMODITIES": {
        "GC=F": ("Oro", "🥇"),
        "ZS=F": ("Soja", "🌱"),
        "CL=F": ("Petróleo", "🛢️"),
        "SI=F": ("Plata", "🥈")
    },
    "CRYPTOS": {
        "BTC-USD": ("Bitcoin", "🟠"),
        "ETH-USD": ("Ethereum", "💎"),
        "SOL-USD": ("Solana", "🟣")
    }
}

# ============= UTILIDADES =============

def traducir_texto(texto, destino='es'):
    if not TRADUCTOR_DISPONIBLE or not texto:
        return texto
    try:
        texto_truncado = texto[:4000]
        traductor = GoogleTranslator(source='auto', target=destino)
        return traductor.translate(texto_truncado)
    except Exception as e:
        print(f"⚠️ Error traduciendo: {e}")
        return texto

def esta_abierto_wall_street():
    tz_ny = pytz.timezone('America/New_York')
    ahora_ny = datetime.now(tz_ny)
    if ahora_ny.weekday() >= 5:
        return False
    apertura = ahora_ny.replace(hour=9, minute=30, second=0, microsecond=0)
    cierre = ahora_ny.replace(hour=16, minute=0, second=0, microsecond=0)
    return apertura <= ahora_ny <= cierre

def formatear_cambio(cambio):
    if cambio > 0:
        return f"🟢 +{cambio:.2f}%"
    elif cambio < 0:
        return f"🔴 {cambio:.2f}%"
    else:
        return f"⚪ 0.00%"

def obtener_datos_monitor():
    lineas = [
        "📊 <b>VISOR DE MERCADOS</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━",
        ""
    ]

    abierto = esta_abierto_wall_street()
    estado_ws = "🟢 MERCADO ABIERTO" if abierto else "🔴 MERCADO CERRADO"
    lineas.append(f"🇺🇸 <b>Wall Street:</b> {estado_ws}\n")

    for seccion, activos in MARKETS.items():
        emojis_seccion = {"WALL_STREET": "🏦", "COMMODITIES": "🌾", "CRYPTOS": "₿"}
        emoji_sec = emojis_seccion.get(seccion, "📈")

        if seccion != "WALL_STREET":
            lineas.append(f"\n{emoji_sec} <b>{seccion.replace('_', ' ')}</b>")

        for ticker, (nombre, emoji) in activos.items():
            try:
                data = yf.Ticker(ticker).history(period="2d")
                if len(data) < 2:
                    continue

                precio = data['Close'].iloc[-1]
                precio_ant = data['Close'].iloc[-2]
                cambio = ((precio / precio_ant) - 1) * 100

                if ticker == "^TNX":
                    precio_str = f"{precio:.2f}%"
                else:
                    precio_str = f"{precio:,.2f}"

                indicador = "🟢" if cambio >= 0 else "🔴"
                cambio_str = f"{cambio:+.2f}%"

                linea = f"{emoji} {indicador} <code>{nombre:<12}</code> <b>{precio_str:>10}</b>  <code>{cambio_str:>8}</code>"
                lineas.append(linea)

            except Exception as e:
                print(f"⚠️ Error en {ticker}: {e}")
                continue

    lineas.append("\n━━━━━━━━━━━━━━━━━━━━━━━")
    hora_ar = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%H:%M")
    lineas.append(f"🕐 <i>Actualizado: {hora_ar} AR</i>")

    return "\n".join(lineas)

# ============= TELEGRAM =============

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')

        if not self.token or not self.chat_id:
            raise ValueError("Faltan credenciales de Telegram")

    def enviar_texto(self, texto, disable_preview=True):
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            'chat_id': self.chat_id,
            'text': texto[:4000],
            'parse_mode': 'HTML',
            'disable_web_page_preview': disable_preview
        }
        try:
            resp = requests.post(url, json=payload, timeout=25)
            return resp.status_code == 200
        except Exception as e:
            print(f"❌ Error enviando texto: {e}")
            return False

    def enviar_foto_con_caption(self, foto_url, caption, link_bsky=None):
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        header = "📊 <b>Bluesky Feed</b>\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        footer = f"\n\n🔗 <a href='{link_bsky}'>Ver en Bluesky</a>" if link_bsky else ""
        caption_completo = f"{header}{caption}{footer}"
        if len(caption_completo) > 1024:
            caption_completo = caption_completo[:1021] + "..."
        payload = {
            'chat_id': self.chat_id,
            'photo': foto_url,
            'caption': caption_completo,
            'parse_mode': 'HTML'
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                error_desc = resp.json().get('description', '')
                if "wrong" in error_desc.lower() or "failed" in error_desc.lower():
                    return self.enviar_texto(caption_completo, disable_preview=False)
                return False
            return True
        except Exception as e:
            print(f"❌ Error enviando foto: {e}")
            return False

    def enviar_alerta_mmd(self, link_stream, imagen_url=None):
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        caption = (
            "🔔 <b>¡AHORAPLAY!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📺 Transmisión en vivo MaxiMedioDia de: 13:00 - 15:00 (AR)\n\n"
            f"▶️ <a href='{link_stream}'>CLICK PARA VER AHORA</a>"
        )
        if not imagen_url:
            imagen_url = "https://img.youtube.com/vi/live/maxresdefault.jpg"
        payload = {
            'chat_id': self.chat_id,
            'photo': imagen_url,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        try:
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code != 200:
                return self.enviar_texto(caption, disable_preview=False)
            return True
        except Exception as e:
            return self.enviar_texto(caption, disable_preview=False)

    def enviar_spotify(self, titulo, link_spotify, imagen_url=None, descripcion=""):
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        caption = (
            "🎙️ <b>Bloomberg Línea Argentina</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>{titulo}</b>\n\n"
            f"{descripcion[:200]}{'...' if len(descripcion) > 200 else ''}\n\n"
            f"🎧 <a href='{link_spotify}'>Escuchar en Spotify</a>"
        )
        if len(caption) > 1024:
            caption = caption[:1021] + "..."
        if not imagen_url:
            imagen_url = "https://storage.googleapis.com/spotifynewsroom/spotify-logo.png"
        payload = {
            'chat_id': self.chat_id,
            'photo': imagen_url,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        try:
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code != 200:
                return self.enviar_texto(caption, disable_preview=False)
            return True
        except Exception as e:
            return self.enviar_texto(caption, disable_preview=False)

# ============= GESTOR BSKY (JSON con cabeceras por cuenta) =============

class GestorHistorialBsky:
    """
    Historial de Bluesky organizado por cuenta.
    Archivo: last_id_bsky.json
    Estructura:
    {
        "TRENDSPIDER_BSKY": [
            "https://bsky.app/.../post/abc123",
            "https://bsky.app/.../post/def456",
            ...  (ultimas 15 URLs de esta cuenta)
        ],
        "BARCHART_BSKY": [
            "https://bsky.app/.../post/xyz789",
            ...
        ]
    }
    - Guarda las ultimas 15 URLs por cuenta
    - Al agregar la 16ta, descarta la mas vieja (la primera de la lista)
    - Identifica naturalmente cada post por su URL unica de Bluesky
    """
    ARCHIVO = "last_id_bsky.json"
    LIMITE_POR_CUENTA = 15

    def __init__(self):
        self.data = self._cargar()

    def _cargar(self):
        if not os.path.exists(self.ARCHIVO):
            print("📄 Creando nuevo last_id_bsky.json")
            return {}
        try:
            with open(self.ARCHIVO, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
                if not contenido:
                    print("📄 last_id_bsky.json vacío, iniciando nuevo")
                    return {}
                return json.loads(contenido)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON corrupto en last_id_bsky.json: {e} — iniciando nuevo")
            # Backup del archivo corrupto
            try:
                os.rename(self.ARCHIVO, f"{self.ARCHIVO}.backup")
            except:
                pass
            return {}
        except Exception as e:
            print(f"⚠️ Error cargando last_id_bsky.json: {e}")
            return {}

    def existe(self, nombre_feed, url):
        """Devuelve True si la URL ya fue enviada para esta cuenta"""
        lista = self.data.get(nombre_feed, [])
        return url in lista

    def agregar(self, nombre_feed, url):
        """
        Agrega la URL a la lista de esta cuenta.
        Si supera LIMITE_POR_CUENTA, descarta la mas vieja.
        """
        if nombre_feed not in self.data:
            self.data[nombre_feed] = []

        lista = self.data[nombre_feed]

        # No agregar duplicados
        if url in lista:
            return

        lista.append(url)  # agrega al final (mas reciente)

        # Si supera el limite, elimina el mas viejo (el primero)
        if len(lista) > self.LIMITE_POR_CUENTA:
            eliminado = lista.pop(0)
            print(f"🗑️ [{nombre_feed}] URL vieja eliminada del historial")

        self.data[nombre_feed] = lista

    def guardar(self):
        try:
            with open(self.ARCHIVO, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1, ensure_ascii=False)
            print(f"✅ last_id_bsky.json guardado ({sum(len(v) for v in self.data.values())} URLs en {len(self.data)} cuentas)")
        except Exception as e:
            print(f"❌ Error guardando last_id_bsky.json: {e}")

    def mostrar_estado(self):
        """Muestra un resumen del historial para los logs"""
        for cuenta, urls in self.data.items():
            print(f"   📋 {cuenta}: {len(urls)}/{self.LIMITE_POR_CUENTA} URLs guardadas")

# ============= GESTOR SIMPLE (para especiales, spotify, maxi) =============

class GestorHistorial:
    """
    Gestor simple de historial para archivos .txt
    Usado por: last_id_especial.txt, last_id_spotify.txt, ultimo_maxi.txt
    """
    LIMITE = 200

    def __init__(self, archivo):
        self.archivo = archivo
        self.datos = self._cargar()

    def _cargar(self):
        if os.path.exists(self.archivo):
            with open(self.archivo, "r") as f:
                items = [line.strip() for line in f if line.strip()]
                # Deduplicar manteniendo orden
                vistos = set()
                resultado = []
                for item in items:
                    if item not in vistos:
                        vistos.add(item)
                        resultado.append(item)
                return resultado
        return []

    def existe(self, item):
        return item in self.datos

    def agregar(self, item):
        if item not in self.datos:
            self.datos.append(item)

    def guardar(self):
        items_a_guardar = self.datos[-self.LIMITE:]
        with open(self.archivo, "w") as f:
            f.write("\n".join(items_a_guardar))

# ============= EXTRACTORES =============

def extraer_imagen_de_bsky(html_content):
    patrones = [
        r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*bsky-image[^"]*"',
        r'background-image:\s*url\(([^)]+)\)',
        r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|gif))"',
        r'"thumb":\s*"([^"]+)"'
    ]
    for patron in patrones:
        match = re.search(patron, html_content, re.IGNORECASE)
        if match:
            url = match.group(1).replace('&amp;', '&')
            if url.startswith('http'):
                return url
    return None

def obtener_link_stream_youtube():
    return "https://www.youtube.com/@Ahora_Play/streams"

# ============= MAIN =============

def main():
    print(f"🚀 Iniciando VISOR v2.3 - {datetime.now().strftime('%H:%M:%S')}")

    bot = TelegramBot()
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora_ar = datetime.now(tz_ar)
    fecha_hoy = ahora_ar.strftime("%Y-%m-%d")

    # 1. ALERTA AHORAPLAY!
    gestor_maxi = GestorHistorial("ultimo_maxi.txt")
    if ahora_ar.weekday() < 5 and ahora_ar.hour == 12:
        if not gestor_maxi.existe(fecha_hoy):
            link_stream = obtener_link_stream_youtube()
            imagen_mmd = "https://img.youtube.com/vi/live/maxresdefault.jpg"
            if bot.enviar_alerta_mmd(link_stream, imagen_mmd):
                gestor_maxi.agregar(fecha_hoy)
                gestor_maxi.guardar()
                print(f"✅ Alerta AHORAPLAY enviada: {fecha_hoy}")

    # 2. VISOR DE MERCADOS (10:00-19:00 AR)
    if ahora_ar.weekday() < 5 and 10 <= ahora_ar.hour <= 19:
        datos = obtener_datos_monitor()
        if bot.enviar_texto(datos, disable_preview=True):
            print("✅ Visor de mercados enviado")

    # 3. FEEDS BLUESKY — nuevo sistema JSON con cabeceras por cuenta
    gestor_bsky = GestorHistorialBsky()
    enviados_bsky = 0

    for nombre_feed, url_feed in FEEDS_BSKY.items():
        try:
            resp = requests.get(url_feed, timeout=30)
            feed = feedparser.parse(resp.content)

            nuevos_feed = 0
            for entrada in feed.entries[:3]:  # revisa los 3 mas recientes
                link = entrada.get('link', '').strip()
                if not link:
                    continue

                # Consulta el historial de ESTA cuenta especificamente
                if gestor_bsky.existe(nombre_feed, link):
                    print(f"⏭️ [{nombre_feed}] Ya enviado: {link.split('/')[-1]}")
                    continue

                titulo = entrada.get('title', '')
                desc = entrada.get('description', '')
                texto_limpio = re.sub(r'<[^>]+>', '', desc) or titulo
                texto_traducido = traducir_texto(texto_limpio)

                imagen_url = None
                if desc and '<img' in desc:
                    imagen_url = extraer_imagen_de_bsky(desc)
                if not imagen_url:
                    try:
                        resp_html = requests.get(link, timeout=10)
                        imagen_url = extraer_imagen_de_bsky(resp_html.text)
                    except:
                        pass

                if imagen_url:
                    exito = bot.enviar_foto_con_caption(imagen_url, texto_traducido, link)
                else:
                    emoji = "📊"
                    mensaje = (
                        f"{emoji} <b>{nombre_feed.replace('_', ' ')}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{texto_traducido}\n\n"
                        f"🔗 <a href='{link}'>Ver en Bluesky</a>"
                    )
                    exito = bot.enviar_texto(mensaje, disable_preview=False)

                if exito:
                    # Registra en el historial de ESTA cuenta
                    gestor_bsky.agregar(nombre_feed, link)
                    enviados_bsky += 1
                    nuevos_feed += 1
                    time.sleep(2)

            print(f"📡 [{nombre_feed}] {nuevos_feed} nuevos enviados")

        except Exception as e:
            print(f"⚠️ Error en {nombre_feed}: {e}")
            continue

    # Guardar siempre el JSON (aunque no haya nuevos, para mantener consistencia)
    gestor_bsky.guardar()
    gestor_bsky.mostrar_estado()
    if enviados_bsky > 0:
        print(f"✅ {enviados_bsky} posts de Bluesky procesados en total")

    # 4. AMBITO DOLAR
    gestor_especial = GestorHistorial("last_id_especial.txt")
    enviados_especial = 0

    for nombre, config in FEEDS_ESPECIALES.items():
        try:
            resp = requests.get(config['url'], timeout=30)
            feed = feedparser.parse(resp.content)

            for entrada in feed.entries[:5]:
                link = entrada.get('link', '').strip()
                if not link or gestor_especial.existe(link):
                    continue

                titulo = entrada.get('title', '')
                desc = entrada.get('description', '')
                texto_completo = f"{titulo} {desc}"
                texto_limpio = re.sub(r'<[^>]+>', '', texto_completo)
                texto_inicio = texto_limpio[:100].lower()

                contiene_apertura = "apertura de jornada" in texto_inicio
                contiene_cierre = "cierre de jornada" in texto_inicio

                if not (contiene_apertura or contiene_cierre):
                    print(f"⏭️ Saltando: no es apertura/cierre ({texto_limpio[:30]}...)")
                    continue

                tipo = "APERTURA" if contiene_apertura else "CIERRE"
                emoji = config.get('emoji', '💵')

                mensaje = (
                    f"{emoji} <b>Ambito Dolar - {tipo}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{texto_limpio[:500]}\n\n"
                    f"🔗 <a href='{link}'>Ver gráfico completo</a>"
                )

                if bot.enviar_texto(mensaje, disable_preview=False):
                    gestor_especial.agregar(link)
                    enviados_especial += 1
                    print(f"✅ Ambito {tipo} enviado")
                    time.sleep(1.5)

        except Exception as e:
            print(f"⚠️ Error en {nombre}: {e}")

    if enviados_especial > 0:
        gestor_especial.guardar()
        print(f"✅ {enviados_especial} posts de Ambito Dolar guardados en historial")

    # 5. SPOTIFY
    gestor_spotify = GestorHistorial("last_id_spotify.txt")
    enviados_spotify = 0

    for nombre, config in FEEDS_SPOTIFY.items():
        try:
            resp = requests.get(config['url_rss'], timeout=30)
            feed = feedparser.parse(resp.content)
            print(f"📦 Spotify feed: {len(feed.entries)} episodios encontrados")

            for entrada in feed.entries[:1]:
                ep_id = entrada.get('id', '') or entrada.get('link', '')
                if not ep_id or gestor_spotify.existe(ep_id):
                    print(f"⏭️ Spotify: episodio ya enviado anteriormente")
                    continue

                titulo = entrada.get('title', 'Sin título')
                link = entrada.get('link', config['url_base'])
                descripcion = re.sub(r'<[^>]+>', '', entrada.get('description', ''))

                imagen = None
                if 'image' in entrada:
                    imagen = entrada['image'].get('href') if isinstance(entrada['image'], dict) else entrada['image']
                elif 'itunes_image' in entrada:
                    imagen = entrada['itunes_image']
                if not imagen:
                    imagen = config.get('imagen_default')

                link_spotify = link if ('spotify.com' in link or 'podcasters' in link) else config['url_base']

                print(f"📤 Enviando Spotify: {titulo[:60]}...")
                if bot.enviar_spotify(titulo, link_spotify, imagen, descripcion):
                    gestor_spotify.agregar(ep_id)
                    enviados_spotify += 1
                    print(f"✅ Spotify enviado: {titulo[:50]}...")
                    time.sleep(2)

        except Exception as e:
            print(f"⚠️ Error Spotify: {e}")

    if enviados_spotify > 0:
        gestor_spotify.guardar()
        print(f"✅ {enviados_spotify} episodios de Spotify guardados en historial")

    print(f"🏁 Finalizado - {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
