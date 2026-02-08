import streamlit as st
import yfinance as yf
import pandas_ta as ta
import pandas as pd
import plotly.graph_objects as go
import requests
from io import StringIO
import time

# --- CONFIGURATIE ---
st.set_page_config(page_title="Pure Giannino Sniper", layout="wide")

@st.cache_data(ttl=3600)
def get_all_tickers():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        sp500 = pd.read_html(StringIO(requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", headers=headers).text))[0]['Symbol'].tolist()
        nasdaq = pd.read_html(StringIO(requests.get("https://en.wikipedia.org/wiki/Nasdaq-100", headers=headers).text))[4]['Ticker'].tolist()
        return sorted(list(set([t.replace('.', '-') for t in sp500 + nasdaq])))
    except:
        return ["AAPL", "MSFT", "NVDA", "AMD", "TSLA", "AMZN", "META", "GOOGL"]

def get_pure_giannino_score(ticker, spy_perf_5d):
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False, timeout=5)
        if df is None or df.empty or len(df) < 100:
            return None
        
        c = df['Close'].squeeze()
        h = df['High'].squeeze()
        l = df['Low'].squeeze()
        o = df['Open'].squeeze()
        
        # Laatste twee kaarsen voor de 3-Bar Play analyse
        today = {"h": float(h.iloc[-1]), "l": float(l.iloc[-1]), "c": float(c.iloc[-1]), "o": float(o.iloc[-1])}
        yesterday = {"h": float(h.iloc[-2]), "l": float(l.iloc[-2]), "c": float(c.iloc[-2]), "o": float(o.iloc[-2])}
        
        # 1. GIANNINO CRITERIUM: De 'Baby Bar' Locatie
        # De low van vandaag moet boven het midden van gisteren liggen
        yesterday_midpoint = yesterday['l'] + (yesterday['h'] - yesterday['l']) / 2
        is_high_and_tight = today['l'] >= yesterday_midpoint
        
        # 2. GIANNINO CRITERIUM: De Range Contractie
        today_range = today['h'] - today['l']
        yesterday_range = yesterday['h'] - yesterday['l']
        is_tight = today_range < (yesterday_range * 0.7)
        
        # 3. TREND & RELATIVE STRENGTH
        stock_perf_5d = float(c.pct_change(5).iloc[-1])
        ma50 = ta.sma(c, 50).iloc[-1]
        
        score = 0
        signals = []
        
        if is_high_and_tight: 
            score += 3 # Dit is de belangrijkste factor voor de setup
            signals.append("Giannino: Baby Bar in upper 50%")
        if is_tight: 
            score += 2
            signals.append("Contractie: Tight Resting Bar")
        if stock_perf_5d > spy_perf_5d: 
            score += 2
            signals.append("RS: Sterker dan Markt")
        if today['c'] > ma50: 
            score += 1
            signals.append("Trend: Boven MA50")

        return {
            "Ticker": ticker,
            "Score": score,
            "Price": round(today['c'], 2),
            "RS_Val": stock_perf_5d,
            "Signals": signals,
            "DF": df
        }
    except:
        return None

# --- UI ---
st.title("🏹 Pure Giannino 3-Bar Sniper")
st.markdown("Zoekt naar de 'Baby Bar' in de bovenste helft van de vorige kaars — de perfecte 'Bullish Rest'.")

with st.sidebar:
    spy = yf.download("SPY", period="1y", interval="1d", progress=False)
    spy_perf_5d = float(spy['Close'].squeeze().pct_change(5).iloc[-1])
    max_scan = st.slider("Aantal aandelen", 50, 500, 200)

if st.button("Start Sniper Scan"):
    tickers = get_all_tickers()[:max_scan]
    results = []
    
    progress = st.progress(0)
    for i, t in enumerate(tickers):
        res = get_pure_giannino_score(t, spy_perf_5d)
        if res and res['Score'] >= 5: # Focus op setups die ècht kloppen
            results.append(res)
        progress.progress((i + 1) / len(tickers))

    if results:
        # Top 5 gebaseerd op de hoogste 'Giannino Score' en dan RS
        top_5 = sorted(results, key=lambda x: (x['Score'], x['RS_Val']), reverse=True)[:5]
        
        for idx, item in enumerate(top_5):
            with st.container(border=True):
                col1, col2, col3 = st.columns([0.5, 2, 3])
                with col1:
                    st.title(f"#{idx+1}")
                with col2:
                    st.subheader(item['Ticker'])
                    st.write(f"Score: **{item['Score']}/8**")
                    for s in item['Signals']: st.markdown(f"✅ <small>{s}</small>", unsafe_allow_html=True)
                    st.link_button("Grafiek ↗️", f"https://www.tradingview.com/chart/?symbol={item['Ticker']}")
                with col3:
                    df_p = item['DF'].tail(30)
                    fig = go.Figure(data=[go.Candlestick(x=df_p.index, open=df_p['Open'], high=df_p['High'], low=df_p['Low'], close=df_p['Close'])])
                    fig.update_layout(height=200, margin=dict(l=0,r=0,b=0,t=0), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, width='stretch')
    else:
        st.warning("Geen pure 'High & Tight' setups gevonden. Geduld is winst.")