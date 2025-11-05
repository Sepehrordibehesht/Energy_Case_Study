import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd
from simulation import run_simulation

st.title("Energy case study — simulation UI")

num_houses = st.number_input("Number of houses", min_value=1, value=100, step=1)
num_solar = st.number_input("Number of solar houses", min_value=0, max_value=int(num_houses), value=50, step=1)
num_evs = st.number_input("Number of EVs", min_value=0, max_value=int(num_houses), value=20, step=1)
num_smart = st.number_input("Number of Smart EVs", min_value=0, max_value=int(num_evs), value=10, step=1)

# Run simulation and save result in session_state to avoid recomputing on UI interactions
if st.button("Run simulation"):
    with st.spinner("Running..."):
        # pass seed for deterministic results consistent with simulation.py
        res = run_simulation(int(num_houses), int(num_solar), int(num_evs), int(num_smart), seed=42)
    st.session_state["res"] = res
    st.session_state["params"] = (int(num_houses), int(num_solar), int(num_evs), int(num_smart))

# If we have stored results, show them. Otherwise prompt user to run.
if "res" not in st.session_state:
    st.info("Click 'Run simulation' to compute results. Slider changes won't trigger recomputation once results are stored.")
else:
    # warn if inputs changed since last run
    current_params = (int(num_houses), int(num_solar), int(num_evs), int(num_smart))
    if st.session_state.get("params") != current_params:
        st.warning("Simulation results were produced with different input parameters. Click 'Run simulation' to recompute with the new settings.")

    res = st.session_state["res"]
    totals = res["totals"]

    # Totals and averages
    st.metric("Total energy (all houses)", f"{totals['total_all_Wh']/1000:.1f} kWh")
    st.write("Breakdown (totals):")
    st.write(f"Smart EV houses: {totals['total_smart_Wh']/1000:.1f} kWh")
    st.write(f"Non‑Smart EV houses: {totals['total_non_smart_Wh']/1000:.1f} kWh")
    st.write(f"No EV houses: {totals['total_no_ev_Wh']/1000:.1f} kWh")

    st.write("Per-house averages (Wh/week):")
    st.write(f"Avg per Smart EV house: {totals['average_smart_Wh']:.1f} Wh/week ({totals['average_smart_Wh']/1000:.2f} kWh/week)")
    st.write(f"Avg per Non-Smart EV house: {totals['average_non_smart_Wh']:.1f} Wh/week ({totals['average_non_smart_Wh']/1000:.2f} kWh/week)")
    st.write(f"Avg per No-EV house: {totals['average_no_ev_Wh']:.1f} Wh/week ({totals['average_no_ev_Wh']/1000:.2f} kWh/week)")

    # show peak-hour totals and solar used for EV charging
    st.write(f"Total energy during peak hours (6-8am, 6-9pm): {totals['total_peak_Wh']/1000:.1f} kWh")
    st.write(f"Peak energy — Smart EV houses: {totals['total_peak_smart_Wh']/1000:.1f} kWh")
    st.write(f"Peak energy — Non-Smart EV houses: {totals['total_peak_non_smart_Wh']/1000:.1f} kWh")
    st.write(f"Estimated solar energy used for smart EV charging (solar houses): {totals['total_solar_ev_Wh']/1000:.1f} kWh")
    st.write(f"Total solar energy produced by solar houses: {totals.get('total_solar_production_Wh', 0)/1000:.1f} kWh")

    # show how many smart houses had solar (model.py reported this)
    st.write(f"Smart EV houses with solar (count): {totals['counts'].get('smart_houses_with_solar', 0)}")

    day = st.slider("Select day to plot (0=day1 .. 6=day7)", 0, 6, 1)
    start = day*24
    hours = list(range(24))
    per_hour_all = res["per_hour"]["all"][start:start+24]
    per_hour_smart = res["per_hour"]["smart"][start:start+24]
    per_hour_non = res["per_hour"]["non_smart"][start:start+24]

    df_plot = pd.DataFrame({
        "hour": hours,
        "all": per_hour_all,
        "smart": per_hour_smart,
        "non_smart": per_hour_non
    }).set_index("hour")

    st.line_chart(df_plot)

    # daily totals for all 7 days
    per_hour_all_full = res["per_hour"]["all"]
    per_hour_smart_full = res["per_hour"]["smart"]
    per_hour_non_full = res["per_hour"]["non_smart"]

    per_day_all = per_hour_all_full.reshape(7, 24).sum(axis=1)
    per_day_smart = per_hour_smart_full.reshape(7, 24).sum(axis=1)
    per_day_non = per_hour_non_full.reshape(7, 24).sum(axis=1)

    df_days = pd.DataFrame({
        "day": [f"Day {i+1}" for i in range(7)],
        "all_Wh": per_day_all,
        "smart_Wh": per_day_smart,
        "non_smart_Wh": per_day_non
    }).set_index("day")

    st.subheader("Daily totals (all 7 days)")
    st.table(df_days)

    st.subheader("Daily totals chart")
    st.bar_chart(df_days)

    # downloads
    if st.checkbox("Download daily totals CSV"):
        st.download_button("Download daily totals", data=df_days.to_csv(), file_name="daily_totals.csv", mime="text/csv")

    if st.checkbox("Download results as CSV"):
        all_houses_df = pd.concat([h.df.assign(house_id=h.house_id) for h in res["houses"]], ignore_index=True)
        csv = all_houses_df.to_csv(index=False)
        st.download_button("Download CSV", data=csv, file_name="simulation_results.csv", mime="text/csv")