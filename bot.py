#!/usr/bin/env python3
"""
Bsky-Telegram Bot - VISOR FINANCIERO v2.1
Corregido: Filtro Ambito Dolar, visor alineado, alerta MMD renombrada
"""
import os
import sys
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
    "CL_CODING": "https://bsky.app/profile/clcoding.bsky.social/rss"
}

# AMBITO DOLAR - Filtro específico para "Apertura de jornada" y "Cierre de jornada"
FEEDS_ESPECIALES = {
    "AMBITO_DOLAR": {
        "url": "https://bsky.app/profile/ambitodolar.bsky.social/rss",
        "filtros_exactos": ["Apertura de jornada", "Cierre de jornada"],  # ← Filtros exactos
        "emoji": "💵"
    }
}

FEEDS_SPOTIFY = {
    "BLOOMBERG_LINEA": {
        "nombre": "🎧 Bloomberg Línea Argentina",
        "url_rss": "https://anchor.fm/s/6d5f6e48/podcast/rss",
        "url_base": "https://open.spotify.com/show/6d5f6e48",
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
    """
    Visor de mercados con indicadores alineados verticalmente
    Formato: [EMOJI] [INDICADOR] [NOMBRE] [PRECIO ALINEADO] [VARIACIÓN]
    """
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
                
                # Formato especial para Tasa 10Y
                if ticker == "^TNX":
                    precio_str = f"{precio:.2f}%"
                else:
                    precio_str = f"{precio:,.2f}"
                
                # NUEVO: Indicador alineado al inicio, precio alineado a la derecha
                indicador = "🟢" if cambio >= 0 else "🔴"
                cambio_str = f"{cambio:+.2f}%"
                
                # Formato alineado: Emoji Indicador | Nombre | Precio | Variación
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
        """
        Alerta renombrada: AHORAPLAY! en lugar de MAXI MEDIODÍA
        """
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        
        # NUEVO: Texto renombrado según solicitud
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

# ============= GESTORES =============

class GestorHistorial:
    def __init__(self, archivo):
        self.archivo = archivo
        self.datos = self._cargar()
    
    def _cargar(self):
        if os.path.exists(self.archivo):
            with open(self.archivo, "r") as f:
                return set(line.strip() for line in f if line.strip())
        return set()
    
    def existe(self, item):
        return item in self.datos
    
    def agregar(self, item):
        self.datos.add(item)
    
    def guardar(self):
        with open(self.archivo, "w") as f:
            f.write("\n".join(sorted(self.datos)[-150:]))

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
    print(f"🚀 Iniciando VISOR v2.1 - {datetime.now().strftime('%H:%M:%S')}")
    
    bot = TelegramBot()
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora_ar = datetime.now(tz_ar)
    fecha_hoy = ahora_ar.strftime("%Y-%m-%d")
    
    # 1. ALERTA AHORAPLAY! (antes MMD)
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
    
    # 3. FEEDS BLUESKY CON TRADUCCIÓN
    gestor_bsky = GestorHistorial("last_id_bsky.txt")
    enviados_bsky = 0
    
    for nombre_feed, url_feed in FEEDS_BSKY.items():
        try:
            resp = requests.get(url_feed, timeout=30)
            feed = feedparser.parse(resp.content)
            
            for entrada in feed.entries[:2]:
                link = entrada.get('link', '').strip()
                if not link or gestor_bsky.existe(link):
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
                    gestor_bsky.agregar(link)
                    enviados_bsky += 1
                    time.sleep(2)
                    
        except Exception as e:
            print(f"⚠️ Error en {nombre_feed}: {e}")
            continue
    
    if enviados_bsky > 0:
        gestor_bsky.guardar()
        print(f"✅ {enviados_bsky} posts de Bluesky procesados")
    
    # 4. AMBITO DOLAR - Filtro exacto para "Apertura de jornada" y "Cierre de jornada"
    gestor_especial = GestorHistorial("last_id_especial.txt")
    
    for nombre, config in FEEDS_ESPECIALES.items():
        try:
            resp = requests.get(config['url'], timeout=30)
            feed = feedparser.parse(resp.content)
            
            for entrada in feed.entries[:5]:  # Revisar más porque filtramos
                link = entrada.get('link', '').strip()
                if not link or gestor_especial.existe(link):
                    continue
                
                # Obtener texto completo
                titulo = entrada.get('title', '')
                desc = entrada.get('description', '')
                texto_completo = f"{titulo} {desc}"
                texto_limpio = re.sub(r'<[^>]+>', '', texto_completo)
                
                # NUEVO: Filtro exacto para "Apertura de jornada" o "Cierre de jornada"
                # Buscar al inicio del texto (donde suele estar)
                texto_inicio = texto_limpio[:100].lower()
                
                contiene_apertura = "apertura de jornada" in texto_inicio
                contiene_cierre = "cierre de jornada" in texto_inicio
                
                if not (contiene_apertura or contiene_cierre):
                    print(f"⏭️ Saltando: no es apertura/cierre ({texto_limpio[:30]}...)")
                    continue
                
                # Determinar qué tipo es para el mensaje
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
                    print(f"✅ Ambito {tipo} enviado")
                    time.sleep(1.5)
                    
        except Exception as e:
            print(f"⚠️ Error en {nombre}: {e}")
    
    # 5. SPOTIFY
    gestor_spotify = GestorHistorial("last_id_spotify.txt")
    
    for nombre, config in FEEDS_SPOTIFY.items():
        try:
            resp = requests.get(config['url_rss'], timeout=30)
            feed = feedparser.parse(resp.content)
            
            for entrada in feed.entries[:1]:
                ep_id = entrada.get('id', '') or entrada.get('link', '')
                if not ep_id or gestor_spotify.existe(ep_id):
                    continue
                
                titulo = entrada.get('title', 'Sin título')
                link = entrada.get('link', config['url_base'])
                descripcion = re.sub(r'<[^>]+>', '', entrada.get('description', ''))
                
                imagen = None
                if 'image' in entrada:
                    imagen = entrada['image'].get('href') if isinstance(entrada['image'], dict) else entrada['image']
                elif 'itunes_image' in entrada:
                    imagen = entrada['itunes_image']
                
                link_spotify = link if 'spotify.com' in link else config['url_base']
                
                if bot.enviar_spotify(titulo, link_spotify, imagen, descripcion):
                    gestor_spotify.agregar(ep_id)
                    print(f"✅ Spotify: {titulo[:50]}...")
                    time.sleep(2)
                    
        except Exception as e:
            print(f"⚠️ Error Spotify: {e}")
    
    print(f"🏁 Finalizado - {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
