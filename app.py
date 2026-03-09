import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
from scipy.stats import norm

st.set_page_config(page_title="Holdco Wheel Terminal", layout="wide")

# --- PROBABILITY CALCULATION ---
def calculate_pop(S, K, t, sigma, r=0.04):
    try:
        if t <= 0 or sigma <= 0: return 0.5
        d2 = (np.log(S / K) + (r - 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
        return norm.cdf(d2)
    except: return 0.5

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
    except: return None, None, None

@st.cache_data(ttl=600)
def compare_options(symbol, target_strike, opt_type="put"):
    tk = yf.Ticker(symbol)
    comparison_data = []
    for expiry in tk.options:
        try:
            expiry_dt = datetime.strptime(expiry, '%Y-%m-%d')
            dte = (expiry_dt - datetime.now()).days
            if 0 < dte <= 90:
                chain = tk.option_chain(expiry)
                options = chain.puts if opt_type == "put" else chain.calls
                
                # Strike matching
                if opt_type == "call":
                    valid_opts = options[options['strike'] >= target_strike]
                else:
                    valid_opts = options[options['strike'] <= target_strike]
                
                if valid_opts.empty: continue
                idx = (valid_opts['strike'] - target_strike).abs().idxmin()
                opt = valid_opts.loc[idx]
                
                if opt['lastPrice'] <= 0.01: continue
                
                ann_ret = round(((opt['lastPrice'] / opt['strike']) * (365 / dte) * 100), 2)
                comparison_data.append({
                    "Expiry": expiry, "DTE": dte, "Strike": opt['strike'],
                    "Premium": opt['lastPrice'], "IV": opt['impliedVolatility'],
                    "Ann. Return": ann_ret
                })
        except: continue
    return pd.DataFrame(comparison_data).sort_values("DTE") if comparison_data else pd.DataFrame()

# --- SIDEBAR & GLOBAL DATA ---
st.sidebar.header("🛡️ Strategy Controls")
ticker_sym = st.sidebar.text_input("Ticker", value="SPY").upper()
contracts = st.sidebar.number_input("Contracts (100 sh/ea)", value=5, min_value=1)

curr_price, expirations, curr_vix = fetch_ticker_basics(ticker_sym)

if curr_price:
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{ticker_sym} Price", f"${curr_price:.2f}")
    m2.metric("VIX (Fear Index)", f"{curr_vix:.2f}")
    m3.metric("Capital at Risk", f"${(curr_price * contracts * 100):,.0f}")
    
    st.divider()
    tab1, tab2, tab3 = st.tabs(["📊 Battle Board", "🛡️ Insurance Layer", "🔄 Plan B (Recovery)"])

    # --- TAB 1: BATTLE BOARD (Scanning) ---
    with tab1:
        st.subheader("Phase 1: Put Scanning & Selection")
        target_put = st.number_input("Target Put Strike ($)", value=curr_price * 0.95, step=1.0)
        
        df_puts = compare_options(ticker_sym, target_put, "put")
        if not df_puts.empty:
            fig = px.bar(df_puts, x='Expiry', y='Ann. Return', color='Ann. Return', 
                         color_continuous_scale='Blues', text_auto=True, title="Yield Comparison %")
            st.plotly_chart(fig, use_container_width=True)
            
            # Full table view
            df_styled = df_puts.copy()
            df_styled['Premium'] = df_styled['Premium'].map("${:,.2f}".format)
            df_styled['Ann. Return'] = df_styled['Ann. Return'].map("{:,.2f}%".format)
            st.dataframe(df_styled, use_container_width=True, hide_index=True, height=(len(df_styled)*35)+40)
        else:
            st.warning("No data found for this strike.")

    # --- TAB 2: INSURANCE LAYER (The Hedge) ---
    with tab2:
        st.subheader("The Hedged Entry (Bull Put Spread)")
        st.markdown("> **Note:** We sell the Put at your target support and *simultaneously* buy a lower Put as insurance.")
        
        c1, c2 = st.columns(2)
        with c1:
            sell_strike = st.number_input("Sell Strike (Entry)", value=target_put, key="ins_sell")
            sell_prem = st.number_input("Premium Received ($)", value=10.50)
        with c2:
            hedge_offset = st.slider("Hedge Offset (% below entry)", 2, 10, 5)
            buy_strike = sell_strike * (1 - (hedge_offset/100))
            st.write(f"Insurance Strike: **${buy_strike:.2f}**")
            buy_cost = st.number_input("Insurance Cost ($)", value=2.50)

        net_prem = sell_prem - buy_cost
        max_risk = (sell_strike - buy_strike) - net_prem
        
        st.divider()
        r1, r2, r3 = st.columns(3)
        r1.metric("Net Income", f"${net_prem:.2f}")
        r2.metric("Max Portfolio Risk", f"${(max_risk * contracts * 100):,.2f}", delta="Capped Loss", delta_color="normal")
        r3.metric("Tax-Free CDA Room", f"${(net_prem * 0.5 * contracts * 100):,.2f}")
        
        st.info(f"🛡️ **Peace of Mind:** By spending ${buy_cost:.2f} now, you ensure that even if {ticker_sym} goes to zero, your loss stops exactly at ${buy_strike:.2f}.")

    # --- TAB 3: PLAN B (The Wheel) ---
    with tab3:
        st.subheader("Phase 3: Covered Call Recovery")
        assigned_at = st.number_input("Assigned Strike Price ($)", value=target_put)
        total_put_prem = st.number_input("Total Put Premium Collected ($)", value=10.50)
        
        breakeven = assigned_at - total_put_prem
        st.metric("Net Cost Basis (Breakeven)", f"${breakeven:.2f}")
        
        df_calls = compare_options(ticker_sym, assigned_at, "call")
        if not df_calls.empty:
            sel_call_expiry = st.selectbox("Select Call Expiry:", df_calls['Expiry'])
            row_c = df_calls[df_calls['Expiry'] == sel_call_expiry].iloc[0]
            
            call_gain = (row_c['Strike'] - assigned_at) * contracts * 100
            total_prof = call_gain + ((total_put_prem + row_c['Premium']) * contracts * 100)
            
            st.success(f"🚀 **Total Lifecycle Return:** If called away, your total Holdco profit is **${total_prof:,.2f}**.")
            st.write(f"This includes Put Premium + Call Premium + Stock Appreciation.")
        else:
            st.warning("No calls available at this strike currently.")

else:
    st.error("Invalid Ticker. Check spelling or connection.")
