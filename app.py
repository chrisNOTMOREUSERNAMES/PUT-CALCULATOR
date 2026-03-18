import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from scipy.stats import norm
from datetime import datetime

# Page Config
st.set_page_config(page_title="Technical Comparison Dashboard", layout="wide")
st.title("📊 4-EMA Benchmark & Options Greeks")

# --- BLACK-SCHOLES CALCULATION ENGINE ---
def calculate_greeks(S, K, T, r, sigma, option_type='put'):
    """
    S: Current Price, K: Strike, T: Time to Expiry (years), 
    r: Risk-free rate (approx 0.04), sigma: IV
    """
    if T <= 0 or sigma <= 0: return 0, 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'put':
        delta = norm.cdf(d1) - 1
    else:
        delta = norm.cdf(d1)
        
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return delta, gamma

# --- DATA FETCHING ---
@st.cache_data(ttl=600)
def get_technical_data(symbol, interval):
    try:
        t_obj = yf.Ticker(symbol)
        df = t_obj.history(period="max", interval=interval)
        if df.empty or len(df) < 25: return None, None
        
        # Technicals
        df['EMA4'] = df['Close'].ewm(span=4, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        sma20 = df['Close'].rolling(window=20).mean()
        std20 = df['Close'].rolling(window=20).std()
        df['BB_Top'] = sma20 + (std20 * 2)
        df['BB_Bot'] = sma20 - (std20 * 2)
        df['BB_Width'] = ((df['BB_Top'] - df['BB_Bot']) / sma20) * 100
        
        # Stochastic (5,1)
        low_5 = df['Low'].rolling(window=5).min()
        high_5 = df['High'].rolling(window=5).max()
        df['%K'] = (df['Close'] - low_5) / (high_5 - low_5) * 100
        
        return df, t_obj
    except: return None, None

# --- UI ---
with st.sidebar:
    st.header("Settings")
    raw_tickers = st.text_area("Tickers", "AAPL, MSFT, NVDA, SPY")
    tickers = [t.strip().upper() for t in raw_tickers.split(",") if t.strip()]

if tickers:
    grid = st.columns(2)
    for idx, ticker in enumerate(tickers):
        with grid[idx % 2]:
            with st.container(border=True):
                st.header(ticker)
                t_d, t_w, t_m = st.tabs(["Daily", "Weekly", "Monthly"])
                for tab, interval in zip([t_d, t_w, t_m], ["1d", "1wk", "1mo"]):
                    with tab:
                        df, t_obj = get_technical_data(ticker, interval)
                        if df is not None:
                            last = df.iloc[-1]
                            curr_p = float(last['Close'])
                            
                            # Standard Metrics
                            c1, c2 = st.columns(2)
                            c1.markdown(f"**Price:** `${curr_p:.2f}`")
                            c2.markdown(f"**Stoch (5,1):** `{last['%K']:.1f}`")

                            # --- OPTIONS & GREEKS ---
                            st.markdown("### 🎲 Options Analysis")
                            expirations = t_obj.options
                            if expirations:
                                e1, e2 = st.columns(2)
                                sel_exp = e1.selectbox(f"Expiry", expirations, key=f"e_{ticker}_{interval}")
                                
                                # Process expiration date for T (Time)
                                exp_date = datetime.strptime(sel_exp, '%Y-%m-%d')
                                days_to_expiry = (exp_date - datetime.now()).days
                                T = max(days_to_expiry, 1) / 365.0
                                
                                opt_chain = t_obj.option_chain(sel_exp)
                                puts = opt_chain.puts
                                
                                sel_strike = e2.selectbox(f"Strike", puts['strike'].tolist(), 
                                                           index=len(puts)//2, key=f"s_{ticker}_{interval}")
                                
                                target_put = puts[puts['strike'] == sel_strike].iloc[0]
                                iv = target_put['impliedVolatility']
                                
                                # Calculate Greeks
                                delta, gamma = calculate_greeks(curr_p, sel_strike, T, 0.04, iv)
                                
                                g1, g2, g3, g4 = st.columns(4)
                                g1.metric("Put Price", f"${target_put['lastPrice']:.2f}")
                                g2.metric("IV", f"{iv*100:.1f}%")
                                g3.metric("Delta", f"{delta:.3f}")
                                g4.metric("Gamma", f"{gamma:.4f}")
                            else:
                                st.info("No options available.")

                            st.divider()
                            st.markdown("### 🫧 Bollinger Analysis")
                            # Proximity logic (Current vs BB 1%)
                            dist_top = abs(curr_p - last['BB_Top']) / last['BB_Top']
                            dist_bot = abs(curr_p - last['BB_Bot']) / last['BB_Bot']
                            
                            b1, b2 = st.columns(2)
                            b1.write(f"Width: `{last['BB_Width']:.2f}%`")
                            if dist_top <= 0.01 or curr_p >= last['BB_Top']:
                                b2.error("🔥 Near/Above Upper BB")
                            elif dist_bot <= 0.01 or curr_p <= last['BB_Bot']:
                                b2.success("❄️ Near/Below Lower BB")
                            else:
                                b2.write("Position: Neutral")
                        else: st.error(f"No data for {ticker}")
