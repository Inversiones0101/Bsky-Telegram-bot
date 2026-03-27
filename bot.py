#!/usr/bin/env python3
"""
Bsky-Telegram Bot - VISOR FINANCIERO MEJORADO v2.0
Con traducción, imágenes de Bluesky, Spotify y alertas visuales
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

# Traductor - instalar: pip install deep-translator
try:
    from deep_translator import GoogleTranslator
    TRADUCTOR_DISPONIBLE = True
except ImportError:
    TRADUCTOR_DISPONIBLE = False
    print("⚠️ deep-translator no instalado. Traducción desactivada.")

# ============= CONFIGURACIÓN =============

FEEDS_BSKY = {
    "TRENDSPIDER_BSKY": "https://bsky.app/profile/trendspider.com/rss",
    "BARCHART_BSKY": "https://bsky.app/profile/barchart.com/rss",
    "QUANTHUSTLE": "https://bsky.app/profile/quanthustle.bsky.social/rss",
    "EARNINGS_FORESIGHT": "https://bsky.app/profile/earningsforesight.bsky.social/rss",
    "CL_CODING": "https://bsky.app/profile/clcoding.bsky.social/rss"
}

# Feeds especiales (sin traducción, con filtros específicos)
FEEDS_ESPECIALES = {
    "AMBITO_DOLAR": {
        "url": "https://bsky.app/profile/ambitodolar.bsky.social/rss",
        "filtros": ["APERTURA", "CIERRE", "DOLAR", "BLUE", "MEP", "CCL"]
    }
}

# NUEVO: Feed de Spotify
FEEDS_SPOTIFY = {
    "BLOOMBERG_LINEA": {
        "nombre": "🎧 Bloomberg Línea Argentina",
        "url_rss": "https://anchor.fm/s/6d5f6e48/podcast/rss",  # RSS del podcast
        "url_base": "https://open.spotify.com/show/6d5f6e48",  # URL base del show
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
    """Traduce texto al español usando Google Translator"""
    if not TRADUCTOR_DISPONIBLE or not texto:
        return texto
    
    try:
        # Limitar texto para no sobrecargar la API
        texto_truncado = texto[:4000]
        traductor = GoogleTranslator(source='auto', target=destino)
        return traductor.translate(texto_truncado)
    except Exception as e:
        print(f"⚠️ Error traduciendo: {e}")
        return texto  # Fallback: texto original

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
                    valor_str = f"{precio:.2f}%"
                else:
                    valor_str = f"{precio:,.2f}"
                
                cambio_str = formatear_cambio(cambio)
                lineas.append(f"{emoji} <code>{nombre:<12}</code> <b>{valor_str:>10}</b>  {cambio_str}")
                
            except:
                continue
    
    lineas.append("\n━━━━━━━━━━━━━━━━━━━━━━━")
    hora_ar = datetime.now(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%H:%M")
    lineas.append(f"🕐 <i>Actualizado: {hora_ar} AR</i>")
    
    return "\n".join(lineas)

# ============= TELEGRAM MEJORADO =============

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.token or not self.chat_id:
            raise ValueError("Faltan credenciales de Telegram")

    def enviar_texto(self, texto, disable_preview=True):
        """Envía mensaje de texto simple"""
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
        """
        Envía foto con caption traducido.
        Si hay link de Bluesky, lo agrega al caption.
        """
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        
        # Preparar caption
        header = "📊 <b>Bluesky Feed</b>\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        footer = ""
        
        if link_bsky:
            footer = f"\n\n🔗 <a href='{link_bsky}'>Ver en Bluesky</a>"
        
        caption_completo = f"{header}{caption}{footer}"
        
        # Telegram limita caption a 1024 caracteres
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
            
            # Si falla por URL de foto inválida, enviar como texto
            if resp.status_code != 200:
                error_desc = resp.json().get('description', '')
                if "wrong file" in error_desc.lower() or "failed to get" in error_desc.lower():
                    print(f"⚠️ Foto inválida, enviando como texto")
                    return self.enviar_texto(caption_completo, disable_preview=False)
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error enviando foto: {e}")
            return False

    def enviar_alerta_mmd(self, link_stream, imagen_url=None):
        """
        Alerta de Maxi Mediodía con imagen y link directo al stream
        """
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        
        caption = (
            "🔔 <b>¡MAXI MEDIODÍA EN BREVE!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📺 <b>Transmisión en vivo:</b> 13:00 - 15:00 (AR)\n\n"
            f"▶️ <a href='{link_stream}'>CLICK PARA VER AHORA</a>"
        )
        
        # Imagen por defecto si no se provee una
        if not imagen_url:
            imagen_url = "https://img.youtube.com/vi/placeholder/maxresdefault.jpg"
        
        payload = {
            'chat_id': self.chat_id,
            'photo': imagen_url,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        try:
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code != 200:
                # Fallback a texto si la imagen falla
                return self.enviar_texto(caption, disable_preview=False)
            return True
        except Exception as e:
            print(f"❌ Error alerta MMD: {e}")
            return self.enviar_texto(caption, disable_preview=False)

    def enviar_spotify(self, titulo, link_spotify, imagen_url=None, descripcion=""):
        """Envía episodio de Spotify con imagen y link"""
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
        
        # Imagen por defecto de Spotify si no hay una
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
            print(f"❌ Error Spotify: {e}")
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
    """Extrae URL de imagen del HTML de Bluesky"""
    # Patrones comunes de imágenes en Bluesky
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
    """
    Obtiene el link DIRECTO al stream en vivo de @Ahora_Play
    Si no hay stream activo, devuelve el link del canal
    """
    try:
        # Intentar obtener stream activo via RSS de YouTube
        url_canal = "https://www.youtube.com/@Ahora_Play/streams"
        
        # Por ahora, devolvemos el link del canal (se puede mejorar con scraping)
        return "https://www.youtube.com/@Ahora_Play/streams"
        
    except:
        return "https://www.youtube.com/@Ahora_Play/streams"

# ============= MAIN =============

def main():
    print(f"🚀 Iniciando VISOR v2.0 - {datetime.now().strftime('%H:%M:%S')}")
    
    bot = TelegramBot()
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora_ar = datetime.now(tz_ar)
    fecha_hoy = ahora_ar.strftime("%Y-%m-%d")
    
    # 1. ALERTA MAXI MEDIODÍA (12:00-12:59 AR)
    gestor_maxi = GestorHistorial("ultimo_maxi.txt")
    
    if ahora_ar.weekday() < 5 and ahora_ar.hour == 12:
        if not gestor_maxi.existe(fecha_hoy):
            link_stream = obtener_link_stream_youtube()
            # Imagen de preview del programa (puedes cambiarla)
            imagen_mmd = "https://img.youtube.com/vi/live/maxresdefault.jpg"
            
            if bot.enviar_alerta_mmd(link_stream, imagen_mmd):
                gestor_maxi.agregar(fecha_hoy)
                gestor_maxi.guardar()
                print(f"✅ Alerta MMD enviada: {fecha_hoy}")
    
    # 2. VISOR DE MERCADOS (10:00-19:00 AR)
    if ahora_ar.weekday() < 5 and 10 <= ahora_ar.hour <= 19:
        datos = obtener_datos_monitor()
        if bot.enviar_texto(datos, disable_preview=True):
            print("✅ Visor de mercados enviado")
    
    # 3. FEEDS BLUESKY CON TRADUCCIÓN E IMÁGENES
    gestor_bsky = GestorHistorial("last_id_bsky.txt")
    enviados_bsky = 0
    
    for nombre_feed, url_feed in FEEDS_BSKY.items():
        try:
            resp = requests.get(url_feed, timeout=30)
            feed = feedparser.parse(resp.content)
            
            for entrada in feed.entries[:2]:  # Solo últimos 2
                link = entrada.get('link', '').strip()
                if not link or gestor_bsky.existe(link):
                    continue
                
                # Obtener contenido
                titulo = entrada.get('title', '')
                desc = entrada.get('description', '')
                
                # Limpiar HTML
                texto_limpio = re.sub(r'<[^>]+>', '', desc) or titulo
                
                # TRADUCIR al español
                texto_traducido = traducir_texto(texto_limpio)
                
                # Intentar obtener imagen del contenido HTML
                imagen_url = None
                if desc and '<img' in desc:
                    imagen_url = extraer_imagen_de_bsky(desc)
                
                # Si no hay imagen en descripción, intentar con el link
                if not imagen_url:
                    try:
                        resp_html = requests.get(link, timeout=10)
                        imagen_url = extraer_imagen_de_bsky(resp_html.text)
                    except:
                        pass
                
                # Enviar con foto si existe, si no como texto
                if imagen_url:
                    exito = bot.enviar_foto_con_caption(imagen_url, texto_traducido, link)
                else:
                    # Sin imagen: enviar como texto con link
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
    
    # 4. FEEDS ESPECIALES (sin traducción, con filtros)
    gestor_especial = GestorHistorial("last_id_especial.txt")
    
    for nombre, config in FEEDS_ESPECIALES.items():
        try:
            resp = requests.get(config['url'], timeout=30)
            feed = feedparser.parse(resp.content)
            
            for entrada in feed.entries[:3]:
                link = entrada.get('link', '').strip()
                if not link or gestor_especial.existe(link):
                    continue
                
                texto = re.sub(r'<[^>]+>', '', entrada.get('description', ''))
                
                # Filtro especial
                if not any(f in texto.upper() for f in config['filtros']):
                    continue
                
                # Sin traducir (es español)
                mensaje = (
                    f"💵 <b>Ambito Dolar</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{texto[:400]}\n\n"
                    f"🔗 <a href='{link}'>Ver en Bluesky</a>"
                )
                
                if bot.enviar_texto(mensaje, disable_preview=False):
                    gestor_especial.agregar(link)
                    time.sleep(1.5)
                    
        except Exception as e:
            print(f"⚠️ Error en {nombre}: {e}")
    
    # 5. SPOTIFY BLOOMBERG
    gestor_spotify = GestorHistorial("last_id_spotify.txt")
    
    for nombre, config in FEEDS_SPOTIFY.items():
        try:
            resp = requests.get(config['url_rss'], timeout=30)
            feed = feedparser.parse(resp.content)
            
            for entrada in feed.entries[:1]:  # Solo el más reciente
                # ID único del episodio
                ep_id = entrada.get('id', '') or entrada.get('link', '')
                if not ep_id or gestor_spotify.existe(ep_id):
                    continue
                
                titulo = entrada.get('title', 'Sin título')
                link = entrada.get('link', config['url_base'])
                descripcion = re.sub(r'<[^>]+>', '', entrada.get('description', ''))
                
                # Buscar imagen en el feed
                imagen = None
                if 'image' in entrada:
                    imagen = entrada['image'].get('href') if isinstance(entrada['image'], dict) else entrada['image']
                elif 'itunes_image' in entrada:
                    imagen = entrada['itunes_image']
                
                # Construir link directo a Spotify si es posible
                link_spotify = link if 'spotify.com' in link else config['url_base']
                
                if bot.enviar_spotify(titulo, link_spotify, imagen, descripcion):
                    gestor_spotify.agregar(ep_id)
                    print(f"✅ Spotify enviado: {titulo[:50]}...")
                    time.sleep(2)
                    
        except Exception as e:
            print(f"⚠️ Error Spotify: {e}")
    
    print(f"🏁 Finalizado - {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
