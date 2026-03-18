import streamlit as st
import yfinance as yf
import pandas as pd
from curl_cffi import requests
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(page_title="The Wheel Strategy Scanner", layout="wide")

# --- Sidebar Inputs ---
st.sidebar.header("Strategy Parameters")
ticker_input = st.sidebar.text_input("Ticker (e.g., SPY, TD.TO, RY.TO)", "SPY").upper()
target_dte = st.sidebar.slider("Days to Expiration (DTE)", 15, 60, 45)
min_otm = st.sidebar.slider("Min % Out-of-the-Money", 1, 15, 5)
max_otm = st.sidebar.slider("Max % Out-of-the-Money", 5, 25, 10)

st.title("🛞 The Wheel & Hedged Put Scanner")
st.caption("Identify 'Pump' exit levels (Calls) and 'Happy to Buy' entry levels (Puts).")

def get_data(ticker):
    """Fetches option and price data using browser impersonation."""
    session = requests.Session(impersonate="chrome")
    tk = yf.Ticker(ticker, session=session)
    
    try:
        # Get Price
        history = tk.history(period="5d")
        if history.empty:
            return None, None, None
        current_price = history['Close'].iloc[-1]
        
        # Get Expirations
        expirations = tk.options
        if not expirations:
            return None, None, None
        
        # Find closest expiry to target DTE
        today = datetime.now()
        target_date = today + timedelta(days=target_dte)
        best_expiry = min(expirations, key=lambda x: abs(datetime.strptime(x, '%Y-%m-%d') - target_date))
        
        # Get Puts
        chain = tk.option_chain(best_expiry)
        puts = chain.puts
        
        # Add Metrics
        puts = puts[puts['strike'] < current_price].copy()
        puts['OTM_pct'] = ((current_price - puts['strike']) / current_price) * 100
        puts['ROC_Monthly'] = (puts['lastPrice'] / puts['strike']) * 100
        puts['Annualized_Return'] = puts['ROC_Monthly'] * (365 / target_dte)
        
        return puts, current_price, best_expiry
        
    except Exception as e:
        st.error(f"Error fetching {ticker}: {e}")
        return None, None, None

# --- Main Dashboard Logic ---
if ticker_input:
    puts_df, price, expiry = get_data(ticker_input)
    
    if puts_df is not None:
        # Display Header Metrics
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric(f"{ticker_input} Price", f"${price:.2f}")
        col_m2.metric("Target Expiry", expiry)
        col_m3.metric("Current DTE", (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days)

        # 1. Filtered Short Put Candidates
        st.subheader(f"Step 1: Sell Cash-Secured Puts ({min_otm}% - {max_otm}% OTM)")
        candidates = puts_df[(puts_df['OTM_pct'] >= min_otm) & (puts_df['OTM_pct'] <= max_otm)]
        
        if not candidates.empty:
            display_cols = ['strike', 'lastPrice', 'bid', 'ask', 'OTM_pct', 'ROC_Monthly', 'Annualized_Return']
            st.dataframe(candidates[display_cols].sort_values(by='strike', ascending=False), use_container_width=True)
            
            # 2. Spread / Insurance Builder
            st.divider()
            st.subheader("Step 2: Add 'Big Drop' Insurance (The Hedged Wheel)")
            
            c1, c2 = st.columns(2)
            with c1:
                sell_strike = st.selectbox("Select Short Put Strike (Your Entry Level)", candidates['strike'])
            with c2:
                # Filter for insurance strikes below the sell strike
                insurance_options = puts_df[puts_df['strike'] < sell_strike]
                if not insurance_options.empty:
                    buy_strike = st.selectbox("Select Insurance Put Strike (The Floor)", insurance_options['strike'][::-1])
                else:
                    st.warning("No lower strikes available for insurance.")
                    buy_strike = None

            if buy_strike:
                # Calculate Spread Metrics
                s_price = candidates[candidates['strike'] == sell_strike]['lastPrice'].values[0]
                b_price = insurance_options[insurance_options['strike'] == buy_strike]['lastPrice'].values[0]
                net_credit = s_price - b_price
                max_loss = (sell_strike - buy_strike) - net_credit
                
                st.success(f"""
                **Execution Summary:**
                * **Net Premium Collected:** ${net_credit * 100:.2f} 
                * **Maximum Risk (The Gap):** ${max_loss * 100:.2f}
                * **Insurance Cost:** {((b_price/s_price)*100):.1f}% of your premium income.
                """)
        else:
            st.warning(f"No strikes found in the {min_otm}-{max_otm}% OTM range for this DTE.")
            
    else:
        st.info("Please ensure the ticker is correct and you are not currently rate-limited by Yahoo.")

# --- Helpful Strategy Note ---
st.sidebar.divider()
st.sidebar.info("""
**Note on Tax Efficiency (HoldCo):**
Frequent option trading may be viewed as business income by the CRA. To maintain capital gains treatment, aim for longer-dated options (30-45+ DTE) and avoid high-frequency 'churning' of the same position.
""")
