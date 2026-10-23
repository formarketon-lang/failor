import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import date

st.set_page_config(
    page_title="TradeLab Pro",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background-color: #0b1120;
    color: #e2e8f0;
}
[data-testid="stSidebar"] {
    background-color: #111827;
}
div[data-testid="stMetric"] {
    background: #1e293b;
    padding: 14px;
    border-radius: 10px;
    border: 1px solid #334155;
}
</style>
""", unsafe_allow_html=True)

st.title("📈 TradeLab Pro")
st.caption("Indian Equity Research | Scanner | Trading Journal")

# ---------------- SESSION STATE ----------------

if "journal" not in st.session_state:
    st.session_state.journal = pd.DataFrame(columns=[
        "Date", "Symbol", "Side", "Entry",
        "Exit", "Quantity", "P&L", "Notes"
    ])

# ---------------- DATA FUNCTIONS ----------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_stock(symbol, period="6mo", interval="1d"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(
        period=period,
        interval=interval,
        auto_adjust=False
    )

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()
    df.columns = [str(c) for c in df.columns]

    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    if "Date" not in df.columns:
        if "index" in df.columns:
            df = df.rename(columns={"index": "Date"})
        else:
            return pd.DataFrame()

    return df.dropna(subset=["Open", "High", "Low", "Close"])

def add_indicators(df):
    df = df.copy()
    df["SMA20"] = df["Close"].rolling(20).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["AvgVolume20"] = df["Volume"].rolling(20).mean()
    df["RSI"] = calculate_rsi(df["Close"])
    return df

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period, min_periods=period, adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period, min_periods=period, adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))

def normalize_symbol(symbol, exchange):
    symbol = symbol.strip().upper()

    if not symbol:
        return ""

    if "." in symbol:
        return symbol

    suffix = ".NS" if exchange == "NSE" else ".BO"
    return symbol + suffix

def scan_symbol(symbol, exchange, period, interval):
    ticker_symbol = normalize_symbol(symbol, exchange)
    df = fetch_stock(ticker_symbol, period, interval)

    if df.empty or len(df) < 2:
        return None, "ডেটা পাওয়া যায়নি বা পর্যাপ্ত ক্যান্ডেল নেই"

    df = add_indicators(df)
    last = df.iloc[-1]
    previous = df.iloc[-2]

    close = float(last["Close"])
    sma20 = last["SMA20"]
    sma50 = last["SMA50"]
    volume = last["Volume"]
    avg_volume = last["AvgVolume20"]
    rsi = last["RSI"]

    if pd.notna(sma20) and pd.notna(sma50):
        if close > sma20 and sma20 > sma50:
            signal = "Bullish"
        elif close < sma20 and sma20 < sma50:
            signal = "Bearish"
        else:
            signal = "Neutral"
    else:
        signal = "Insufficient history"

    if pd.notna(avg_volume) and avg_volume > 0:
        volume_ratio = float(volume / avg_volume)
    else:
        volume_ratio = None

    result = {
        "Symbol": ticker_symbol,
        "Date": last["Date"],
        "Close": round(close, 2),
        "Change %": round(
            (close / float(previous["Close"]) - 1) * 100, 2
        ) if float(previous["Close"]) else 0,
        "SMA20": round(float(sma20), 2) if pd.notna(sma20) else None,
        "SMA50": round(float(sma50), 2) if pd.notna(sma50) else None,
        "RSI": round(float(rsi), 2) if pd.notna(rsi) else None,
        "Volume": int(volume) if pd.notna(volume) else 0,
        "Volume/SMA20": round(volume_ratio, 2)
        if volume_ratio is not None else None,
        "Trend": signal
    }

    return (df, result), None

# ---------------- SIDEBAR ----------------

st.sidebar.title("TradeLab Pro Menu")

page = st.sidebar.radio(
    "Select Module",
    [
        "Dashboard",
        "Stock Scanner",
        "Stock Analysis",
        "CSV Import",
        "Trading Journal",
        "Risk Calculator"
    ]
)

# ---------------- DASHBOARD ----------------

if page == "Dashboard":
    st.header("Dashboard")

    journal = st.session_state.journal
    total_trades = len(journal)

    total_pnl = (
        pd.to_numeric(journal["P&L"], errors="coerce").fillna(0).sum()
        if total_trades else 0
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Journal Trades", total_trades)
    c2.metric("Recorded P&L", f"₹{total_pnl:,.2f}")
    c3.metric("Data Mode", "Yahoo Finance")

    st.info(
        "শুরু করতে Stock Scanner নির্বাচন করুন। "
        "প্রথমবার ডেটা আনতে ইন্টারনেট প্রয়োজন।"
    )

    st.subheader("Recent Trades")
    if total_trades:
        st.dataframe(journal.tail(10), use_container_width=True)
    else:
        st.write("এখনও কোনো ট্রেড সংরক্ষিত হয়নি।")

# ---------------- STOCK SCANNER ----------------

elif page == "Stock Scanner":
    st.header("🔎 All-in-One Stock Scanner")

    c1, c2, c3 = st.columns(3)

    with c1:
        exchange = st.selectbox("Exchange", ["NSE", "BSE"])

    with c2:
        mode = st.selectbox(
            "Scan Mode", ["EOD", "Swing", "Intraday"]
        )

    with c3:
        trend_filter = st.selectbox(
            "Trend Filter", ["All", "Bullish", "Bearish", "Neutral"]
        )

    if mode == "Intraday":
        interval = st.selectbox(
            "Candle Interval", ["5m", "15m", "30m", "60m"]
        )
        period = "5d"
    elif mode == "Swing":
        interval = "1d"
        period = "1y"
    else:
        interval = "1d"
        period = "6mo"

    default_symbols = "RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, ITC, HINDUNILVR, SBIN"

    symbols_text = st.text_area(
        "Stock Symbols (comma-separated)",
        value=default_symbols,
        help="উদাহরণ: RELIANCE, TCS, INFY"
    )

    st.caption(
        "এই তালিকাটি নমুনা। এটি সম্পূর্ণ NSE/BSE universe নয়।"
    )

    run_scan = st.button(
        "▶ Run Scanner", type="primary", use_container_width=True
    )

    if run_scan:
        symbols = list(dict.fromkeys(
            s.strip().upper()
            for s in symbols_text.replace("\n", ",").split(",")
            if s.strip()
        ))

        if not symbols:
            st.warning("কমপক্ষে একটি স্টকের প্রতীক লিখুন।")
        else:
            results = []
            chart_data = {}

            progress = st.progress(0)
            status = st.empty()

            for i, symbol in enumerate(symbols):
                status.write(f"ডেটা সংগ্রহ হচ্ছে: {symbol}")

                try:
                    output, error = scan_symbol(
                        symbol, exchange, period, interval
                    )

                    if output is not None:
                        df, result = output
                        chart_data[result["Symbol"]] = df

                        if (
                            trend_filter == "All"
                            or result["Trend"] == trend_filter
                        ):
                            results.append(result)

                except Exception as exc:
                    st.warning(f"{symbol}: {exc}")

                progress.progress((i + 1) / len(symbols))

            status.empty()

            if results:
                result_df = pd.DataFrame(results)
                st.session_state["scan_results"] = result_df
                st.session_state["scan_charts"] = chart_data

                st.success(f"স্ক্যান সম্পন্ন: {len(results)}টি ফলাফল")
                st.dataframe(
                    result_df,
                    use_container_width=True,
                    hide_index=True
                )

                csv = result_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Export Scan Results CSV",
                    data=csv,
                    file_name="tradelab_scan_results.csv",
                    mime="text/csv"
                )
            else:
                st.warning(
                    "কোনো ফলাফল পাওয়া যায়নি। Symbol, internet "
                    "connection এবং নির্বাচিত filter পরীক্ষা করুন।"
                )

    if "scan_results" in st.session_state:
        st.subheader("Candlestick Chart")

        available_symbols = st.session_state["scan_results"]["Symbol"].tolist()

        selected_symbol = st.selectbox(
            "Chart Symbol", available_symbols, key="chart_symbol"
        )

        df = st.session_state["scan_charts"].get(selected_symbol)

        if df is not None and not df.empty:
            df = add_indicators(df)

            fig = go.Figure()

            fig.add_trace(go.Candlestick(
                x=df["Date"],
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="Candles"
            ))

            fig.add_trace(go.Scatter(
                x=df["Date"], y=df["SMA20"],
                name="SMA 20", mode="lines"
            ))

            fig.add_trace(go.Scatter(
                x=df["Date"], y=df["SMA50"],
                name="SMA 50", mode="lines"
            ))

            fig.update_layout(
                template="plotly_dark",
                height=550,
                xaxis_rangeslider_visible=False,
                title=selected_symbol
            )

            st.plotly_chart(fig, use_container_width=True)

# ---------------- STOCK ANALYSIS ----------------

elif page == "Stock Analysis":
    st.header("📊 Stock Analysis")

    exchange = st.selectbox("Exchange", ["NSE", "BSE"], key="analysis_exchange")
    symbol = st.text_input(
        "Stock Symbol", value="HINDUNILVR", key="analysis_symbol"
    )
    period = st.selectbox(
        "Historical Period", ["1mo", "3mo", "6mo", "1y", "2y"]
    )

    if st.button("Analyze Stock", type="primary"):
        ticker_symbol = normalize_symbol(symbol, exchange)

        with st.spinner("ডেটা সংগ্রহ হচ্ছে..."):
            try:
                df = fetch_stock(ticker_symbol, period, "1d")

                if df.empty:
                    st.error("স্টকের ডেটা পাওয়া যায়নি।")
                else:
                    df = add_indicators(df)
                    last = df.iloc[-1]

                    a, b, c = st.columns(3)
                    a.metric("Latest Close", f"₹{last['Close']:.2f}")
                    b.metric(
                        "SMA20",
                        f"₹{last['SMA20']:.2f}"
                        if pd.notna(last["SMA20"]) else "N/A"
                    )
                    c.metric(
                        "RSI",
                        f"{last['RSI']:.2f}"
                        if pd.notna(last["RSI"]) else "N/A"
                    )

                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(
                        x=df["Date"],
                        open=df["Open"],
                        high=df["High"],
                        low=df["Low"],
                        close=df["Close"],
                        name="Candles"
                    ))
                    fig.add_trace(go.Scatter(
                        x=df["Date"], y=df["SMA20"], name="SMA20"
                    ))
                    fig.add_trace(go.Scatter(
                        x=df["Date"], y=df["SMA50"], name="SMA50"
                    ))
                    fig.update_layout(
                        template="plotly_dark",
                        height=550,
                        xaxis_rangeslider_visible=False
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    st.subheader("Recent Price Data")
                    st.dataframe(df.tail(20), use_container_width=True)

            except Exception as exc:
                st.error(f"Analysis error: {exc}")

# ---------------- CSV IMPORT ----------------

elif page == "CSV Import":
    st.header("📁 CSV Data Import")

    uploaded_file = st.file_uploader(
        "Upload stock CSV", type=["csv"]
    )

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.success(f"CSV loaded: {len(df)} rows")
            st.dataframe(df.head(100), use_container_width=True)

            st.caption(
                "CSV বিশ্লেষণের জন্য Date, Open, High, Low, Close, "
                "Volume কলাম থাকা উপযোগী।"
            )

            if st.button("Check OHLCV Columns"):
                required = {
                    "Open", "High", "Low", "Close", "Volume"
                }
                missing = required - set(df.columns)

                if not missing:
                    st.success("প্রয়োজনীয় OHLCV কলাম উপস্থিত আছে।")
                else:
                    st.warning(
                        "অনুপস্থিত কলাম: " + ", ".join(sorted(missing))
                    )

        except Exception as exc:
            st.error(f"CSV পড়া যায়নি: {exc}")

# ---------------- TRADING JOURNAL ----------------

elif page == "Trading Journal":
    st.header("📒 Trading Journal")

    with st.form("trade_form", clear_on_submit=True):
        c1, c2 = st.columns(2)

        with c1:
            trade_date = st.date_input("Trade Date", value=date.today())
            symbol = st.text_input("Symbol")
            side = st.selectbox("Side", ["BUY", "SELL"])
            entry = st.number_input("Entry Price", min_value=0.0, step=0.05)

        with c2:
            exit_price = st.number_input(
                "Exit Price", min_value=0.0, step=0.05
            )
            quantity = st.number_input(
                "Quantity", min_value=1, value=1, step=1
            )
            notes = st.text_input("Notes")

        submitted = st.form_submit_button("Save Trade")

        if submitted:
            if not symbol.strip() or entry <= 0 or exit_price <= 0:
                st.error("Symbol, Entry ও Exit Price সঠিকভাবে দিন।")
            else:
                pnl = (
                    (exit_price - entry) * quantity
                    if side == "BUY"
                    else (entry - exit_price) * quantity
                )

                new_trade = pd.DataFrame([{
                    "Date": str(trade_date),
                    "Symbol": symbol.strip().upper(),
                    "Side": side,
                    "Entry": entry,
                    "Exit": exit_price,
                    "Quantity": quantity,
                    "P&L": round(pnl, 2),
                    "Notes": notes
                }])

                st.session_state.journal = pd.concat(
                    [st.session_state.journal, new_trade],
                    ignore_index=True
                )

                st.success(f"Trade recorded. P&L: ₹{pnl:,.2f}")

    journal = st.session_state.journal

    if not journal.empty:
        st.subheader("Journal Records")
        st.dataframe(journal, use_container_width=True)

        st.metric(
            "Total Recorded P&L",
            f"₹{pd.to_numeric(journal['P&L']).sum():,.2f}"
        )

        st.download_button(
            "Export Journal CSV",
            journal.to_csv(index=False).encode("utf-8"),
            "tradelab_journal.csv",
            "text/csv"
        )

        if st.button("Clear Current Session Journal"):
            st.session_state.journal = journal.iloc[0:0].copy()
            st.rerun()
    else:
        st.info(
            "এই সংস্করণে Journal ব্রাউজারের বর্তমান Streamlit session-এ "
            "থাকে; স্থায়ী database storage এখনো যোগ করা হয়নি।"
        )

# ---------------- RISK CALCULATOR ----------------

elif page == "Risk Calculator":
    st.header("🛡️ Risk Calculator")

    capital = st.number_input(
        "Trading Capital (₹)", min_value=0.0, value=25000.0, step=1000.0
    )

    risk_pct = st.number_input(
        "Risk Per Trade (%)", min_value=0.1, max_value=10.0,
        value=1.0, step=0.1
    )

    entry = st.number_input(
        "Entry Price (₹)", min_value=0.0, value=100.0, step=0.5
    )

    stop = st.number_input(
        "Stop-Loss Price (₹)", min_value=0.0, value=90.0, step=0.5
    )

    if st.button("Calculate Position Size", type="primary"):
        risk_amount = capital * risk_pct / 100
        risk_per_share = abs(entry - stop)

        if entry <= 0 or stop <= 0 or risk_per_share <= 0:
            st.error("Entry ও Stop-Loss সঠিকভাবে দিন।")
        else:
            quantity = int(risk_amount / risk_per_share)
            position_value = quantity * entry

            a, b, c = st.columns(3)
            a.metric("Allowed Risk", f"₹{risk_amount:,.2f}")
            b.metric("Risk per Share", f"₹{risk_per_share:,.2f}")
            c.metric("Suggested Quantity", quantity)

            st.write(f"Position Value: ₹{position_value:,.2f}")

            if position_value > capital:
                st.warning(
                    "এই quantity-র জন্য মূলধনের চেয়ে বেশি অর্থ লাগবে। "
                    "Quantity কমানো বা উপযুক্ত leverage-free setup বিবেচনা করুন।"
                )

st.sidebar.divider()
st.sidebar.caption("TradeLab Pro | Research & Education")
