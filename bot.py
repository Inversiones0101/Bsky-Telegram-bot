import os
import feedparser
import requests
import time
import re
import yfinance as yf
from datetime import datetime
import pytz

# --- CONFIGURACIÓN DE FEEDS ---
FEEDS = {
    "AMBITO_DOLAR": "https://bsky.app/profile/ambitodolar.bsky.social/rss",
    "TRENDSPIDER_BSKY": "https://bsky.app/profile/trendspider.com/rss",
    "BARCHART_BSKY": "https://bsky.app/profile/barchart.com/rss",
    "QUANTHUSTLE": "https://bsky.app/profile/quanthustle.bsky.social/rss",
    "EARNINGS_FORESIGHT": "https://bsky.app/profile/earningsforesight.bsky.social/rss",
    "CL_CODING": "https://bsky.app/profile/clcoding.bsky.social/rss"
}

# --- CONFIGURACIÓN DE ACTIVOS ---
MARKETS = {
    "WALL_STREET": {
        "^SPX": "S&P 500", 
        "^DJI": "Dow Jones", 
        "^IXIC": "NASDAQ", 
        "^VIX": "VIX", 
        "^TNX": "Tasa 10Y"
    },
    "COMMODITIES": {
        "GC=F": "Gold", 
        "ZS=F": "Soja", 
        "CL=F": "Oil", 
        "SI=F": "Silver"
    },
    "CRYPTOS": {
        "BTC-USD": "BTC", 
        "ETH-USD": "ETH", 
        "SOL-USD": "SOL"
    }
}

def esta_abierto_wall_street():
    tz_ny = pytz.timezone('America/New_York')
    ahora_ny = datetime.now(tz_ny)
    if ahora_ny.weekday() >= 5: return False 
    apertura = ahora_ny.replace(hour=9, minute=30, second=0, microsecond=0)
    cierre = ahora_ny.replace(hour=16, minute=0, second=0, microsecond=0)
    return apertura <= ahora_ny <= cierre

def obtener_datos_monitor():
    lineas = ["🔭 <b>VISOR</b>", "━━━━━━━━━━━━━━"]
    abierto = esta_abierto_wall_street()
    estado_ws = "🟢 <b>ABIERTO</b>" if abierto else "🔴 <b>CERRADO</b>"
    lineas.append(f"\n🇺🇸 <b>VISOR USA:</b> {estado_ws}")
    
    for seccion, activos in MARKETS.items():
        if seccion != "WALL_STREET":
            emoji = "🧱" if seccion == "COMMODITIES" else "🪙"
            lineas.append(f"\n{emoji} <b>{seccion}:</b> 🟢 <b>ABIERTO</b>")
        for ticker, nombre in activos.items():
            try:
                val = yf.Ticker(ticker).history(period="5d")
                if len(val) < 2: continue
                precio = val['Close'].iloc[-1]
                cambio = ((precio / val['Close'].iloc[-2]) - 1) * 100
                color = "🟢" if cambio >= 0 else "🔴"
                formato = f"{precio:.2f}%" if ticker == "^TNX" else f"{precio:,.2f}"
                lineas.append(f"{color} <b>{nombre}:</b> <code>{formato} ({cambio:+.2f}%)</code>")
            except: continue
    return "\n".join(lineas)

def enviar_telegram(titulo, link, fuente):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not link:
        mensaje = f"🔭 <b>{fuente}</b>\n━━━━━━━━━━━━━━\n{titulo}"
        disable_preview = True
    else:
        mensaje = f"🎯 <b>{fuente}</b>\n━━━━━━━━━━━━━━\n📝 {titulo}\n\n🔗 {link}"
        disable_preview = False 
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'HTML', 'disable_web_page_preview': disable_preview}
    requests.post(url, json=payload, timeout=25)

def main():
    print("🚀 Ejecutando Visor...")
    tz_ar = pytz.timezone('America/Argentina/Buenos_Aires')
    ahora_ar = datetime.now(tz_ar)
    fecha_hoy = ahora_ar.strftime("%Y-%m-%d")
    
    
    # 1. LÓGICA YUOTUBE
    archivo_envio = "ultimo_maxi.txt"
    ultimo_envio = ""
    if os.path.exists(archivo_envio):
        with open(archivo_envio, "r") as f: ultimo_envio = f.read().strip()

    # CAMBIO 1: Rango horario de 12:00 a 12:59 (hora Argentina)
    # Así el mensaje llega PREVIO al inicio de las 13:00hs
    if ahora_ar.weekday() < 5 and ahora_ar.hour == 12:
        if ultimo_envio != fecha_hoy:
            # CAMBIO 2: Enlace directo a la transmisión de hoy
            msg_maxi = (
                "🔔 <b>¡PRÓXIMAMENTE: MAXI MEDIODÍA!</b>\n"
                "━━━━━━━━━━━━━━\n"
                "📺 <b>Ver Programa en Vivo:</b> https://www.youtube.com/@Ahora_Play/streams"
            )
            enviar_telegram(msg_maxi, None, "ALERTA MMD")
            
            # CAMBIO 3: Guardado inmediato para BLOQUEAR repeticiones
            with open(archivo_envio, "w") as f: f.write(fecha_hoy)
            print(f"✅ Alerta MMD programada enviada para {fecha_hoy}")


    # 2. LÓGICA DEL VISOR
    if ahora_ar.weekday() < 5 and 10 <= ahora_ar.hour <= 19:
        enviar_telegram(obtener_datos_monitor(), None, "Fuente: yfinance")

    # 3. LÓGICA DE FEEDS BLUESKY
    archivo_h = "last_id_inicio.txt"
    historial = set()
    if os.path.exists(archivo_h):
        with open(archivo_h, "r") as f: historial = set(f.read().splitlines())

    nuevos_links = []
    for nombre, url in FEEDS.items():
        try:
            feed = feedparser.parse(requests.get(url, timeout=30).content)
            for entrada in reversed(feed.entries[:5]):
                link = entrada.get('link')
                if link and link not in historial:
                    desc = entrada.get('description', entrada.get('title', ''))
                    texto_limpio = re.sub(r'<[^>]+>', '', desc)
                    
                    if nombre == "AMBITO_DOLAR":
                        if "APERTURA" in texto_limpio.upper() or "CIERRE" in texto_limpio.upper():
                            enviar_telegram(texto_limpio[:450], link, nombre)
                    else:
                        enviar_telegram(texto_limpio[:450], link, nombre)
                    
                    historial.add(link)
                    nuevos_links.append(link)
                    time.sleep(1)
        except: continue
    
    # GUARDADO FINAL DE SEGURIDAD (Esto asegura que el archivo se actualice)
    if nuevos_links:
        with open(archivo_h, "a") as f:
            for l in nuevos_links:
                f.write(l + "\n")
        print(f"✅ Memoria actualizada con {len(nuevos_links)} nuevos links.")

if __name__ == "__main__":
    main()
