import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px
import io

st.set_page_config(page_title="Holdco Lifecycle Terminal", layout="wide")

# --- 1. PERSISTENT LEDGER ---
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = pd.DataFrame(columns=[
        "Date", "Ticker", "Type", "Status", "Strike", "Premium/sh", "Contracts", "Total PnL", "CDA Room"
    ])

# --- 2. DATA UTILITIES ---
@st.cache_data(ttl=600)
def fetch_ticker_basics(symbol):
    try:
        tk = yf.Ticker(symbol)
        price = tk.info.get('regularMarketPrice') or tk.info.get('previousClose')
        return price, tk.options
    except: return None, None

@st.cache_data(ttl=600)
def get_options(symbol, strike, opt_type):
    tk = yf.Ticker(symbol)
    # Simplified scanner for the Battle Board
    return tk.option_chain(tk.options[0]).puts if opt_type == 'put' else tk.option_chain(tk.options[0]).calls

# --- 3. APP HEADER ---
st.title("🛡️ Holdco Wheel Command Center")
ticker_sym = st.sidebar.text_input("Active Ticker", value="SPY").upper()
curr_price, expirations = fetch_ticker_basics(ticker_sym)

tab1, tab2, tab3, tab4 = st.tabs(["📊 Battle Board", "🛡️ Insurance", "🔄 Plan B", "📁 Lifecycle Ledger"])

# ... (Tabs 1-3 content logic as before) ...

# ==========================================
# TAB 4: THE LIFECYCLE LEDGER
# ==========================================
with tab4:
    st.subheader("📋 Trade Lifecycle Management")
    
    col_input, col_summary = st.columns([1, 2])
    
    with col_input:
        st.markdown("### Log New Event")
        with st.form("lifecycle_form"):
            t_date = st.date_input("Event Date", value=datetime.now())
            t_type = st.selectbox("Transaction Type", ["Put Sold", "Call Sold", "Bought Insurance", "Assigned (Buy Shares)", "Called Away (Sell Shares)", "Expired Worthless"])
            t_strike = st.number_input("Strike Price / Purchase Price", value=0.0)
            t_prem = st.number_input("Premium/sh or Cost/sh", value=0.0)
            t_qty = st.number_input("Contracts (100 sh ea)", min_value=1, value=1)
            
            # Logic for PnL and CDA
            # Credits (Inflow)
            if t_type in ["Put Sold", "Call Sold", "Called Away (Sell Shares)"]:
                pnl = t_prem * t_qty * 100 if t_type != "Called Away (Sell Shares)" else (t_strike * t_qty * 100)
            # Debits (Outflow)
            else:
                pnl = -(t_prem * t_qty * 100) if t_type != "Assigned (Buy Shares)" else -(t_strike * t_qty * 100)
            
            submitted = st.form_submit_button("Commit to Ledger")
            
            if submitted:
                # CDA is only generated on net realized capital gains (Premiums + Stock Gains)
                # For this simple log, we track CDA on premiums and stock price differences
                cda = (pnl * 0.5) if pnl > 0 else 0
                
                new_row = pd.DataFrame([{
                    "Date": t_date, "Ticker": ticker_sym, "Type": t_type, 
                    "Strike": t_strike, "Premium/sh": t_prem, "Contracts": t_qty, 
                    "Total PnL": pnl, "CDA Room": cda
                }])
                st.session_state.trade_history = pd.concat([st.session_state.trade_history, new_row], ignore_index=True)
                st.rerun()

    with col_summary:
        st.markdown("### Performance Summary")
       if not st.session_state.trade_history.empty:

# TO THIS:
if len(st.session_state.trade_history) > 0:
            df = st.session_state.trade_history
            
            # Filter for specific ticker
            ticker_df = df[df["Ticker"] == ticker_sym]
            
            s1, s2, s3 = st.columns(3)
            total_pnl = ticker_df["Total PnL"].sum()
            total_cda = ticker_df["CDA Room"].sum()
            
            # IMPORTANT: Total PnL here includes the cash spent to buy shares
            # To see "Trading Profit", we look at premiums and sales vs buys
            s1.metric("Total Cash Flow", f"${total_pnl:,.2f}")
            s2.metric("Total CDA Credit", f"${total_cda:,.2f}")
            s3.metric("Trade Count", len(ticker_df))
            
            st.divider()
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # CSV Export
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Full Tax Ledger", data=csv, file_name="holdco_ledger.csv")
            
            if st.button("Clear All Data"):
                st.session_state.trade_history = pd.DataFrame(columns=df.columns)
                st.rerun()
        else:
            st.info("No data logged. Record your first 'Put Sold' to begin.")
