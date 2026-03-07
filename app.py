import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Holdco Pro Terminal 2026", layout="wide")

st.title("🛡️ Holdco Pro Option Terminal")

# --- DATA FETCHING (Robust Version) ---
@st.cache_data(ttl=300)
def get_market_data(symbol):
    try:
        tk = yf.Ticker(symbol)
        # Handle the case where fast_info might fail on weekends
        info = tk.info
        curr_price = info.get('regularMarketPrice') or info.get('navPrice') or info.get('previousClose')
        
        vix_tk = yf.Ticker("^VIX")
        vix_price = vix_tk.info.get('regularMarketPrice') or vix_tk.info.get('previousClose')
        
        expirations = tk.options
        return tk, expirations, curr_price, vix_price
    except Exception as e:
        return None, None, None, None

# --- SIDEBAR ---
st.sidebar.header("1. Asset Selection")
ticker_sym = st.sidebar.text_input("Ticker", value="SPY").upper()
contracts = st.sidebar.number_input("Contracts", value=5, min_value=1)

tk, expirations, curr_price, curr_vix = get_market_data(ticker_sym)

if tk and expirations and curr_price:
    # --- OPTION SELECTORS ---
    st.sidebar.header("2. Option Selection")
    selected_expiry = st.sidebar.selectbox("Select Expiry Date", expirations)
    
    # Fetch chain
    chain = tk.option_chain(selected_expiry)
    puts = chain.puts
    
    # Filter for Out-of-the-Money Puts
    otm_puts = puts[puts['strike'] < curr_price].sort_values('strike', ascending=False)
    
    if not otm_puts.empty:
        selected_strike = st.sidebar.selectbox("Select Strike Price", otm_puts['strike'])
        opt_row = otm_puts[otm_puts['strike'] == selected_strike].iloc[0]
        
        # Market Data
        live_prem = opt_row['lastPrice']
        # Handle cases where IV might be missing
        live_iv = (opt_row['impliedVolatility'] * 100) if 'impliedVolatility' in opt_row else 0
        
        # --- CALCULATIONS ---
        total_cash = selected_strike * contracts * 100
        total_prem = live_prem * contracts * 100
        cda_credit = total_prem * 0.50
        pass_impact = (total_prem / 50000) * 100
        safety_margin = ((curr_price - selected_strike) / curr_price) * 100
        
        expiry_dt = datetime.strptime(selected_expiry, '%Y-%m-%d')
        dte = (expiry_dt - datetime.now()).days
        if dte <= 0: dte = 1
        ann_return = ((total_prem / (total_cash - total_prem)) * (365 / dte) * 100)

        # --- UI DISPLAY ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Stock Price", f"${curr_price:.2f}")
        col2.metric("Put Premium (Last)", f"${live_prem:.2f}")
        col3.metric("Implied Vol (IV)", f"{live_iv:.1f}%")
        col4.metric("VIX Index", f"{curr_vix:.2f}")

        st.divider()

        c_left, c_right = st.columns([1, 2])
        with c_left:
            st.subheader("Holdco Battle Check")
            r1 = curr_vix > 20
            r2 = live_iv > 20
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
    else:
        st.warning(f"No Out-of-the-Money puts found for {ticker_sym} at this expiry.")
else:
    st.error(f"Unable to fetch data for {ticker_sym}. Markets may be offline or ticker is invalid.")
    st.info("Check your internet connection or try a major ticker like 'TSLA' or 'BTC-USD'.")
