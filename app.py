import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from scipy.stats import norm
from datetime import datetime

# Page Config
st.set_page_config(page_title="Technical Comparison Dashboard", layout="wide")
st.title("📊 4-EMA Benchmark & Options Greeks")

# --- BLACK-SCHOLES ENGINE (Now with Theta) ---
def calculate_greeks(S, K, T, r, sigma, option_type='put'):
    if T <= 0 or sigma <= 0: return 0, 0, 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    # Delta & Gamma
    if option_type == 'put':
        delta = norm.cdf(d1) - 1
    else:
        delta = norm.cdf(d1)
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    
    # Theta (Daily Decay)
    term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
    if option_type == 'put':
        term2 = r * K * np.exp(-r * T) * norm.cdf(-d2)
        theta = (term1 + term2) / 365.0
    else:
        term2 = r * K * np.exp(-r * T) * norm.cdf(d2)
        theta = (term1 - term2) / 365.0
        
    return delta, gamma, theta

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
        df['%K'] = (df['Close'] - df['Low'].rolling(5).min()) / (df['High'].rolling(5).max() - df['Low'].rolling(5).min()) * 100
        
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
                            
                            st.markdown(f"**Live Price:** `${curr_p:.2f}` | **Stoch:** `{last['%K']:.1f}`")

                            # --- UPDATED OPTIONS SECTION ---
                            st.markdown("### 🎲 Options Strategy (Targeting 30-60 DTE)")
                            expirations = list(t_obj.options)
                            
                            if expirations:
                                # Logic to help user find the 30-60 day range
                                today = datetime.now()
                                exp_info = []
                                for ex in expirations:
                                    d = datetime.strptime(ex, '%Y-%m-%d')
                                    days = (d - today).days
                                    exp_info.append(f"{ex} ({days}d)")
                                
                                e1, e2 = st.columns(2)
                                sel_exp_label = e1.selectbox(f"Expiry Selection", exp_info, index=min(5, len(exp_info)-1), key=f"e_{ticker}_{interval}")
                                sel_exp = sel_exp_label.split(" (")[0]
                                
                                # Re-calculate T for Greeks
                                exp_date = datetime.strptime(sel_exp, '%Y-%m-%d')
                                DTE = (exp_date - today).days
                                T = max(DTE, 1) / 365.0
                                
                                opt_chain = t_obj.option_chain(sel_exp)
                                puts = opt_chain.puts
                                
                                # Default to At-The-Money strike
                                atm_idx = (puts['strike'] - curr_p).abs().idxmin()
                                sel_strike = e2.selectbox(f"Put Strike", puts['strike'].tolist(), index=int(atm_idx), key=f"s_{ticker}_{interval}")
                                
                                target_put = puts[puts['strike'] == sel_strike].iloc[0]
                                iv = target_put['impliedVolatility']
                                
                                # Calculate Greeks (Delta, Gamma, Theta)
                                delta, gamma, theta = calculate_greeks(curr_p, sel_strike, T, 0.04, iv)
                                
                                g1, g2, g3, g4 = st.columns(4)
                                g1.metric("Price", f"${target_put['lastPrice']:.2f}")
                                g2.metric("Delta", f"{delta:.2f}")
                                g3.metric("Gamma", f"{gamma:.3f}")
                                g4.metric("Theta", f"{theta:.2f}")
                                
                                if DTE < 30: st.warning(f"⚠️ High Theta Risk: {DTE} days to expiry.")
                                elif 30 <= DTE <= 60: st.success(f"✅ Ideal DTE Window: {DTE} days.")
                            
                            st.divider()
                            # (Bollinger Analysis & Table follow here...)
