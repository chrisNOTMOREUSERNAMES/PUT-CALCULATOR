import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="The Wheel Scanner", layout="wide")

st.title("🛞 The Wheel Strategy Dashboard")
ticker_input = st.sidebar.text_input("Enter Ticker (e.g., RY, TD, SPY)", "SPY")
target_dte = st.sidebar.slider("Target DTE", 15, 60, 45)
delta_target = st.sidebar.slider("Short Put Delta Target", 0.10, 0.40, 0.30)

def get_wheel_data(ticker):
    tk = yf.Ticker(ticker)
    current_price = tk.history(period="1d")['Close'].iloc[-1]
    
    # Get expiration dates
    expirations = tk.options
    if not expirations:
        return None, None
    
    # Find expiration closest to target DTE
    today = datetime.now()
    target_date = today + timedelta(days=target_dte)
    best_expiry = min(expirations, key=lambda x: abs(datetime.strptime(x, '%Y-%m-%d') - target_date))
    
    # Fetch Puts for that expiry
    opt_chain = tk.option_chain(best_expiry)
    puts = opt_chain.puts
    
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
        # We look for strikes roughly 5-8% OTM as a proxy for 0.30 Delta
        short_put_candidates = data[(data['OTM_pct'] > 5) & (data['OTM_pct'] < 10)]
        
        st.write("### Potential Short Put Candidates (Approx. 0.30 Delta)")
        st.dataframe(short_put_candidates[['strike', 'lastPrice', 'OTM_pct', 'ROC_Monthly', 'Annualized_Return']])
        
        # Insurance Put Logic
        st.divider()
        st.write("### Hedged Wheel (Protected Spread) Builder")
        col1, col2 = st.columns(2)
        
        with col1:
            sell_strike = st.selectbox("Select Short Put Strike", short_put_candidates['strike'])
        with col2:
            # Filter for strikes lower than the sell strike for insurance
            insurance_candidates = data[data['strike'] < sell_strike]
            buy_strike = st.selectbox("Select Insurance Put Strike", insurance_candidates['strike'][::-1])
            
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
        st.error("No option data found for this ticker.")
