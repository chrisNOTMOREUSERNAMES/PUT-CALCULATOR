import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Holdco Pro Terminal 2026", layout="wide")

st.title("🛡️ Holdco Pro Option Terminal")

# --- CACHED DATA FETCHING (Returns simple types only) ---
@st.cache_data(ttl=300)
def fetch_ticker_basics(symbol):
    try:
        tk = yf.Ticker(symbol)
        # Fetching info can be slow, so we cache the results
        info = tk.info
        price = info.get('regularMarketPrice') or info.get('previousClose')
        expirations = tk.options
        
        vix_tk = yf.Ticker("^VIX")
        vix_price = vix_tk.info.get('regularMarketPrice') or vix_tk.info.get('previousClose')
        
        return price, expirations, vix_price
    except Exception as e:
        return None, None, None

@st.cache_data(ttl=300)
def fetch_option_chain(symbol, expiry):
    try:
        tk = yf.Ticker(symbol)
        chain = tk.option_chain(expiry)
        # Convert the dataframe to a plain dict or keep as DF (Streamlit can cache DFs)
        return chain.puts
    except:
        return pd.DataFrame()

# --- SIDEBAR ---
st.sidebar.header("1. Asset Selection")
ticker_sym = st.sidebar.text_input("Ticker", value="SPY").upper()
contracts = st.sidebar.number_input("Contracts", value=5, min_value=1)

curr_price, expirations, curr_vix = fetch_ticker_basics(ticker_sym)

if curr_price and expirations:
    # --- OPTION SELECTORS ---
    st.sidebar.header("2. Option Selection")
    selected_expiry = st.sidebar.selectbox("Select Expiry Date", expirations)
    
    # Fetch the puts for the selected expiry
    puts_df = fetch_option_chain(ticker_sym, selected_expiry)
    
    if not puts_df.empty:
        # Filter for Out-of-the-Money Puts
        otm_puts = puts_df[puts_df['strike'] < curr_price].sort_values('strike', ascending=False)
        
        if not otm_puts.empty:
            selected_strike = st.sidebar.selectbox("Select Strike Price", otm_puts['strike'])
            opt_row = otm_puts[otm_puts['strike'] == selected_strike].iloc[0]
            
            # Extract values
            live_prem = opt_row['lastPrice']
            # Implied Volatility calculation
            live_iv = (opt_row['impliedVolatility'] * 100) if 'impliedVolatility' in opt_row else 0
            
            # --- CALCULATIONS ---
            total_cash = selected_strike * contracts * 100
            total_prem = live_prem * contracts * 100
            cda_credit = total_prem * 0.50
            pass_impact = (total_prem / 50000) * 100
            safety_margin = ((curr_price - selected_strike) / curr_price) * 100
            
            expiry_dt = datetime.strptime(selected_expiry, '%Y-%m-%d')
            dte = (expiry_dt - datetime.now()).days
            if dte <= 0: dte = 1
            ann_return = ((total_prem / (total_cash - total_prem)) * (365 / dte) * 100)

            # --- UI DISPLAY ---
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Stock Price", f"${curr_price:.2f}")
            col2.metric("Put Premium (Last)", f"${live_prem:.2f}")
            col3.metric("Implied Vol (IV)", f"{live_iv:.1f}%")
            col4.metric("VIX Index", f"{curr_vix:.2f}")

            st.divider()

            c_left, c_right = st.columns([1, 2])
            with c_left:
                st.subheader("Holdco Battle Check")
                # Updated Rule 1: Panic Premium
                r1 = curr_vix > 20
                # Updated Rule 2: IV Check
                r2 = live_iv > 20
                # Updated Rule 3: Safety (Probability Proxy)
                r3 = safety_margin > 8.0
                # Updated Rule 4: Tax Protection
                r4 = total_prem < 4166
                
                def check(label, cond, val):
                    color = "green" if cond else "red"
                    st.markdown(f":{color}[{'✅' if cond else '❌'} {label}: **{val}**]")

                check("Market Fear (VIX)", r1, f"{curr_vix:.2f}")
                check("IV Level (Relative Value)", r2, f"{live_iv:.1f}%")
                check("Safety (OTM Margin)", r3, f"{safety_margin:.1f}%")
                check("Tax Shield (Monthly Cap)", r4, f"${total_prem:,.0f}")

            with c_right:
                st.subheader("Capital Analysis")
                st.write(f"💰 **Cash Required (Collateral):** ${total_cash:,.2f}")
                st.write(f"🍁 **Tax-Free CDA Credit:** ${cda_credit:,.2f}")
                st.progress(min(pass_impact/100, 1.0), text=f"Passive Income Threshold Use: {pass_impact:.1f}%")
                st.metric("Annualized Return", f"{ann_return:.2f}%")
        else:
            st.warning("No OTM puts available for this expiry.")
    else:
        st.warning("Could not load the option chain.")
else:
    st.error("Ticker data unavailable. Check the symbol or try again later.")
