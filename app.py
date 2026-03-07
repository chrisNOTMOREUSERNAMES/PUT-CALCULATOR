import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
from scipy.stats import norm

st.set_page_config(page_title="Holdco Pro: Expiry Battle", layout="wide")

# --- PROBABILITY CALCULATION (Black-Scholes Delta Proxy) ---
def calculate_pop(S, K, t, sigma, r=0.04):
    if t <= 0 or sigma <= 0: return 0.5
    d2 = (np.log(S / K) + (r - 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
    return norm.cdf(d2)

# --- CACHED DATA FETCHING ---
@st.cache_data(ttl=600)
def fetch_ticker_basics(symbol):
    try:
        tk = yf.Ticker(symbol)
        info = tk.info
        price = info.get('regularMarketPrice') or info.get('previousClose')
        expirations = tk.options
        vix_price = yf.Ticker("^VIX").info.get('regularMarketPrice') or yf.Ticker("^VIX").info.get('previousClose', 20.0)
        return price, expirations, vix_price
    except:
        return None, None, None

@st.cache_data(ttl=600)
def compare_expiries(symbol, target_strike, curr_price):
    tk = yf.Ticker(symbol)
    comparison_data = []
    for expiry in tk.options[:8]:
        try:
            chain = tk.option_chain(expiry).puts
            idx = (chain['strike'] - target_strike).abs().idxmin()
            opt = chain.loc[idx]
            dte = (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days
            if dte <= 0: dte = 1
            
            comparison_data.append({
                "Expiry": expiry,
                "DTE": dte,
                "Actual Strike": opt['strike'],
                "Premium": opt['lastPrice'],
                "IV": opt['impliedVolatility'],
                "Annualized Return": round(((opt['lastPrice'] / (opt['strike'] - opt['lastPrice'])) * (365 / dte) * 100), 2)
            })
        except: continue
    return pd.DataFrame(comparison_data)

# --- SIDEBAR ---
st.sidebar.header("🛡️ Battle Parameters")
ticker_sym = st.sidebar.text_input("Ticker", value="SPY").upper()
target_strike = st.sidebar.number_input("Target Strike ($)", value=480.0, step=0.5, format="%.2f")
contracts = st.sidebar.number_input("Contracts", value=5, min_value=1)

# --- MAIN ---
st.title("🛡️ Holdco Expiry Comparison")
curr_price, expirations, curr_vix = fetch_ticker_basics(ticker_sym)

if curr_price:
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{ticker_sym} Price", f"${curr_price:.2f}")
    m2.metric("VIX (Fear Index)", f"{curr_vix:.2f}")
    m3.metric("Target Strike", f"${target_strike:.2f}")

    st.divider()
    with st.spinner("Scanning Option Chains..."):
        df_comp = compare_expiries(ticker_sym, target_strike, curr_price)
    
    if not df_comp.empty:
        fig = px.bar(df_comp, x='Expiry', y='Annualized Return', color='Annualized Return', 
                     color_continuous_scale='Blues', text_auto=True, title="Yield Battle: Annualized Return %")
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        st.subheader("📋 Holdco Battle Checklist")
        selected_expiry = st.selectbox("Select Expiry for Safety Deep-Dive:", df_comp['Expiry'])
        row = df_comp[df_comp['Expiry'] == selected_expiry].iloc[0]
        
        # Logic Calc
        total_prem = row['Premium'] * contracts * 100
        safety_margin = ((curr_price - row['Actual Strike']) / curr_price) * 100
        pop = calculate_pop(curr_price, row['Actual Strike'], row['DTE']/365, row['IV'])
        
        col_a, col_b = st.columns(2)
        with col_a:
            def check_ui(label, condition, val):
                st.markdown(f"{'✅' if condition else '❌'} {label}: **{val}**", unsafe_allow_html=True)

            check_ui("Market Fear (VIX > 20)", curr_vix > 20, f"{curr_vix:.2f}")
            check_ui("Safety Margin (> 8% OTM)", safety_margin > 8, f"{safety_margin:.1f}%")
            check_ui("Prob. of Profit (> 80%)", pop > 0.80, f"{pop*100:.1f}%")
            check_ui("Tax Shield (Premium < $4,166)", total_prem < 4166, f"${total_prem:,.2f}")
        
        with col_b:
            st.info(f"💰 **Cash Required:** ${(row['Actual Strike'] * contracts * 100):,.2f}")
            st.success(f"🍁 **Tax-Free CDA Credit:** ${(total_prem * 0.5):,.2f}")
            st.warning(f"⚖️ **Passive Limit Use:** {(total_prem/50000)*100:.1f}% of $50k")

    else: st.error("No valid option data found.")
else: st.error("Invalid Ticker.")
