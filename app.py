import streamlit as st
import yfinance as yf
import pandas as pd
from curl_cffi import requests # Updated import
from datetime import datetime, timedelta

st.set_page_config(page_title="The Wheel Scanner", layout="wide")

st.title("🛞 The Wheel Strategy Dashboard")
ticker_input = st.sidebar.text_input("Enter Ticker (e.g., RY, TD, SPY)", "SPY")
target_dte = st.sidebar.slider("Target DTE", 15, 60, 45)

def get_wheel_data(ticker):
    # Use curl_cffi to mimic a browser TLS fingerprint
    session = requests.Session(impersonate="chrome")
    
    # Pass the specialized session to yfinance
    tk = yf.Ticker(ticker, session=session)
    
    try:
        # Get price and options
        history = tk.history(period="1d")
        if history.empty:
            return None, None, None
        current_price = history['Close'].iloc[-1]
        
        expirations = tk.options
        if not expirations:
            return None, None, None
        
        # Find expiration closest to target DTE
        today = datetime.now()
        target_date = today + timedelta(days=target_dte)
        best_expiry = min(expirations, key=lambda x: abs(datetime.strptime(x, '%Y-%m-%d') - target_date))
        
        opt_chain = tk.option_chain(best_expiry)
        puts = opt_chain.puts
        
        # Calculations
        puts = puts[puts['strike'] < current_price].copy()
        puts['OTM_pct'] = (current_price - puts['strike']) / current_price * 100
        puts['ROC_Monthly'] = (puts['lastPrice'] / puts['strike']) * 100
        puts['Annualized_Return'] = puts['ROC_Monthly'] * (365 / target_dte)
        
        return puts, current_price, best_expiry
    except Exception as e:
        st.error(f"Data Retrieval Error: {e}")
        return None, None, None

if ticker_input:
    data, price, expiry = get_wheel_data(ticker_input)
    
    if data is not None:
        st.metric(f"{ticker_input} Price", f"${price:.2f}")
        st.subheader(f"Options for Expiry: {expiry}")
        
        # 0.30 Delta is often roughly 5-7% OTM
        short_put_candidates = data[(data['OTM_pct'] >= 5) & (data['OTM_pct'] <= 10)]
        
        if not short_put_candidates.empty:
            st.write("### Potential Short Put Candidates")
            st.dataframe(short_put_candidates[['strike', 'lastPrice', 'OTM_pct', 'ROC_Monthly', 'Annualized_Return']])
            
            # Spread Builder
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                sell_strike = st.selectbox("Select Short Put Strike", short_put_candidates['strike'])
            with col2:
                insurance_candidates = data[data['strike'] < sell_strike]
                if not insurance_candidates.empty:
                    buy_strike = st.selectbox("Select Insurance Put Strike", insurance_candidates['strike'][::-1])
                    
                    sell_p = data[data['strike'] == sell_strike]['lastPrice'].values[0]
                    buy_p = data[data['strike'] == buy_strike]['lastPrice'].values[0]
                    net = sell_p - buy_p
                    
                    st.success(f"Net Credit: ${net*100:.2f} | Max Risk: ${(sell_strike - buy_strike - net)*100:.2f}")
        else:
            st.warning("No strikes found in the target range. Try adjusting the ticker or DTE.")
