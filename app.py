import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="Holdco Pro Terminal 2026", layout="wide")

st.title("🛡️ Holdco Pro Option Terminal")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Asset Selection")
ticker_sym = st.sidebar.text_input("Ticker", value="SPY").upper()
contracts = st.sidebar.number_input("Contracts", value=5)

# --- DATA FETCHING ---
@st.cache_data(ttl=300) # Cache for 5 mins to stay fast
def get_option_data(symbol):
    tk = yf.Ticker(symbol)
    expirations = tk.options
    price = tk.fast_info['last_price']
    vix = yf.Ticker("^VIX").fast_info['last_price']
    return tk, expirations, price, vix

try:
    tk, expirations, curr_price, curr_vix = get_option_data(ticker_sym)
    
    # --- OPTION SELECTORS ---
    st.sidebar.header("2. Option Selection")
    selected_expiry = st.sidebar.selectbox("Select Expiry Date", expirations)
    
    # Get the chain for that expiry
    chain = tk.option_chain(selected_expiry)
    puts = chain.puts
    
    # Filter for Strikes (usually want Out-of-the-Money)
    otm_puts = puts[puts['strike'] < curr_price].sort_values('strike', ascending=False)
    selected_strike = st.sidebar.selectbox("Select Strike Price", otm_puts['strike'])
    
    # Get specific data for selected strike
    opt_row = otm_puts[otm_puts['strike'] == selected_strike].iloc[0]
    
    # --- CALCULATIONS ---
    live_prem = opt_row['lastPrice']
    live_iv = opt_row['impliedVolatility'] * 100
    
    # Financial Logic
    total_cash = selected_strike * contracts * 100
    total_prem = live_prem * contracts * 100
    cda_credit = total_prem * 0.50
    pass_impact = (total_prem / 50000) * 100
    safety_margin = ((curr_price - selected_strike) / curr_price) * 100
    
    # Annualized Return (DTE Calculation)
    from datetime import datetime
    dte = (datetime.strptime(selected_expiry, '%Y-%m-%d') - datetime.now()).days
    if dte <= 0: dte = 1
    ann_return = ((total_prem / (total_cash - total_prem)) * (365 / dte) * 100)

    # --- UI LAYOUT ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Stock Price", f"${curr_price:.2f}")
    col2.metric("Put Premium", f"${live_prem:.2f}")
    col3.metric("Live IV", f"{live_iv:.1f}%")
    col4.metric("VIX Index", f"{curr_vix:.2f}")

    st.divider()

    # --- BATTLE LOGIC CHECKLIST ---
    c_left, c_right = st.columns([1, 2])
    
    with c_left:
        st.subheader("Holdco Battle Check")
        r1 = curr_vix > 20
        r2 = live_iv > 25 # Threshold for "juiced" premium
        r3 = safety_margin > 8.0
        r4 = total_prem < 4166
        
        def check(label, cond, val):
            color = "green" if cond else "red"
            st.markdown(f":{color}[{'✅' if cond else '❌'} {label}: **{val}**]")

        check("Market Fear (VIX)", r1, f"{curr_vix:.2f}")
        check("IV Level (Relative Value)", r2, f"{live_iv:.1f}%")
        check("Safety (OTM Margin)", r3, f"{safety_margin:.1f}%")
        check("Tax Shield (Monthly Cap)", r4, f"${total_prem:,.0f}")

    with c_right:
        st.subheader("Capital Analysis")
        st.write(f"💰 **Cash Required (Collateral):** ${total_cash:,.2f}")
        st.write(f"🍁 **Tax-Free CDA Credit:** ${cda_credit:,.2f}")
        st.progress(min(pass_impact/100, 1.0), text=f"Passive Income Threshold Use: {pass_impact:.1f}%")
        st.metric("Annualized Return", f"{ann_return:.2f}%")

except Exception as e:
    st.error(f"Error loading data for {ticker_sym}. This usually happens during weekends or if the ticker has no options.")
    st.info("Try a high-liquidity ticker like SPY, TSLA, or CCJ.")
