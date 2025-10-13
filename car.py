from house import House
import numpy as np

class Car:
    def __init__(self, car_id, house=None, capacity=60_000, current_charge=0, power=5000, smart=False):
        self.car_id = car_id
        self.capacity = capacity  # in Wh
        self.current_charge = current_charge  # in Wh
        self.power = power  # charging power in W (same as Wh/h)
        self.house = house
        self.smart = smart
        self.connected = True   # True when plugged at home

    def unplug(self, hour):
        """Mark the car as away/unplugged and set house df to -1000 for this hour (caller may set range)."""
        self.connected = False
        if self.house is not None:
            try:
                self.house.df.loc[hour, "ev_charge_Wh"] = np.nan
            except Exception:
                pass

    def plug(self, hour):
        """Mark the car as connected and set the house df ev_charge to current_charge at the plug hour."""
        self.connected = True
        if self.house is not None:
            try:
                self.house.df.loc[hour, "ev_charge_Wh"] = self.current_charge
            except Exception:
                pass

    def charge(self, hour):
        """Charge the car for one hour (hour = integer 0-167). Returns energy charged in Wh."""
        # if not connected, cannot charge
        if not getattr(self, "connected", True):
            return 0

        if self.current_charge >= self.capacity:
            return 0  # already full, no charging

        charge_energy = 0  # initialize
        hour_of_the_day = self.house.df.loc[hour, "time"].hour
        if self.smart:
            #Check if the house has solar:
            if self.house.has_solar:
                solar_available = self.house.df.loc[hour, "solar_production_Wh"]
                # Use solar first, up to power limit
                charge_energy = min(solar_available, self.power)
                # If solar not enough, take rest from grid
                if charge_energy < self.power:
                    extra_needed = self.power - charge_energy
                    charge_energy += extra_needed
                    self.house.df.loc[hour, "energy_consumption_Wh"] += extra_needed
            
            # if the house is not solar
            elif (18<=hour_of_the_day<=21) or (6<=hour_of_the_day<=9):
                charge_energy += 0.3*self.power
                charge_energy = min(charge_energy, self.capacity - self.current_charge)
                self.house.df.loc[hour, "energy_consumption_Wh"] += charge_energy
            else:
                charge_energy += self.power
                charge_energy = min(charge_energy, self.capacity - self.current_charge)
                self.house.df.loc[hour, "energy_consumption_Wh"] += charge_energy
                
            
        else:
            # Non-smart: always charge at full power
            charge_energy = self.power
            charge_energy = min(charge_energy, self.capacity - self.current_charge)
            self.house.df.loc[hour, "energy_consumption_Wh"] += charge_energy

        return charge_energy
