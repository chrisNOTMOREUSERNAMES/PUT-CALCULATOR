import streamlit as st
import pandas as pd
from datetime import datetime

# Initialize session state for the trade log if it doesn't exist
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []

def add_trade(ticker, date, expiry, net_premium, contracts):
    total_gain = net_premium * contracts * 100
    cda_credit = total_gain * 0.5
    st.session_state.trade_history.append({
        "Date": date,
        "Ticker": ticker,
        "Expiry": expiry,
        "Contracts": contracts,
        "Net Premium/sh": net_premium,
        "Total Gain": total_gain,
        "CDA Credit": cda_credit
    })

# ... (Previous fetching and calc functions stay the same)

st.title("🛡️ Holdco Wheel & CDA Terminal")

tab1, tab2, tab3, tab4 = st.tabs(["📊 Battle Board", "🛡️ Insurance Layer", "🔄 Plan B", "📁 Trade Log"])

# (Tabs 1-3 remain as per previous code block)

# ==========================================
# TAB 4: TRADE LOG (Post-Fill Data Entry)
# ==========================================
with tab4:
    st.subheader("📝 Post-Trade Filing")
    st.markdown("Use this tab to record your trades once they are filled in your brokerage. This tracks your cumulative tax-free withdrawal room.")

    with st.form("log_trade_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            log_ticker = st.text_input("Ticker", value="SPY").upper()
            log_date = st.date_input("Entry Date", value=datetime.now())
        with c2:
            log_expiry = st.date_input("Expiry Date")
            log_contracts = st.number_input("Contracts", min_value=1, value=1)
        with c3:
            log_net_prem = st.number_input("Net Premium Received (per share)", value=5.00)
            submitted = st.form_submit_button("Record Trade to Ledger")

        if submitted:
            add_trade(log_ticker, log_date, log_expiry, log_net_prem, log_contracts)
            st.success(f"Trade for {log_ticker} logged successfully!")

    if st.session_state.trade_history:
        df_history = pd.DataFrame(st.session_state.trade_history)
        
        # Summary Metrics
        st.divider()
        h1, h2 = st.columns(2)
        total_cda = df_history["CDA Credit"].sum()
        h1.metric("Total Cumulative CDA Room", f"${total_cda:,.2f}")
        h2.metric("Total Net Premium Income", f"${df_history['Total Gain'].sum():,.2f}")

        # Ledger Table
        st.dataframe(df_history, use_container_width=True, hide_index=True)
        
        if st.button("Clear History"):
            st.session_state.trade_history = []
            st.rerun()
    else:
        st.info("No trades logged yet. Fill out the form above after your trade is executed.")
