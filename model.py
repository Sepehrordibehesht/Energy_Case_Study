import numpy as np
import random
from house import House
from car import Car
from data_frames import hourly_data_solar
import matplotlib.pyplot as plt

def prompt_int(prompt, min_val=None, max_val=None):
    """Prompt repeatedly until the user enters a valid integer within bounds."""
    while True:
        try:
            val = input(prompt)
            ival = int(val)
            if min_val is not None and ival < min_val:
                print(f"Value must be >= {min_val}. Try again.")
                continue
            if max_val is not None and ival > max_val:
                print(f"Value must be <= {max_val}. Try again.")
                continue
            return ival
        except ValueError:
            print("Invalid integer. Please try again.")

# User input (no defaults; user must enter valid integers)
num_houses = prompt_int("Enter number of houses (integer >= 1): ", min_val=1)
num_solar = prompt_int(f"Enter number of solar houses (0-{num_houses}): ", min_val=0, max_val=num_houses)
num_evs = prompt_int(f"Enter number of EVs (0-{num_houses}): ", min_val=0, max_val=num_houses)
num_smart_evs = prompt_int(f"Enter number of Smart EVs (0-{num_evs}): ", min_val=0, max_val=num_evs)
num_non_smart_evs = num_evs - num_smart_evs



# ---------------------------
# 1️⃣ Create houses
# ---------------------------
np.random.seed(42)
random.seed(42)

houses = [House(house_id=i) for i in range(1, num_houses + 1)]

# ---------------------------
# 2️⃣ Assign solar houses
# ---------------------------
solar_houses = np.random.choice(houses, num_solar, replace=False)
for house in solar_houses:
    house.has_solar = True
    # Use Wh for hourly production
    aligned_solar = np.roll(hourly_data_solar["Power(W)"].values[:168], 6)
    house.df["solar_production_Wh"] = aligned_solar

# ---------------------------
# 3️⃣ Assign EVs (smart and non-smart)
# ---------------------------
evs = []
ev_houses = np.random.choice(houses, num_evs, replace=False)

for i, house in enumerate(ev_houses, start=1):
    smart = True if i <= num_smart_evs else False
    current_charge = np.random.randint(1000, 60000)  # initial charge in Wh
    car = Car(car_id=i, house=house, current_charge=current_charge, smart=smart)
    house.assign_ev(car)
    evs.append(car)

# ---------------------------
# Helper: create daily leave/return windows
# ---------------------------
def sample_leave_return_for_week():
    """
    For each day 0..6 sample leave ~07:00 +/-1 and return ~19:00 +/-1.
    Returns list of tuples (leave_hour_index, return_hour_index) for the 7 days.
    """
    intervals = []
    for day in range(7):
        leave_local = 7 + random.choice([-1, 0, 1]) 
        return_local = 19 + random.choice([-1, 0, 1])
        leave = day * 24 + leave_local 
        ret = day * 24 + return_local 
        # safety: ensure return after leave; if not, push return forward within the day
        if ret <= leave:
            ret = min(leave + 8, day*24 + 23)  # at least some hours away, cap to day end
        intervals.append((leave, ret))
    return intervals

# ---------------------------
# 4️⃣ Build plug/unplug events and mark away hours in dataframes
# ---------------------------
# events: hour -> list of (car, action) with action in {'unplug','plug'}
events = {}

for ev in evs:
    intervals = sample_leave_return_for_week()
    for leave, ret in intervals:
        # mark events
        events.setdefault(leave, []).append((ev, "unplug"))
        events.setdefault(ret, []).append((ev, "plug"))
        # mark away hours in the house df (set ev_charge_Wh to nan while away)
        for h in range(leave, min(ret, 168)):
            ev.house.df.loc[h, "ev_charge_Wh"] = np.nan

# ---------------------------
# 5️⃣ Run hourly simulation over 168 hours
# ---------------------------
for hour in range(168):
    # first process plug/unplug events at this hour
    for (ev, action) in events.get(hour, []):
        if action == "unplug":
            ev.unplug(hour)
        elif action == "plug":
            # sample arrival SoC between 10% and 40% of capacity (e.g. 60000 Wh)
            return_charge = random.randint(int(0.10 * ev.capacity), int(0.40 * ev.capacity))
            ev.current_charge = return_charge
            ev.plug(hour)
            # ensure dataframe reflects arrival SoC
            try:
                ev.house.df.loc[hour, "ev_charge_Wh"] = ev.current_charge
            except Exception:
                pass

    # then allow charging for cars that are connected at this hour
    for ev in evs:
        if not ev.connected:
            # ensure df shows -1000 while away (already set) and skip charging
            continue

        # if connected and not full, attempt one hour charge
        if ev.current_charge < ev.capacity:
            charged = ev.charge(hour)  # returns Wh actually charged this hour
            # increment current charge and cap
            ev.current_charge = min(ev.capacity, ev.current_charge + charged)
            # write the new charge state into the dataframe for this hour
            ev.house.df.loc[hour, "ev_charge_Wh"] = ev.current_charge

# ---------------------------
# (optional) After-sim: inspect results
# ---------------------------
if __name__ == "__main__":
    # compute scalar totals (Wh) across houses
    total_all_Wh = sum(house.df["energy_consumption_Wh"].sum() for house in houses)
    total_smart_Wh = sum(house.df["energy_consumption_Wh"].sum() for house in houses if house.ev_type == "Smart")
    total_non_smart_Wh = sum(house.df["energy_consumption_Wh"].sum() for house in houses if house.ev_type == "Non-Smart")
    total_no_ev_Wh = sum(house.df["energy_consumption_Wh"].sum() for house in houses if house.ev is None)

    print(f"Total all houses: {total_all_Wh} Wh ({total_all_Wh/1000:.1f} kWh)")
    print(f"Total houses with Smart EVs: {total_smart_Wh} Wh ({total_smart_Wh/1000:.1f} kWh)")
    print(f"Total houses with Non‑Smart EVs: {total_non_smart_Wh} Wh ({total_non_smart_Wh/1000:.1f} kWh)")
    print(f"Total houses with no EV: {total_no_ev_Wh} Wh ({total_no_ev_Wh/1000:.1f} kWh)")

    #total energy consumed in peak hours (6-8 am and 6-9 pm) for all houses
    peak_hours = list(range(6, 9)) + list(range(18, 22))
    total_peak_Wh = sum(house.df[house.df["time"].dt.hour.isin(peak_hours)]["energy_consumption_Wh"].sum() for house in houses)
    print(f"Total energy consumed in peak hours by all houses(6-8 am and 6-9 pm): {total_peak_Wh} Wh ({total_peak_Wh/1000:.1f} kWh)")
    #total energy consumed in peak hours (6-8 am and 6-9 pm) for smart ev houses
    total_peak_smart_Wh = sum(house.df[house.df["time"].dt.hour.isin(peak_hours)]["energy_consumption_Wh"].sum() for house in houses if house.ev_type == "Smart")
    print(f"Total energy consumed in peak hours by smart ev houses(6-8 am and 6-9 pm): {total_peak_smart_Wh} Wh ({total_peak_smart_Wh/1000:.1f} kWh)")
    #total energy consumed in peak hours (6-8 am and 6-9 pm) for non-smart ev houses
    total_peak_non_smart_Wh = sum(house.df[house.df["time"].dt.hour.isin(peak_hours)]["energy_consumption_Wh"].sum() for house in houses if house.ev_type == "Non-Smart")
    print(f"Total energy consumed in peak hours by non-smart ev houses(6-8 am and 6-9 pm): {total_peak_non_smart_Wh} Wh ({total_peak_non_smart_Wh/1000:.1f} kWh)")
    
    #total energy from solar power consumed for charging evs in solar houses
    total_solar_ev_Wh = 0
    for house in solar_houses:
        if house.ev is not None and house.ev_type == "Smart" and house.ev.connected:
            for hour in range(168):
                if house.df.loc[hour, "ev_charge_Wh"] < house.ev.capacity:
                    solar_used = min(house.df.loc[hour, "solar_production_Wh"], house.ev.power)
                    total_solar_ev_Wh += solar_used
    print(f"Total energy from solar power consumed for charging smart evs in solar houses: {total_solar_ev_Wh} Wh ({total_solar_ev_Wh/1000:.1f} kWh)")

    #Now we choose one day and make a bar chart for 24 hours of energy consumption of all houses, smart ev houses, non-smart ev houses, and no ev houses
    day = 2  # choose day 2 (0-based index)
    start_hour = day * 24
    end_hour = start_hour + 24
    hours = list(range(24))

    # compute per-hour totals (sum across houses) for each of the 24 hours
    all_consumption = [
        sum(house.df.loc[start_hour + h, "energy_consumption_Wh"] for house in houses)
        for h in hours
    ]
    smart_consumption = [
        sum(house.df.loc[start_hour + h, "energy_consumption_Wh"] for house in houses if house.ev_type == "Smart")
        for h in hours
    ]
    non_smart_consumption = [
        sum(house.df.loc[start_hour + h, "energy_consumption_Wh"] for house in houses if house.ev_type == "Non-Smart")
        for h in hours
    ]
    no_ev_consumption = [
        sum(house.df.loc[start_hour + h, "energy_consumption_Wh"] for house in houses if house.ev is None)
        for h in hours
    ]

    solar_houses_consumption = [
        sum(house.df.loc[start_hour + h, "energy_consumption_Wh"] for house in solar_houses)
        for h in hours
    ]

    non_solar_houses = [house for house in houses if not house.has_solar]
    non_solar_houses_consumption = [
        sum(house.df.loc[start_hour + h, "energy_consumption_Wh"] for house in non_solar_houses)
        for h in hours
    ]

    # Plotting (use lines to avoid bar-group complexity)
    plt.figure(figsize=(12, 6))
    plt.plot(hours, all_consumption, marker='o', label="All Houses", color='gray')
    plt.plot(hours, smart_consumption, marker='o', label="Smart EV Houses", color='blue')
    plt.plot(hours, non_smart_consumption, marker='o', label="Non-Smart EV Houses", color='orange')
    plt.plot(hours, no_ev_consumption, marker='o', label="No EV Houses", color='red')
    plt.plot(hours, solar_houses_consumption, marker='o', label="Solar Houses", color='green')
    plt.plot(hours, non_solar_houses_consumption, marker='o', label="Non-Solar Houses", color='purple')
    plt.xlabel("Hour of Day")
    plt.ylabel("Energy Consumption (Wh)")
    plt.title(f"Energy Consumption on Day {day + 1} (All, Smart EV, Non-Smart EV, No EV, Solar, Non-Solar)")
    plt.legend()
    plt.xticks(hours)
    plt.grid(axis='y')
    plt.savefig("energy_consumption_day3.png")
