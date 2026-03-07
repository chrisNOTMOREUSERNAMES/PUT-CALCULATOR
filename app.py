import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from scipy.stats import norm
from datetime import datetime

# Page Config
st.set_page_config(page_title="Technical Comparison Dashboard", layout="wide")
st.title("📊 4-EMA Benchmark & Options Strategy")

# --- GREEKS & PROBABILITY ENGINE ---
def calculate_metrics(S, K, T, r, sigma, option_type='put'):
    if T <= 0 or sigma <= 0: return 0, 0, 0, 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    # Delta
    delta = norm.cdf(d1) - 1 if option_type == 'put' else norm.cdf(d1)
    # Gamma
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    # Theta (Daily Dollar Decay per 100 shares)
    term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
    term2 = r * K * np.exp(-r * T) * norm.cdf(-d2) if option_type == 'put' else -r * K * np.exp(-r * T) * norm.cdf(d2)
    theta_daily = ((term1 + term2) / 365.0) * 100 
    
    # Probability of Profit (Approx based on Delta)
    # For a Put, POP is roughly 1 - ABS(Delta) if you are the seller, 
    # but since you are likely buying:
    pop = norm.cdf(-d2) if option_type == 'put' else norm.cdf(d2)
    
    return delta, gamma, theta_daily, pop * 100

# --- DATA FETCHING ---
@st.cache_data(ttl=600)
def get_technical_data(symbol, interval):
    try:
        t_obj = yf.Ticker(symbol)
        df = t_obj.history(period="max", interval=interval)
        if df.empty or len(df) < 25: return None, None
        
        # Indicators
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
                            last = df.iloc[-1]; curr_p = float(last['Close'])
                            st.markdown(f"**Price:** `${curr_p:.2f}` | **Stoch:** `{last['%K']:.1f}`")

                            # --- OPTIONS & POP ---
                            st.markdown("### 🎲 Options Strategy")
                            expirations = list(t_obj.options)
                            if expirations:
                                today = datetime.now()
                                exp_info = [f"{ex} ({(datetime.strptime(ex, '%Y-%m-%d') - today).days}d)" for ex in expirations]
                                
                                e1, e2 = st.columns(2)
                                sel_exp_label = e1.selectbox(f"Expiry", exp_info, index=min(5, len(exp_info)-1), key=f"e_{ticker}_{interval}")
                                sel_exp = sel_exp_label.split(" (")[0]
                                T = max((datetime.strptime(sel_exp, '%Y-%m-%d') - today).days, 1) / 365.0
                                
                                opt_chain = t_obj.option_chain(sel_exp)
                                puts = opt_chain.puts
                                atm_idx = (puts['strike'] - curr_p).abs().idxmin()
                                sel_strike = e2.selectbox(f"Put Strike", puts['strike'].tolist(), index=int(atm_idx), key=f"s_{ticker}_{interval}")
                                
                                target_put = puts[puts['strike'] == sel_strike].iloc[0]
                                delta, gamma, theta_val, pop = calculate_metrics(curr_p, sel_strike, T, 0.04, target_put['impliedVolatility'])
                                
                                g1, g2, g3, g4 = st.columns(4)
                                g1.metric("Delta", f"{delta:.2f}")
                                g2.metric("Theta/Day", f"-${abs(theta_val):.2f}")
                                g3.metric("POP", f"{pop:.1f}%")
                                g4.metric("IV", f"{target_put['impliedVolatility']*100:.0f}%")
                                
                                st.caption(f"Contract Price: ${target_put['lastPrice']:.2f} | 100 Shares: ${target_put['lastPrice']*100:.2f}")

                            st.divider()
                            # (Bollinger Analysis Section Follows...)
