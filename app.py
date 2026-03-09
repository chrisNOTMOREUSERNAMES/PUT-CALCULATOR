import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
from scipy.stats import norm

st.set_page_config(page_title="Holdco Pro: Wheel Terminal", layout="wide")

# --- PROBABILITY CALCULATION ---
def calculate_pop(S, K, t, sigma, r=0.04):
    try:
        if t <= 0 or sigma <= 0: return 0.5
        d2 = (np.log(S / K) + (r - 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
        return norm.cdf(d2)
    except:
        return 0.5

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
                
                # For puts, find closest strike. For calls, find closest strike AT OR ABOVE target
                if opt_type == "call":
                    valid_calls = options[options['strike'] >= target_strike]
                    if valid_calls.empty: continue
                    idx = (valid_calls['strike'] - target_strike).abs().idxmin()
                    opt = valid_calls.loc[idx]
                else:
                    idx = (options['strike'] - target_strike).abs().idxmin()
                    opt = options.loc[idx]
                
                # Math limits to prevent infinity errors on zero bids
                last_price = opt['lastPrice']
                if last_price <= 0.01: continue
                
                if opt_type == "put":
                    raw_ret = last_price / (opt['strike'] - last_price)
                else:
                    raw_ret = last_price / opt['strike'] # Return on capital tied up in stock
                    
                ann_ret = round((raw_ret * (365 / dte) * 100), 2)
                
                comparison_data.append({
                    "Expiry": expiry,
                    "DTE": dte,
                    "Actual Strike": opt['strike'],
                    "Premium": last_price,
                    "IV": opt['impliedVolatility'],
                    "Annualized Return": ann_ret
                })
        except: continue
    
    df = pd.DataFrame(comparison_data)
    if not df.empty:
        df = df.sort_values("DTE")
    return df

# --- SIDEBAR ---
st.sidebar.header("🛡️ Asset Selection")
ticker_sym = st.sidebar.text_input("Ticker", value="SPY").upper()
contracts = st.sidebar.number_input("Contracts (100 sh)", value=5, min_value=1)

curr_price, expirations, curr_vix = fetch_ticker_basics(ticker_sym)

if curr_price:
    # Top Level Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{ticker_sym} Price", f"${curr_price:.2f}")
    m2.metric("VIX (Fear Index)", f"{curr_vix:.2f}")
    m3.metric("Capital at Risk", f"${(curr_price * contracts * 100):,.0f}")
    st.divider()

    # --- TABS FOR THE WHEEL STRATEGY ---
    tab1, tab2 = st.tabs(["Phase 1: Entry (Sell Puts)", "Phase 3: Plan B (Sell Covered Calls)"])

    # ==========================================
    # TAB 1: SELL PUTS
    # ==========================================
    with tab1:
        st.subheader("Phase 1: Income Generation & Entry")
        target_strike_put = st.number_input("Target Put Strike ($)", value=curr_price * 0.90, step=0.5, format="%.2f")
        
        with st.spinner("Scanning Put Chains..."):
            df_puts = compare_options(ticker_sym, target_strike_put, "put")
            
        if not df_puts.empty:
            fig_put = px.bar(df_puts, x='Expiry', y='Annualized Return', color='Annualized Return', 
                         color_continuous_scale='Blues', text_auto=True, title="Put Yield Battle %")
            st.plotly_chart(fig_put, use_container_width=True)

            df_styled_p = df_puts.copy()
            df_styled_p['Premium'] = df_styled_p['Premium'].map("${:,.2f}".format)
            df_styled_p['IV'] = (df_styled_p['IV'] * 100).map("{:,.1f}%".format)
            df_styled_p['Annualized Return'] = df_styled_p['Annualized Return'].map("{:,.2f}%".format)
            st.dataframe(df_styled_p, use_container_width=True, hide_index=True, height=(len(df_styled_p)*35)+40)
        else:
            st.warning("No put options found for this criteria.")

    # ==========================================
    # TAB 2: PLAN B (COVERED CALLS)
    # ==========================================
    with tab2:
        st.subheader("Phase 3: The Rescue Mission")
        st.info("Got assigned? Don't panic. Enter your assigned strike and the premium you already collected to find your breakeven and sell Covered Calls to generate more CDA.")
        
        c1, c2 = st.columns(2)
        with c1:
            assigned_strike = st.number_input("Assigned Strike Price ($)", value=curr_price, step=0.5, format="%.2f")
        with c2:
            premium_kept = st.number_input("Premium Kept from Put ($)", value=2.00, step=0.1, format="%.2f")
            
        breakeven = assigned_strike - premium_kept
        st.metric("Your True Breakeven", f"${breakeven:.2f}")
        
        # We want to sell calls AT or ABOVE the assigned strike to avoid capital losses on the stock
        target_strike_call = st.number_input("Target Call Strike ($) - Must be >= Assigned Strike", value=assigned_strike, step=0.5, format="%.2f")
        
        with st.spinner("Scanning Call Chains..."):
            df_calls = compare_options(ticker_sym, target_strike_call, "call")
            
        if not df_calls.empty:
            fig_call = px.bar(df_calls, x='Expiry', y='Annualized Return', color='Annualized Return', 
                         color_continuous_scale='Greens', text_auto=True, title="Covered Call Yield Battle %")
            st.plotly_chart(fig_call, use_container_width=True)

            df_styled_c = df_calls.copy()
            df_styled_c['Premium'] = df_styled_c['Premium'].map("${:,.2f}".format)
            df_styled_c['IV'] = (df_styled_c['IV'] * 100).map("{:,.1f}%".format)
            df_styled_c['Annualized Return'] = df_styled_c['Annualized Return'].map("{:,.2f}%".format)
            st.dataframe(df_styled_c, use_container_width=True, hide_index=True, height=(len(df_styled_c)*35)+40)
            
            # Plan B Recovery Math
            st.divider()
            best_call = df_calls.iloc[0] # Just an example taking the nearest
            new_cda = (best_call['Premium'] * contracts * 100) * 0.5
            st.success(f"🍁 **Holdco Bonus:** Selling the nearest call adds another **${new_cda:,.2f}** to your tax-free CDA, while waiting for the stock to recover.")
        else:
            st.warning("No call options found. The stock may have dropped too far to sell calls at this strike profitably. Consider waiting for a green day.")

else: 
    st.error("Invalid Ticker or Connection Issue.")
