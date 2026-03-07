import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Holdco Battle Logic 2026", layout="centered")

# --- CUSTOM STYLING ---
st.markdown("""
    <style>
    .main { background-color: #0b0f19; }
    .stMetric { background-color: #161e2e; padding: 15px; border-radius: 10px; border: 1px solid #38bdf8; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ Holdco Battle Logic 2026")

# --- THE RULES REFERENCE ---
with st.expander("📊 View Holdco Rule Checklist"):
    st.table(pd.DataFrame({
        "Rule Category": ["Market Fear", "Relative Value", "Probability", "Tax Protection"],
        "Condition": ["VIX > 20", "IV Percentile > 70%", "Delta < 0.20", "Premium < $4,166/mo"],
        "Logic": ["Panic Premium", "Historical Value", "80%+ Win Rate", "Stay under $50k/yr limit"]
    }))

# --- INPUTS ---
col1, col2 = st.columns(2)

with col1:
    ticker_sym = st.text_input("Manual Ticker", value="CCJ").upper()
    contracts = st.number_input("Contracts (100 sh ea)", value=5, step=1)
    dte = st.number_input("Days to Expiry", value=45, step=1)

with col2:
    strike = st.number_input("Strike Price ($)", value=100.0, step=0.5)
    premium = st.number_input("Put Premium ($)", value=4.20, step=0.1)

# --- LIVE DATA FETCH ---
if st.button("⚡ FETCH LIVE MARKET DATA"):
    try:
        stock = yf.Ticker(ticker_sym)
        vix = yf.Ticker("^VIX")
        
        curr_price = stock.fast_info['last_price']
        curr_vix = vix.fast_info['last_price']
        
        st.session_state['curr_price'] = curr_price
        st.session_state['curr_vix'] = curr_vix
        st.success(f"Fetched {ticker_sym}: ${curr_price:.2f} | VIX: {curr_vix:.2f}")
    except:
        st.error("Could not fetch data. Check ticker symbol.")

# Use session state or default
price = st.session_state.get('curr_price', 115.0)
vix_val = st.session_state.get('curr_vix', 20.0)

st.write(f"**Current Reference Price:** ${price:.2f} | **Current VIX:** {vix_val:.2f}")

# --- CALCULATIONS ---
total_cash = strike * contracts * 100
total_prem = premium * contracts * 100
ann_return = ((total_prem / (total_cash - total_prem)) * (365 / dte) * 100)
cda_credit = total_prem * 0.50
pass_impact = (total_prem / 50000) * 100
safety_buffer = ((price - strike) / price) * 100

# --- RESULTS ---
st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Annualized Return", f"{ann_return:.2f}%")
c2.metric("CDA Credit (Tax-Free)", f"${cda_credit:,.0f}")
c3.metric("Passive Limit Use", f"{pass_impact:.1f}%")

st.info(f"💰 **Cash Required (Collateral):** ${total_cash:,.2f}")

# --- CHECKLIST LOGIC ---
st.subheader("Final Battle Check")
r1 = vix_val > 20
r2 = safety_buffer > 8.0  # Proxy for Delta < 0.20
r3 = total_prem < 4166

def check_ui(label, condition):
    color = "green" if condition else "red"
    icon = "✅" if condition else "❌"
    st.markdown(f":{color}[{icon} {label}]")

check_ui(f"Market Fear (VIX: {vix_val:.2f} > 20)", r1)
check_ui(f"Probability (Margin: {safety_buffer:.1f}% > 8%)", r2)
check_ui(f"Tax Shield (Premium: ${total_prem:,.2f} < $4,166)", r3)
