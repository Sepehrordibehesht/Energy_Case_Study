import numpy as np
import random
from house import House
from car import Car
from data_frames import hourly_data_solar

def run_simulation(num_houses, num_solar, num_evs, num_smart_evs, seed=42):
    """
    Run the 168-hour simulation and return results.
    Returns dict with keys: houses, solar_houses, evs, totals, per_hour (dict)
    """
    np.random.seed(seed)
    random.seed(seed)

    houses = [House(house_id=i) for i in range(1, num_houses + 1)]

    # assign solar
    solar_houses = []
    if num_solar > 0:
        solar_houses = list(np.random.choice(houses, num_solar, replace=False))
        # align solar (model.py used "Energy(Wh)" column and a 6-hour roll)
        aligned_solar = np.roll(hourly_data_solar["Energy(Wh)"].values[:168], 6)
        for house in solar_houses:
            house.has_solar = True
            house.df["solar_production_Wh"] = aligned_solar

    # assign EVs
    evs = []
    if num_evs > 0:
        ev_houses = list(np.random.choice(houses, num_evs, replace=False))
        for i, house in enumerate(ev_houses, start=1):
            smart = True if i <= num_smart_evs else False
            current_charge = np.random.randint(1000, 60000)
            car = Car(car_id=i, house=house, current_charge=current_charge, smart=smart)
            house.assign_ev(car)
            evs.append(car)

    # helper for daily leave/return
    def sample_leave_return_for_week():
        intervals = []
        for day in range(7):
            leave_local = 7 + random.choice([-1, 0, 1])
            return_local = 19 + random.choice([-1, 0, 1])
            leave = day * 24 + leave_local
            ret = day * 24 + return_local
            if ret <= leave:
                ret = min(leave + 8, day*24 + 23)
            intervals.append((leave, ret))
        return intervals

    # build events and mark away hours (ev_charge_Wh = np.nan while away)
    events = {}
    for ev in evs:
        intervals = sample_leave_return_for_week()
        for leave, ret in intervals:
            events.setdefault(leave, []).append((ev, "unplug"))
            events.setdefault(ret, []).append((ev, "plug"))
            for h in range(leave, min(ret, 168)):
                ev.house.df.loc[h, "ev_charge_Wh"] = np.nan

    # run simulation
    for hour in range(168):
        for (ev, action) in events.get(hour, []):
            if action == "unplug":
                ev.unplug(hour)
            elif action == "plug":
                return_charge = random.randint(int(0.10 * ev.capacity), int(0.40 * ev.capacity))
                ev.current_charge = return_charge
                ev.plug(hour)
                try:
                    ev.house.df.loc[hour, "ev_charge_Wh"] = ev.current_charge
                except Exception:
                    pass

        for ev in evs:
            if not ev.connected:
                continue
            if ev.current_charge < ev.capacity:
                charged = ev.charge(hour)
                ev.current_charge = min(ev.capacity, ev.current_charge + charged)
                ev.house.df.loc[hour, "ev_charge_Wh"] = ev.current_charge

    # compute totals and per-hour aggregates
    total_all_Wh = sum(h.df["energy_consumption_Wh"].sum() for h in houses)
    total_smart_Wh = sum(h.df["energy_consumption_Wh"].sum() for h in houses if h.ev_type == "Smart")
    total_non_smart_Wh = sum(h.df["energy_consumption_Wh"].sum() for h in houses if h.ev_type == "Non-Smart")
    total_no_ev_Wh = sum(h.df["energy_consumption_Wh"].sum() for h in houses if h.ev is None)

    num_smart = sum(1 for h in houses if h.ev_type == "Smart")
    num_non_smart = sum(1 for h in houses if h.ev_type == "Non-Smart")
    num_no_ev = sum(1 for h in houses if h.ev is None)

    average_smart_Wh = total_smart_Wh / num_smart if num_smart > 0 else 0.0
    average_non_smart_Wh = total_non_smart_Wh / num_non_smart if num_non_smart > 0 else 0.0
    average_no_ev_Wh = total_no_ev_Wh / num_no_ev if num_no_ev > 0 else 0.0

    # peak hours totals (6-8 am and 6-9 pm)
    peak_hours = list(range(6, 9)) + list(range(18, 22))
    total_peak_Wh = sum(h.df[h.df["time"].dt.hour.isin(peak_hours)]["energy_consumption_Wh"].sum() for h in houses)
    total_peak_smart_Wh = sum(h.df[h.df["time"].dt.hour.isin(peak_hours)]["energy_consumption_Wh"].sum() for h in houses if h.ev_type == "Smart")
    total_peak_non_smart_Wh = sum(h.df[h.df["time"].dt.hour.isin(peak_hours)]["energy_consumption_Wh"].sum() for h in houses if h.ev_type == "Non-Smart")

    # total energy from solar consumed for charging smart EVs in solar houses (approximate)
    total_solar_ev_Wh = 0.0
    for house in solar_houses:
        if house.ev is not None and house.ev_type == "Smart":
            for hour in range(168):
                ev_charge = house.df.loc[hour, "ev_charge_Wh"]
                if not np.isnan(ev_charge) and ev_charge < house.ev.capacity:
                    solar_used = min(house.df.loc[hour, "solar_production_Wh"], house.ev.power)
                    total_solar_ev_Wh += float(solar_used)

    totals = {
        "total_all_Wh": total_all_Wh,
        "total_smart_Wh": total_smart_Wh,
        "total_non_smart_Wh": total_non_smart_Wh,
        "total_no_ev_Wh": total_no_ev_Wh,
        "average_smart_Wh": average_smart_Wh,
        "average_non_smart_Wh": average_non_smart_Wh,
        "average_no_ev_Wh": average_no_ev_Wh,
        "total_peak_Wh": total_peak_Wh,
        "total_peak_smart_Wh": total_peak_smart_Wh,
        "total_peak_non_smart_Wh": total_peak_non_smart_Wh,
        "total_solar_ev_Wh": total_solar_ev_Wh,
        "counts": {"num_houses": num_houses, "num_smart": num_smart, "num_non_smart": num_non_smart, "num_no_ev": num_no_ev}
    }

    # per-hour totals (168)
    per_hour_all = np.array([sum(h.df.loc[hr, "energy_consumption_Wh"] for h in houses) for hr in range(168)])
    per_hour_smart = np.array([sum(h.df.loc[hr, "energy_consumption_Wh"] for h in houses if h.ev_type == "Smart") for hr in range(168)])
    per_hour_non_smart = np.array([sum(h.df.loc[hr, "energy_consumption_Wh"] for h in houses if h.ev_type == "Non-Smart") for hr in range(168)])

    per_hour = {
        "all": per_hour_all,
        "smart": per_hour_smart,
        "non_smart": per_hour_non_smart
    }

    return {
        "houses": houses,
        "solar_houses": solar_houses,
        "evs": evs,
        "totals": totals,
        "per_hour": per_hour
    }