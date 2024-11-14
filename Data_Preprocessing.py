# -*- coding: utf-8 -*-
"""
Created on Sat Nov  9 17:08:51 2024

@author: GoMc
"""

import pandas as pd

# Load the wind data, adjusting parameters as necessary
PV_data = pd.read_csv('PV_Data_uncorrected.csv', skiprows=3)
Wind_data = pd.read_csv('Wind_Data_corrected.csv', skiprows=3)
Energy_consumption = pd.read_csv('Energy_consumption_2019.csv')

# Check if 'Unnamed: 0' exists and drop it
if 'Unnamed: 0' in Energy_consumption.columns:
    Energy_consumption.drop(columns=['Unnamed: 0'], inplace=True)

# Ensure 'local_time' is correctly formatted
PV_data['local_time'] = pd.to_datetime(PV_data['local_time'])
Wind_data['local_time'] = pd.to_datetime(Wind_data['local_time'])
Energy_consumption['local_time'] = pd.to_datetime(Energy_consumption['local_time'])

# Drop duplicates, keeping the first occurrence
PV_data.drop_duplicates(subset='local_time', keep='first', inplace=True)
Wind_data.drop_duplicates(subset='local_time', keep='first', inplace=True)
Energy_consumption.drop_duplicates(subset='local_time', keep='first', inplace=True)

# Select only the relevant columns from PV and Wind data
PV_data = PV_data[['local_time', 'electricity']]
Wind_data = Wind_data[['local_time', 'electricity']]

# Set 'local_time' as the index
PV_data.set_index('local_time', inplace=True)
Wind_data.set_index('local_time', inplace=True)
Energy_consumption.set_index('local_time', inplace=True)

# Rename columns to avoid conflicts when merging
PV_data.rename(columns={'electricity': 'PV_Output (kWh)'}, inplace=True)
Wind_data.rename(columns={'electricity': 'Wind_Output (kWh)'}, inplace=True)

# Concatenate the DataFrames
combined_df = pd.concat([PV_data, Wind_data, Energy_consumption], axis=1)

# Fill NaN values with 0 in combined_df
combined_df.fillna(0, inplace=True)

# Save the preprocessed data to a CSV file for later use
combined_df.to_csv('preprocessed_combined_data.csv', index=True)

print("Data preprocessing complete. Saved to 'preprocessed_combined_data.csv'")
