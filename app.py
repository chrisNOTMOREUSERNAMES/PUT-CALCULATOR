import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="Holdco Pro: Expiry Battle", layout="wide")

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
    
    # We look at the first 8 expiries to keep it fast
    for expiry in tk.options[:8]:
        try:
            chain = tk.option_chain(expiry).puts
            # Find the contract closest to our target strike
            idx = (chain['strike'] - target_strike).abs().idxmin()
            opt = chain.loc[idx]
            
            # Math
            dte = (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days
            if dte <= 0: dte = 1
            
            prem = opt['lastPrice']
            total_cash = opt['strike'] * 100
            total_prem = prem * 100
            raw_ret = total_prem / (total_cash - total_prem)
            ann_ret = (raw_ret * (365 / dte) * 100)
            
            comparison_data.append({
                "Expiry": expiry,
                "DTE": dte,
                "Actual Strike": opt['strike'],
                "Premium": prem,
                "IV %": opt['impliedVolatility']*100,
                "Annualized Return": round(ann_ret, 2)
            })
        except:
            continue
    return pd.DataFrame(comparison_data)

# --- SIDEBAR INPUTS ---
st.sidebar.header("🛡️ Battle Parameters")
ticker_sym = st.sidebar.text_input("Ticker", value="SPY").upper()

# Keypad-friendly number input
target_strike = st.sidebar.number_input(
    "Target Strike Price ($)", 
    value=480.0, 
    step=0.5, 
    format="%.2f",
    help="Double-click to type a specific strike using your keypad."
)

contracts = st.sidebar.number_input("Contracts (100 sh ea)", value=5, min_value=1)

# --- MAIN INTERFACE ---
st.title("🛡️ Holdco Expiry Comparison")

curr_price, expirations, curr_vix = fetch_ticker_basics(ticker_sym)

if curr_price:
    # Top Level Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric(f"{ticker_sym} Price", f"${curr_price:.2f}")
    m2.metric("Market Fear (VIX)", f"{curr_vix:.2f}", delta="Panic Threshold: 20", delta_color="inverse")
    m3.metric("Target Strike", f"${target_strike:.2f}")

    # --- COMPARISON LOGIC ---
    st.divider()
    st.subheader(f"Battle Analysis: Puts near ${target_strike} Strike")
    
    with st.spinner("Scanning Option Chains..."):
        df_comp = compare_expiries(ticker_sym, target_strike, curr_price)
    
    if not df_comp.empty:
        # Charting the Sweet Spot
        fig = px.bar(df_comp, x='Expiry', y='Annualized Return', 
                     title="Yield Battle: Annualized Return % by Expiry",
                     color='Annualized Return', 
                     color_continuous_scale='Blues',
                     text_auto=True)
        st.plotly_chart(fig, use_container_width=True)
        
        # Formatting the table for display
        df_display = df_comp.copy()
        df_display['Premium'] = df_display['Premium'].map("${:,.2f}".format)
        df_display['IV %'] = df_display['IV %'].map("{:,.1f}%".format)
        df_display['Annualized Return'] = df_display['Annualized Return'].map("{:,.2f}%".format)
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # --- HOLDCO STRATEGY CHECK ---
        st.divider()
        st.subheader("📋 Holdco Battle Checklist")
        
        # Selection for specific row logic
        selected_expiry = st.selectbox("Select Expiry to Validate Strategy:", df_comp['Expiry'])
        row = df_comp[df_comp['Expiry'] == selected_expiry].iloc[0]
        
        # Logic Variables
        total_prem = float(row['Premium'].replace('$', '')) * contracts * 100 if isinstance(row['Premium'], str) else row['Premium'] * contracts * 100
        safety_margin = ((curr_price - row['Actual Strike']) / curr_price) * 100
        pass_impact = (total_prem / 50000) * 100
        cda_credit = total_prem * 0.50

        col_a, col_b = st.columns(2)
        with col_a:
            def check_ui(label, condition, val):
                color = "green" if condition else "red"
                icon = "✅" if condition else "❌"
                st.markdown(f":{color}[{icon} {label}: **{val}**]")

            check_ui("Market Fear (VIX > 20)", curr_vix > 20, f"{curr_vix:.2f}")
            check_ui("Safety Margin (> 8% OTM)", safety_margin > 8, f"{safety_margin:.1f}%")
            check_ui("Tax Shield (Premium < $4,166)", total_prem < 4166, f"${total_prem:,.2f}")
        
        with col_b:
            st.write(f"🍁 **Tax-Free CDA Credit:** ${cda_credit:,.2f}")
            st.write(f"⚖️ **Passive Threshold Use:** {pass_impact:.1f}%")
            st.write(f"💰 **Cash Required:** ${(row['Actual Strike'] * contracts * 100):,.2f}")

    else:
        st.error("No valid option data found for this strike range.")
else:
    st.error("Invalid Ticker or Data Connection Issue.")
