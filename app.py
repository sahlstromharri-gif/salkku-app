import streamlit as st
import pandas as pd
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
import os.path
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Määritetään kansionpolku, jossa app.py ja credentials.json sijaitsevat
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')

# Sivun asetukset (Vaalea teema ja zebra-ikoni)
st.set_page_config(
    page_title="Zebran Salkku",
    page_icon="🦓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Selkeä vaalea tyylittely mobiilille ja työpöydälle
st.markdown("""
    <style>
    .stMain {
        background-color: #f8f9fa;
    }
    .news-card {
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #d0d7de;
        background-color: #ffffff;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .news-title {
        font-size: 16px;
        font-weight: 600;
        color: #0969da;
        text-decoration: none;
    }
    .news-meta {
        font-size: 12px;
        color: #57606a;
        margin-top: 5px;
    }
    .news-date {
        float: right;
        font-size: 12px;
        color: #9a6700;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# Watchlistin osakkeet
WATCHLIST = {
    "Teknologia & Chipit": ["NVDA", "MU", "ACLS", "CANATU.HE", "NOKIA.HE", "NOK", "LDSK.HE"],
    "LiDAR & Erikois": ["OUST"],
    "Kiinteistöt & Pankit": ["DX", "SAMPO.HE", "AKTIA.HE"],
    "Teollisuus & Kulutus": ["UPM.HE", "PUUILO.HE", "HARVIA.HE", "VALMT.HE"]
}

all_symbols = [symbol for category in WATCHLIST.values() for symbol in category]

# Kuva ja otsikko vierekkäin sarakkeilla (kuva vasemmalla, otsikko oikealla)
col_img, col_title = st.columns([1, 8])

with col_img:
    if os.path.exists(os.path.join(BASE_DIR, "Zebra.png")):
        st.image(os.path.join(BASE_DIR, "Zebra.png"), width=120)

with col_title:
    st.markdown("<h1 style='padding-top: 25px;'>Zebran Salkku</h1>", unsafe_allow_html=True)

# Luodaan kolme välilehteä
tab_news, tab_charts, tab_tech = st.tabs(["📰 Uutisvahti & Gmail", "📈 Kurssit & Analyytikot", "📊 Tekniset Indikaattorit"])

# ==========================================
# VÄLILEHTI 1: UUTISVAHTI & GMAIL
# ==========================================
with tab_news:
    st.markdown("Seuraa suosikkiosakkeidesi tuoreimpia uutisia, kotimaisia lähteitä sekä Nordnetin Aamukirjeitä.")

    selected_stocks_news = st.multiselect(
        "Suodata uutisia osakkeiden mukaan (jätä tyhjäksi nähdäksesi kaikki):",
        options=all_symbols,
        default=[],
        key="news_filter"
    )

    active_symbols_news = selected_stocks_news if selected_stocks_news else all_symbols

    @st.cache_data(ttl=600)
    def fetch_all_news(symbols):
        news_list = []
        
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                raw_news = ticker.news
                if raw_news:
                    for item in raw_news:
                        title = item.get("title") or item.get("content", {}).get("title", "Ei otsikkoa")
                        url = item.get("link") or item.get("content", {}).get("clickThroughUrl", {}).get("url", "#")
                        publisher = item.get("publisher") or item.get("content", {}).get("provider", {}).get("displayName", "Yahoo Finance")
                        
                        pub_time = "Tuore uutinen"
                        for key in ["providerPublishTime", "pubDate", "date"]:
                            val = item.get(key) or item.get("content", {}).get(key)
                            if val:
                                if isinstance(val, (int, float)):
                                    try:
                                        pub_time = datetime.fromtimestamp(val).strftime("%Y-%m-%d %H:%M")
                                        break
                                    except Exception:
                                        pass
                                elif isinstance(val, str) and len(val) >= 10:
                                    pub_time = val[:10]
                                    break
                        
                        news_list.append({
                            "source_type": "Markkinat (YF)",
                            "symbol": symbol,
                            "title": title,
                            "url": url,
                            "publisher": publisher,
                            "date": pub_time
                        })
            except Exception:
                continue

        search_terms = {
            "CANATU.HE": "Canatu",
            "NOKIA.HE": "Nokia",
            "NOK": "Nokia",
            "SAMPO.HE": "Sampo",
            "UPM.HE": "UPM",
            "PUUILO.HE": "Puuilo",
            "HARVIA.HE": "Harvia",
            "AKTIA.HE": "Aktia",
            "VALMT.HE": "Valmet",
            "LDSK.HE": "LeadDesk",
            "NVDA": "Nvidia",
            "MU": "Micron",
            "ACLS": "Axcelis",
            "OUST": "Ouster",
            "DX": "Dynex"
        }

        for symbol in symbols:
            term = search_terms.get(symbol, symbol)
            rss_url = f"https://news.google.com/rss/search?q={term}+site:arvopaperi.fi+OR+site:kauppalehti.fi&hl=fi&gl=FI&ceid=FI:fi"
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:3]:
                    news_list.append({
                        "source_type": "Kotimainen talousmedia",
                        "symbol": symbol,
                        "title": entry.title,
                        "url": entry.link,
                        "publisher": "Arvopaperi / Kauppalehti",
                        "date": entry.published[:16] if hasattr(entry, "published") else "Kotimainen"
                    })
            except Exception:
                continue

        SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
        creds = None
        
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)
                
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            elif os.path.exists(CREDENTIALS_PATH):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(TOKEN_PATH, 'wb') as token:
                        pickle.dump(creds, token)
                except Exception:
                    creds = None

        if creds and creds.valid:
            try:
                service = build('gmail', 'v1', credentials=creds)
                query_str = 'from:hei@mail.nordnet.fi Aamukirje'
                results = service.users().messages().list(userId='me', q=query_str, maxResults=10).execute()
                messages = results.get('messages', [])
                
                for msg in messages:
                    txt = service.users().messages().get(userId='me', id=msg['id']).execute()
                    headers = txt.get('payload', {}).get('headers', [])
                    
                    subject = "Nordnet Aamukirje"
                    date_val = "Sähköposti"
                    for h in headers:
                        if h['name'] == 'Subject':
                            subject = h['value']
                        if h['name'] == 'Date':
                            date_val = h['value'][:16]
                            
                    gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{msg['id']}"
                    
                    news_list.append({
                        "source_type": "Gmail (Nordnet)",
                        "symbol": "Salkku / Yleinen",
                        "title": f"📧 {subject}",
                        "url": gmail_url,
                        "publisher": "Nordnet Aamukirje",
                        "date": date_val
                    })
            except Exception:
                pass

        return pd.DataFrame(news_list)

    with st.spinner("Haetaan tuoreimpia uutisia, kotimaisia lähteitä ja Nordnetin sähköposteja..."):
        news_df = fetch_all_news(active_symbols_news)

    if not news_df.empty:
        st.subheader(f"Ajankohtaiset uutiset ja aamukirjeet ({len(news_df)} kpl)")
        for _, row in news_df.iterrows():
            st.markdown(f"""
                <div class="news-card">
                    <span class="news-date">📅 {row['date']}</span>
                    <a class="news-title" href="{row['url']}" target="_blank">{row['title']}</a>
                    <div class="news-meta">
                        <b>{row['symbol']}</b> | Tyyppi: {row['source_type']} | Lähde: {row['publisher']}
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Ei uutisia saatavilla valituille osakkeille tällä hetkellä.")


# ==========================================
# VÄLILEHTI 2: KURSSIKEHITYS & ANALYYTIKOT
# ==========================================
with tab_charts:
    st.markdown("Valitse osakkeet ja kalenteriaika. Kurssikehitys lasketaan kalenteripäivien mukaisesti.")

    col1, col2 = st.columns([2, 1])

    with col1:
        chart_stocks = st.multiselect(
            "Valitse osakkeet vertailuun:",
            options=all_symbols,
            default=["NVDA", "NOKIA.HE"],
            key="chart_stocks_select"
        )

    with col2:
        period_days = {
            "7 päivää": 7,
            "30 päivää": 30,
            "90 päivää": 90,
            "180 päivää": 180,
            "360 päivää": 360,
            "2 vuotta": 730,
            "3 vuotta": 1095,
            "5 vuotta": 1825
        }
        selected_period_label = st.selectbox("Valitse aikajakso:", options=list(period_days.keys()), index=1)
        days_back = period_days[selected_period_label]

    if chart_stocks:
        end_date = datetime.today()
        start_date = end_date - timedelta(days=days_back)

        @st.cache_data(ttl=3600)
        def fetch_calendar_data(symbols, start, end):
            data_frames = {}
            for symbol in symbols:
                try:
                    df = yf.download(symbol, start=start.strftime('%Y-%m-%d'), end=end.strftime('%Y-%m-%d'), progress=False)
                    if not df.empty:
                        if isinstance(df.columns, pd.MultiIndex):
                            close_series = df[('Close', symbol)]
                        else:
                            close_series = df['Close']
                        data_frames[symbol] = close_series.squeeze()
                except Exception:
                    continue
            return pd.DataFrame(data_frames)

        with st.spinner("Ladataan kurssihistoriaa kalenteriajan mukaan..."):
            price_df = fetch_calendar_data(chart_stocks, start_date, end_date)

        if not price_df.empty:
            price_df = price_df.dropna()
            if not price_df.empty:
                perf_df = ((price_df / price_df.iloc[0]) - 1) * 100

                st.subheader(f"Kurssikehitys (%): {selected_period_label}")
                st.line_chart(perf_df)

                summary_data = []

                for symbol in chart_stocks:
                    if symbol in price_df.columns:
                        series = price_df[symbol].dropna()
                        if not series.empty:
                            latest_price = float(series.iloc[-1])
                            start_price = float(series.iloc[0])
                            change_pct = ((latest_price / start_price) - 1) * 100
                            
                            currency = "€" in symbol or ".HE" in symbol and "€" or "$"
                            if ".HE" in symbol:
                                currency = "€"

                            summary_data.append({
                                "Osake": symbol,
                                f"Kurssi ({currency})": round(latest_price, 2),
                                "Muutos %": round(change_pct, 2)
                            })

                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    st.markdown("### 📋 Yhteenveto & Kurssikehitys")
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)

            else:
                st.warning("Valitulla aikajaksolla ei löytynyt riittävästi yhteisiä hintatietoja.")
        else:
            st.warning("Historiatietojen haku epäonnistui valituille osakkeille.")
    else:
        st.info("Valitse vähintään yksi osake yllä olevasta valikosta nähdäksesi kaavion ja kurssitiedot.")


# ==========================================
# VÄLILEHTI 3: TEKNISET INDIKAATTORIT
# ==========================================
with tab_tech:
    st.markdown("📊 **Tekninen analyysi: Kynttiläkaaviot & Indikaattorit**")
    st.markdown("Kaikki keskeiset indikaattorit on jaettu omille selkeille kaavioilleen.")

    tech_stock = st.selectbox("Valitse osake tekniseen analyysiin:", options=all_symbols, key="tech_stock_select")

    if tech_stock:
        currency = "€" if ".HE" in tech_stock else "$"
        
        @st.cache_data(ttl=3600)
        def fetch_full_tech_data(symbol):
            df = yf.download(symbol, period="2y", progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [col[0] for col in df.columns]
                return df
            return pd.DataFrame()

        with st.spinner(f"Ladataan kynttilädataa ja lasketaan indikaattoreita osakkeelle {tech_stock}..."):
            df_full = fetch_full_tech_data(tech_stock)

        if not df_full.empty and len(df_full) > 200:
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if all(col in df_full.columns for col in required_cols):
                
                df_full['SMA 50'] = df_full['Close'].rolling(window=50).mean()
                df_full['SMA 200'] = df_full['Close'].rolling(window=200).mean()

                r_mean = df_full['Close'].rolling(window=20).mean()
                r_std = df_full['Close'].rolling(window=20).std()
                df_full['Bollinger Keskiarvo'] = r_mean
                df_full['Bollinger Ylä'] = r_mean + (r_std * 2)
                df_full['Bollinger Ala'] = r_mean - (r_std * 2)

                delta = df_full['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df_full['RSI'] = 100 - (100 / (1 + rs))

                exp1 = df_full['Close'].ewm(span=12, adjust=False).mean()
                exp2 = df_full['Close'].ewm(span=26, adjust=False).mean()
                df_full['MACD'] = exp1 - exp2
                df_full['MACD Signal'] = df_full['MACD'].ewm(span=9, adjust=False).mean()
                df_full['MACD Hist'] = df_full['MACD'] - df_full['MACD Signal']

                one_year_ago = datetime.today() - timedelta(days=365)
                df = df_full[df_full.index >= pd.Timestamp(one_year_ago)].copy()

                latest_price = float(df_full['Close'].iloc[-1])
                latest_rsi = float(df_full['RSI'].iloc[-1]) if not pd.isna(df_full['RSI'].iloc[-1]) else 50.0
                latest_sma50 = float(df_full['SMA 50'].iloc[-1]) if not pd.isna(df_full['SMA 50'].iloc[-1]) else latest_price

                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.metric(label="Viimeisin kurssi", value=f"{round(latest_price, 2)} {currency}")
                with col_m2:
                    rsi_status = "Yliostettu (>70)" if latest_rsi > 70 else ("Ylimyyty (<30)" if latest_rsi < 30 else "Neutraali")
                    st.metric(label="RSI (14)", value=f"{round(latest_rsi, 1)}", delta=rsi_status)
                with col_m3:
                    trend_status = "Nouseva (SMA 50 yläpuolella)" if latest_price > latest_sma50 else "Laskeva (SMA 50 alapuolella)"
                    st.metric(label="Trendi (SMA 50)", value=f"{round(latest_sma50, 2)} {currency}", delta=trend_status)

                st.markdown("---")

                # 1. KYNTTILÄKAAVIO & LIUKUVAT KESKIARVOT
                st.subheader(f"1. Kynttiläkaavio & Liukuvat keskiarvot: {tech_stock}")
                fig_candlestick = go.Figure(data=[
                    go.Candlestick(
                        x=df.index,
                        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                        name="Kynttilät"
                    ),
                    go.Scatter(x=df.index, y=df['SMA 50'], line=dict(color='red', width=1.5), name="SMA 50"),
                    go.Scatter(x=df.index, y=df['SMA 200'], line=dict(color='dodgerblue', width=1.5), name="SMA 200")
                ])
                fig_candlestick.update_layout(template="plotly_white", height=450, xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_candlestick, use_container_width=True)

                # 2. KAUPANKÄYNTIVOLYYMI
                st.subheader("2. Kaupankäyntivolyymi")
                fig_vol = go.Figure(data=[
                    go.Bar(x=df.index, y=df['Volume'], marker_color='dimgray', name="Volyymi")
                ])
                fig_vol.update_layout(template="plotly_white", height=250, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_vol, use_container_width=True)

                # 3. BOLLINGERIN NAUHAT
                st.subheader("3. Bollingerin nauhat (20 pvl, 2σ)")
                fig_bb = go.Figure(data=[
                    go.Scatter(x=df.index, y=df['Bollinger Ylä'], line=dict(color='gray', width=1, dash='dash'), name="Yläreuna"),
                    go.Scatter(x=df.index, y=df['Bollinger Keskiarvo'], line=dict(color='darkorange', width=1), name="Keskiarvo (SMA 20)"),
                    go.Scatter(x=df.index, y=df['Bollinger Ala'], line=dict(color='gray', width=1, dash='dash'), name="Alareuna", fill='tonexty', fillcolor='rgba(255,165,0,0.08)'),
                    go.Scatter(x=df.index, y=df['Close'], line=dict(color='black', width=1.5), name="Kurssi")
                ])
                fig_bb.update_layout(template="plotly_white", height=350, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_bb, use_container_width=True)

                # 4. MACD
                st.subheader("4. MACD (Momentti)")
                fig_macd = go.Figure(data=[
                    go.Bar(x=df.index, y=df['MACD Hist'], marker_color='cadetblue', name="MACD Histogrammi"),
                    go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue', width=1.5), name="MACD Linja"),
                    go.Scatter(x=df.index, y=df['MACD Signal'], line=dict(color='deeppink', width=1.5), name="Signaalilinja")
                ])
                fig_macd.update_layout(template="plotly_white", height=300, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_macd, use_container_width=True)

                # 5. RSI
                st.subheader("5. RSI (14) - Yliostettu / Ylimyyty")
                fig_rsi = go.Figure(data=[
                    go.Scatter(x=df.index, y=df['RSI'], line=dict(color='royalblue', width=2), name="RSI"),
                    go.Scatter(x=df.index, y=[70]*len(df), line=dict(color='red', width=1, dash='dot'), name="Yliostettu (70)"),
                    go.Scatter(x=df.index, y=[30]*len(df), line=dict(color='green', width=1, dash='dot'), name="Ylimyyty (30)")
                ])
                fig_rsi.update_layout(template="plotly_white", height=300, yaxis=dict(range=[0, 100]), margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_rsi, use_container_width=True)

            else:
                st.error("Puuttuvia hintatietoja osakkeen datassa.")
        else:
            st.warning("Historiatietoja ei ole riittävästi (vähintään 200 päivää) teknisten indikaattoreiden laskemiseen.")

# Sivupalkki
with st.sidebar:
    st.header("Tietoa sovelluksesta")
    st.write("Versio 6.5 - Zebran Salkku.")
    st.markdown("---")
    st.write("**Pikalinkit lähteisiin:**")
    st.markdown("- [Arvopaperi](https://www.arvopaperi.fi)")
    st.markdown("- [Inderes](https://www.inderes.fi)")
    st.markdown("- [Seeking Alpha](https://seekingalpha.com)")