import pandas as pd
import numpy as np

class House:
    def __init__(self, house_id, has_solar=False, ev = None, ev_type=None):
        self.house_id = house_id
        self.has_solar = has_solar
        self.ev = ev
        self.ev_type = ev_type
        
        # Create hourly timestamps for one week (168 hours)
        hours = pd.date_range("2023-08-31", periods=168, freq="h")
        hod = hours.hour.values  # 0..23 repeated

        # Daily energy target (Wh) with a small random margin per house
        base_daily_Wh = 6630.0
        # small random margin between -2% and +5%
        margin = np.random.uniform(-0.02, 0.05)
        daily_target = base_daily_Wh * (1.0 + margin)

        # Build a 24-hour diurnal weight: evening peak + smaller morning peak + baseline
        evening_peak = np.exp(-0.5 * ((np.arange(24) - 19) / 2.5) ** 2)    # peak around 19:00
        morning_peak = 0.5 * np.exp(-0.5 * ((np.arange(24) - 8) / 1.8) ** 2)  # smaller peak ~08:00
        baseline = 0.25 * np.ones(24)  # ensures no hour is zero
        weights24 = baseline + evening_peak + morning_peak
        # per-hour fraction for a single day
        frac24 = weights24 / weights24.sum()

        # Tile for 7 days to get 168 hourly fractions
        hourly_frac = np.tile(frac24, 7)

        # Hourly deterministic values (Wh) before noise
        hourly_base_Wh = hourly_frac * daily_target

        # Multiply by lognormal noise (positively skewed), small sigma for modest variability
        noise = np.random.lognormal(mean=0.0, sigma=0.12, size=168)
        hourly_with_noise = hourly_base_Wh * noise

        # Enforce a small minimum baseline so no hour is 0 (e.g., 20 Wh)
        min_baseline_Wh = 20.0
        hourly_final = np.maximum(hourly_with_noise, min_baseline_Wh)

        # Round to integers (Wh)
        hourly_final = np.round(hourly_final).astype(float)

        self.df = pd.DataFrame({
            "time": hours,
            "energy_consumption_Wh": hourly_final,
            "solar_production_Wh": 0.0,
            "ev_charge_Wh": np.nan            
        })

    def assign_ev(self, ev):
        self.ev = ev
        if ev.smart:
            self.ev_type = "Smart"
        else:
            self.ev_type = "Non-Smart"
        self.df["ev_charge_Wh"] = ev.current_charge
