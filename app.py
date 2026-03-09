import streamlit as st

def insurance_layer_tab():
    st.header("🛡️ Phase 1.5: The Insurance Layer")
    
    col1, col2 = st.columns(2)
    
    with col1:
        spy_price = 672.38  # Current SPY price in Mar 2026
        target_strike = st.number_input("Target Entry Strike (e.g., Monthly 50 SMA)", value=640.0, step=5.0)
        put_premium = st.number_input("Premium Collected ($)", value=12.50)
        
    with col2:
        add_hedge = st.toggle("Add Downside Protection (Hedge)?", value=True)
        if add_hedge:
            # The "Deductible" - how much of a drop you take before insurance kicks in
            hedge_offset = st.slider("Hedge Strike (% below entry)", 2, 15, 5)
            hedge_strike = target_strike * (1 - (hedge_offset / 100))
            hedge_cost = st.number_input("Hedge Cost (Premium Paid)", value=2.50)
            
            net_premium = put_premium - hedge_cost
            max_risk = (target_strike - hedge_strike) - net_premium
        else:
            net_premium = put_premium
            max_risk = target_strike - net_premium

    # --- RESULTS DASHBOARD ---
    st.divider()
    m1, m2, m3 = st.columns(3)
    
    with m1:
        st.metric("Net Premium (Income)", f"${net_premium:.2f}", help="Total cash added to Holdco")
    with m2:
        st.metric("Max Floor Risk", f"${max_risk:.2f}", delta="-FIXED CAP", delta_color="normal")
    with m3:
        cda_room = net_premium * 0.5 * 100
        st.metric("CDA Room Generated", f"${cda_room:,.2f}", help="Tax-free withdrawal credit created")

    st.info(f"💡 **Strategic View:** If SPY gaps below **${hedge_strike:.2f}**, your loss stops. "
            f"You effectively have a **{hedge_offset}% deductible** on your SPY position.")

# Render the tab
insurance_layer_tab()
