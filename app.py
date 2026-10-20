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
import streamlit.components.v1 as components
from time import mktime

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
    .info-box {
        background-color: #ffffff;
        padding: 12px 15px;
        border-radius: 6px;
        border-left: 4px solid #0969da;
        font-size: 13px;
        color: #24292f;
        margin-bottom: 15px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
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
tab_news, tab_charts, tab_tech = st.tabs(["📰 Uutisvahti & Gmail", "📈 Kurssit & Kehitys", "📊 Tekniset Indikaattorit & Tunnusluvut"])

# ==========================================
# VÄLILEHTI 1: UUTISVAHTI & GMAIL
# ==========================================
with tab_news:
    st.markdown("Seuraa suosikkiosakkeidesi tuoreimpia uutisia (enintään 14 päivää vanhoja) sekä Nordnetin Aamukirjeitä.")

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
        now = datetime.now()
        fourteen_days_ago = now - timedelta(days=14)
        
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
            "MU": "Micron Technology OR MU stock",
            "ACLS": "Axcelis",
            "OUST": "Ouster",
            "DX": "Dynex Capital"
        }

        # 1. Kansainväliset uutiset Google RSS:n kautta (suodatus max 14pv)
        for symbol in symbols:
            term = search_terms.get(symbol, symbol)
            rss_url = f"https://news.google.com/rss/search?q={term}&hl=en&gl=US&ceid=US:en"
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:5]:
                    # Tarkistetaan julkaisupäivä
                    pub_date = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        pub_date = datetime.fromtimestamp(mktime(entry.updated_parsed))
                    
                    # Jos päivä löytyy ja se on uudempi kuin 14 päivää
                    if pub_date and pub_date >= fourteen_days_ago:
                        news_list.append({
                            "source_type": "Kansainväliset markkinat",
                            "symbol": symbol,
                            "title": entry.title,
                            "url": entry.link,
                            "publisher": "Google News / Global",
                            "date": pub_date.strftime("%Y-%m-%d %H:%M")
                        })
            except Exception:
                continue

        # 2. Kotimainen lähde: Arvopaperi.fi Google RSS:n kautta (suodatus max 14pv)
        for symbol in symbols:
            term = search_terms.get(symbol, symbol)
            rss_url = f"https://news.google.com/rss/search?q={term}+site:arvopaperi.fi&hl=fi&gl=FI&ceid=FI:fi"
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[:3]:
                    pub_date = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        pub_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        pub_date = datetime.fromtimestamp(mktime(entry.updated_parsed))
                    
                    if pub_date and pub_date >= fourteen_days_ago:
                        news_list.append({
                            "source_type": "Kotimainen talousmedia",
                            "symbol": symbol,
                            "title": entry.title,
                            "url": entry.link,
                            "publisher": "Arvopaperi.fi",
                            "date": pub_date.strftime("%Y-%m-%d %H:%M")
                        })
            except Exception:
                continue

        # 3. Gmail (Nordnet Aamukirjeet)
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
                query_str = 'Nordnet Aamukirje OR Sijoituskirje'
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

    with st.spinner("Haetaan tuoreimpia (max 14pv) uutisia, Arvopaperia ja Nordnetin sähköposteja..."):
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
        st.info("Ei tuoreita uutisia (viimeisen 14 päivän ajalta) saatavilla valituille osakkeille.")


# ==========================================
# VÄLILEHTI 2: KURSSIKEHITYS
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
                            
                            currency = "€" if ".HE" in symbol else "$"

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
# VÄLILEHTI 3: TEKNISET INDIKAATTORIT & TUNNUSLUVUT
# ==========================================
with tab_tech:
    st.markdown("📊 **Tekninen analyysi, Tunnusluvut & Vuositason Trendit**")
    st.markdown("Valitse watchlistin osake tai syötä vapaa ticker (esim. MU, AAPL).")

    tech_options = all_symbols + ["Muu osake (kirjoita ticker)..."]
    selected_tech_option = st.selectbox("Valitse osake tarkasteluun:", options=tech_options, key="tech_stock_select")

    if selected_tech_option == "Muu osake (kirjoita ticker)...":
        custom_ticker = st.text_input("Syötä osakkeen ticker-symboli (esim. MU, AAPL, TSLA):", "").strip().upper()
        tech_stock = custom_ticker if custom_ticker else None
    else:
        tech_stock = selected_tech_option

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

        with st.spinner(f"Ladataan kynttilädataa, tunnuslukuja ja lasketaan indikaattoreita osakkeelle {tech_stock}..."):
            df_full = fetch_full_tech_data(tech_stock)
            
            # Haetaan fundamenttitunnusluvut yfinance info-rajapinnasta
            t_obj = yf.Ticker(tech_stock)
            t_info = t_obj.info
            
            pe_ratio = t_info.get('trailingPE', 'Ei saatavilla')
            fwd_pe = t_info.get('forwardPE', 'Ei saatavilla')