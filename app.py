import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="The Wheel Scanner", layout="wide")

st.title("🛞 The Wheel Strategy Dashboard")
ticker_input = st.sidebar.text_input("Enter Ticker (e.g., RY, TD, SPY)", "SPY")
target_dte = st.sidebar.slider("Target DTE", 15, 60, 45)
delta_target = st.sidebar.slider("Short Put Delta Target", 0.10, 0.40, 0.30)

def get_wheel_data(ticker):
    # --- UPDATE: Custom Session to bypass Yahoo Finance Rate Limits ---
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    })
    
    # Pass the session to the Ticker object
    tk = yf.Ticker(ticker, session=session)
    # -----------------------------------------------------------------
    
    try:
        current_price = tk.history(period="1d")['Close'].iloc[-1]
    except Exception as e:
        st.error(f"Error fetching price data. Yahoo Finance might be blocking the request: {e}")
        return None, None, None
        
    # Get expiration dates
    expirations = tk.options
    if not expirations:
        return None, None, None
    
    # Find expiration closest to target DTE
    today = datetime.now()
    target_date = today + timedelta(days=target_dte)
    best_expiry = min(expirations, key=lambda x: abs(datetime.strptime(x, '%Y-%m-%d') - target_date))
    
    # Fetch Puts for that expiry
    try:
        opt_chain = tk.option_chain(best_expiry)
        puts = opt_chain.puts
    except Exception as e:
        st.error(f"Error fetching option chain: {e}")
        return None, None, None
    
    # Filter for Out-of-the-Money (OTM)
    puts = puts[puts['strike'] < current_price].copy()
    
    # Calculate simple 'Moneyness' as a Delta proxy if Delta isn't provided
    puts['OTM_pct'] = (current_price - puts['strike']) / current_price * 100
    
    # Estimated Return on Capital (ROC)
    puts['ROC_Monthly'] = (puts['lastPrice'] / puts['strike']) * 100
    puts['Annualized_Return'] = puts['ROC_Monthly'] * (365 / target_dte)
    
    return puts, current_price, best_expiry

if ticker_input:
    data, price, expiry = get_wheel_data(ticker_input)
    
    if data is not None:
        st.metric(f"{ticker_input} Price", f"${price:.2f}")
        st.subheader(f"Options for Expiry: {expiry}")
        
        # Filtering for the "Sweet Spot" (Short Put)
        # We look for strikes roughly 5-10% OTM as a proxy for 0.30 Delta
        short_put_candidates = data[(data['OTM_pct'] >= 5) & (data['OTM_pct'] <= 10)]
        
        st.write("### Potential Short Put Candidates (Approx. 0.30 Delta)")
        if not short_put_candidates.empty:
            st.dataframe(short_put_candidates[['strike', 'lastPrice', 'OTM_pct', 'ROC_Monthly', 'Annualized_Return']])
        else:
            st.warning("No short put candidates found in the 5-10% OTM range.")
        
        # Insurance Put Logic
        st.divider()
        st.write("### Hedged Wheel (Protected Spread) Builder")
        col1, col2 = st.columns(2)
        
        if not short_put_candidates.empty:
            with col1:
                sell_strike = st.selectbox("Select Short Put Strike", short_put_candidates['strike'])
            with col2:
                # Filter for strikes lower than the sell strike for insurance
                insurance_candidates = data[data['strike'] < sell_strike]
                
                if not insurance_candidates.empty:
                    buy_strike = st.selectbox("Select Insurance Put Strike", insurance_candidates['strike'][::-1]) # Reverse to show highest first
                    
                    # Calculate Spread Metrics
                    sell_prem = data[data['strike'] == sell_strike]['lastPrice'].values[0]
                    buy_prem = data[data['strike'] == buy_strike]['lastPrice'].values[0]
                    net_credit = sell_prem - buy_prem
                    max_risk = (sell_strike - buy_strike) - net_credit
                    
                    st.info(f"""
                    **Strategy Summary:**
                    * **Net Credit Collected:** ${net_credit * 100:.2f}
                    * **Max Risk (The Gap):** ${max_risk * 100:.2f}
                    * **Insurance Cost:** {((buy_prem/sell_prem)*100):.1f}% of premium income.
                    """)
                else:
                    st.warning("No lower strikes available for insurance.")
