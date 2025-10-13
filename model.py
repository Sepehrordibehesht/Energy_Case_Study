import numpy as np
import random
from house import House
from car import Car
from data_frames import hourly_data_solar

# ---------------------------
# 1️⃣ Create 100 houses
# ---------------------------
np.random.seed(42)
random.seed(42)

houses = [House(house_id=i) for i in range(1, 101)]

# ---------------------------
# 2️⃣ Assign 50 houses to have solar
# ---------------------------
solar_houses = np.random.choice(houses, 50, replace=False)
for house in solar_houses:
    house.has_solar = True
    # Use Wh for hourly production
    aligned_solar = np.roll(hourly_data_solar["Power(W)"].values[:168], 6)
    house.df["solar_production_Wh"] = aligned_solar

# ---------------------------
# 3️⃣ Assign 20 EVs (10 smart, 10 non-smart)
# ---------------------------
evs = []
ev_houses = np.random.choice(houses, 20, replace=False)

for i, house in enumerate(ev_houses, start=1):
    smart = True if i > 10 else False
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
    # quick checks
    print("Sample house ev df (house 1):")
    print(houses[54].df.head(30))
