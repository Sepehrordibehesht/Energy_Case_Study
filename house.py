import pandas as pd
import numpy as np

class House:
    def __init__(self, house_id, has_solar=False, ev = None, ev_type=None):
        self.house_id = house_id
        self.has_solar = has_solar
        self.ev = ev
        self.ev_type = ev_type
        
        # Create hourly DataFrame for one week (168 hours)
        self.df = pd.DataFrame({
            "time": pd.date_range("2023-08-31", periods=168, freq="h"),
            "energy_consumption_Wh": 283,      # default base consumption
            "solar_production_Wh": 0,          # will fill if has_solar
            "ev_charge_Wh": np.nan            
        })

    def assign_ev(self, ev):
        self.ev = ev
        if ev.smart:
            self.ev_type = "Smart"
        else:
            self.ev_type = "Non-Smart"
        self.df["ev_charge_Wh"] = ev.current_charge
