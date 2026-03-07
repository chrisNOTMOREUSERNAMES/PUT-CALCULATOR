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
                "Premium": f"${prem:.2f}",
                "IV %": f"{opt['impliedVolatility']*100:.1f}%",
                "Annualized Return": round(ann_ret, 2)
            })
        except:
            continue
    return pd.DataFrame(comparison_data)

# --- SIDEBAR & MAIN ---
st.title("🛡️ Holdco Expiry Comparison")
ticker_sym = st.sidebar.text_input("Ticker", value="SPY").upper()
target_strike = st.sidebar.number_input("Target Strike Price ($)", value=480.0)

curr_price, expirations, curr_vix = fetch_ticker_basics(ticker_sym)

if curr_price:
    st.metric(f"Current {ticker_sym} Price", f"${curr_price:.2f}", delta=f"VIX: {curr_vix:.2f}")
    
    # --- COMPARISON LOGIC ---
    st.subheader(f"Strategy: Puts near ${target_strike} Strike")
    with st.spinner("Analyzing all expiry dates..."):
        df_comp = compare_expiries(ticker_sym, target_strike, curr_price)
    
    if not df_comp.empty:
        # Visualizing the Sweet Spot
        fig = px.bar(df_comp, x='Expiry', y='Annualized Return', 
                     title="Annualized Return by Expiry",
                     color='Annualized Return', color_continuous_scale='Blues')
        st.plotly_chart(fig, use_container_width=True)
        
        # Comparison Table
        st.dataframe(df_comp, use_container_width=True, hide_index=True)
        
        st.info("💡 **Holdco Logic:** Longer dates (further right) usually have higher premiums but lower *Annualized Returns*. Look for the spike where IV is highest.")
    else:
        st.error("No data found for this strike range.")
else:
    st.error("Invalid Ticker.")
