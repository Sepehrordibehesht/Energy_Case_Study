import pandas as pd
import numpy as np

# Read CSV and let pandas use the first row as header
data_solar_panel = pd.read_csv("Solar_data_year.csv")

# print(data_solar_panel.head())

# Convert the time column to datetime
data_solar_panel["time"] = pd.to_datetime(data_solar_panel["time"])

data_solar_panel.set_index("time", inplace=True)
hourly_data_solar = data_solar_panel.resample("h").sum()
hourly_data_solar = hourly_data_solar.reset_index()




# Only execute these prints if run directly
if __name__ == "__main__":
    print("Hourly Data (Solar):")
    print(hourly_data_solar.head())
    