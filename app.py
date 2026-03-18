import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
from scipy.stats import norm

st.set_page_config(page_title="Holdco Lifecycle Terminal", layout="wide")

# --- 1. PERSISTENT LEDGER INITIALIZATION ---
# Initializing as a DataFrame prevents the .empty crash
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = pd.DataFrame(columns=[
        "Date", "Ticker", "Type", "Strike", "Premium/sh", "Contracts", "Total PnL", "CDA Room", "ACB"
    ])

# --- 2. MATH & PROBABILITY FUNCTIONS ---
def calculate_pop(S, K, t, sigma, r=0.04):
    try:
        if t <= 0 or sigma <= 0: return 0.5
        d2 = (np.log(S / K) + (r - 0.5 * sigma**2) * t) / (sigma * np.sqrt(t))
        return norm.cdf(d2)
    except: return 0.5

# --- 3. DATA FETCHING ---
@st.cache_data(ttl=600)
def fetch_ticker_basics(symbol):
    try:
        tk = yf.Ticker(symbol)
        info = tk.info
        price = info.get('regularMarketPrice') or info.get('previousClose')
        vix_price = yf.Ticker("^VIX").info.get('regularMarketPrice') or 20.0
        return price, tk.options, vix_price
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

# --- 4. GLOBAL SIDEBAR CONTROLS ---
st.sidebar.header("🛡️ Strategy Controls")
ticker_sym = st.sidebar.text_input("Active Ticker", value="SPY").upper()
contracts = st.sidebar.number_input("Contracts (100 sh/ea)", value=5, min_value=1)

curr_price, expirations, curr_vix = fetch_ticker_basics(ticker_sym)

# --- 5. MAIN INTERFACE ---
if curr_price:
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{ticker_sym} Market Price", f"${curr_price:.2f}")
    m2.metric("VIX (Fear Index)", f"{curr_vix:.2f}")
    m3.metric("Capital Requirement (Unhedged)", f"${(curr_price * contracts * 100):,.0f}")
    
    st.divider()
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Battle Board", "🛡️ Insurance Layer", "🔄 Plan B", "📁 Lifecycle Ledger"])

    # ==========================================
    # TAB 1: BATTLE BOARD
    # ==========================================
    with tab1:
        st.subheader("Phase 1: Put Scanning")
        target_put = st.number_input("Target Put Strike ($)", value=curr_price * 0.95, step=1.0)
        df_puts = compare_options(ticker_sym, target_put, "put")
        if not df_puts.empty:
            fig = px.bar(df_puts, x='Expiry', y='Ann. Return', color='Ann. Return', 
                         color_continuous_scale='Blues', text_auto=True, title="Annualized Yield %")
            st.plotly_chart(fig, use_container_width=True)
            
            df_styled = df_puts.copy()
            df_styled['Premium'] = df_styled['Premium'].map("${:,.2f}".format)
            df_styled['Ann. Return'] = df_styled['Ann. Return'].map("{:,.2f}%".format)
            
            h = (len(df_styled) * 35) + 45
            st.dataframe(df_styled, use_container_width=True, hide_index=True, height=h)
        else:
            st.warning("No option data found for this strike.")

    # ==========================================
    # TAB 2: INSURANCE LAYER
    # ==========================================
    with tab2:
        st.subheader("The Hedged Entry (Bull Put Spread)")
        c1, c2 = st.columns(2)
        with c1:
            sell_strike = st.number_input("Sell Strike (Target Support)", value=target_put, key="ins_sell")
            sell_prem = st.number_input("Premium Received ($)", value=10.50)
        with c2:
            hedge_offset = st.slider("Hedge Offset (% below entry)", 2, 10, 5)
            buy_strike = sell_strike * (1 - (hedge_offset/100))
            st.write(f"Insurance Strike: **${buy_strike:.2f}**")
            buy_cost = st.number_input("Insurance Cost ($)", value=2.50)

        net_prem = sell_prem - buy_cost
        max_risk_per_sh = (sell_strike - buy_strike) - net_prem
        
        st.divider()
        r1, r2, r3 = st.columns(3)
        r1.metric("Net Income/sh", f"${net_prem:.2f}")
        r2.metric("Max Portfolio Risk", f"${(max_risk_per_sh * contracts * 100):,.2f}")
        r3.metric("Est. CDA Credit", f"${(net_prem * 0.5 * contracts * 100):,.2f}")

    # ==========================================
    # TAB 3: PLAN B (COVERED CALLS)
    # ==========================================
    with tab3:
        st.subheader("Phase 3: Recovery (Covered Calls)")
        assigned_at = st.number_input("Assigned Strike Price ($)", value=target_put)
        total_put_prem = st.number_input("Total Prior Premium Collected ($)", value=10.50)
        
        breakeven = assigned_at - total_put_prem
        st.metric("Net Cost Basis (ACB)", f"${breakeven:.2f}")
        
        df_calls = compare_options(ticker_sym, assigned_at, "call")
        if not df_calls.empty:
            sel_call_expiry = st.selectbox("Select Call Expiry:", df_calls['Expiry'])
            row_c = df_calls[df_calls['Expiry'] == sel_call_expiry].iloc[0]
            
            call_gain = (row_c['Strike'] - assigned_at) * contracts * 100
            total_prof = call_gain + ((total_put_prem + row_c['Premium']) * contracts * 100)
            
            st.success(f"🚀 **Total Lifecycle Return if Called:** ${total_prof:,.2f}")
            st.dataframe(df_calls, use_container_width=True, hide_index=True)
        else:
            st.warning("No calls available at this strike currently.")

    # ==========================================
    # TAB 4: LIFECYCLE LEDGER & ACB TRACKER
    # ==========================================
    with tab4:
        st.subheader("📋 Trade Lifecycle Management")
        
        col_input, col_summary = st.columns([1, 2])
        
        with col_input:
            st.markdown("### Log New Event")
            with st.form("lifecycle_form"):
                t_date = st.date_input("Event Date", value=datetime.now())
                t_type = st.selectbox("Transaction Type", [
                    "Put Sold", "Bought Insurance", "Spread Closed (Net)", 
                    "Assigned (Buy Shares)", "Call Sold", "Called Away (Sell Shares)"
                ])
                t_strike = st.number_input("Strike / Share Price", value=0.0)
                t_prem = st.number_input("Premium / Cost per share", value=0.0)
                t_qty = st.number_input("Contracts (100 sh ea)", min_value=1, value=contracts)
                
                st.caption("Fill below ONLY if Assigned or Called Away:")
                t_prior_prem = st.number_input("Total Prior Premiums (for ACB calc)", value=0.0)
                
                submitted = st.form_submit_button("Commit to Ledger")
                
                if submitted:
                    pnl = 0
                    cda = 0
                    acb = "N/A"
                    
                    # Logic Router based on Trade Type
                    if t_type in ["Put Sold", "Call Sold", "Spread Closed (Net)"]:
                        pnl = t_prem * t_qty * 100
                        cda = pnl * 0.5 if pnl > 0 else 0
                    elif t_type == "Bought Insurance":
                        pnl = -(t_prem * t_qty * 100)
                    elif t_type == "Assigned (Buy Shares)":
                        pnl = -(t_strike * t_qty * 100) # Massive cash outflow
                        acb = f"${(t_strike - t_prior_prem):.2f}" # Calculates your true break-even
                    elif t_type == "Called Away (Sell Shares)":
                        pnl = t_strike * t_qty * 100 # Massive cash inflow
                        # Capital Gain = (Sell Price - (Strike Bought - Prior Premiums))
                        cap_gain = (t_strike - (t_strike - t_prior_prem)) * t_qty * 100
                        cda = cap_gain * 0.5 if cap_gain > 0 else 0

                    new_row = pd.DataFrame([{
                        "Date": t_date.strftime("%Y-%m-%d"), 
                        "Ticker": ticker_sym, 
                        "Type": t_type, 
                        "Strike": t_strike, 
                        "Premium/sh": t_prem, 
                        "Contracts": t_qty, 
                        "Total PnL": pnl, 
                        "CDA Room": cda,
                        "ACB": acb
                    }])
                    
                    st.session_state.trade_history = pd.concat([st.session_state.trade_history, new_row], ignore_index=True)
                    st.rerun()

        with col_summary:
            st.markdown("### Performance Summary")
            # Safe check using len() to avoid the .empty bug
            if len(st.session_state.trade_history) > 0:
                df = st.session_state.trade_history
                ticker_df = df[df["Ticker"] == ticker_sym]
                
                s1, s2, s3 = st.columns(3)
                total_flow = ticker_df["Total PnL"].sum()
                total_cda = ticker_df["CDA Room"].sum()
                
                s1.metric("Net Cash Flow", f"${total_flow:,.2f}", help="Includes cash used to buy shares if assigned.")
                s2.metric("Total CDA Credit", f"${total_cda:,.2f}", help="Tax-free withdrawal room generated.")
                s3.metric("Events Logged", len(ticker_df))
                
                st.divider()
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Full Tax Ledger", data=csv, file_name=f"holdco_{ticker_sym}_ledger.csv", mime="text/csv")
                
                if st.button("🗑️ Clear All Data"):
                    st.session_state.trade_history = pd.DataFrame(columns=df.columns)
                    st.rerun()
            else:
                st.info("No data logged. Record your first trade to begin tracking your Holdco performance.")

else:
    st.error("Invalid Ticker or Connection Issue. Please check the ticker symbol.")
