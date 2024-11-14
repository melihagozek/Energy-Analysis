# -*- coding: utf-8 -*-
"""
Created on Sat Nov  9 15:37:49 2024

@author: GoMc
"""

import webbrowser
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# Load the preprocessed data from the previous script
combined_df = pd.read_csv('preprocessed_combined_data.csv', index_col='local_time', parse_dates=['local_time'])

# Fill NaN values with 0 in combined_df
combined_df.fillna(0, inplace=True)

# Constants
spenergy_cons = 4.8  # kW/Nm3 (energy consumption per Nm³ of hydrogen)
ely_energy = 300     # Elektrolyser connection energy for hydrogen production (kW)
vol_mass = 11.126    # Conversion factor kg/Nm³
mass_vol = 0.08987956 # Conversion factor Nm³/kg
hydrogen_capacity = 5000  # Storage tank capacity in kg
initial_hydrogen_storage = 200  # Initial storage amount in kg
battery_storage = 0  # Initial battery storage
power_plant_efficiency = 45 # Efficiency of power plant
hydrogen_heating_value = 39.4 # The amount of energy released by hydrogen combusiton in kWh/kg

# Add new columns in the combined DataFrame and set the initial values
combined_df['Storage Tank (kg)'] = initial_hydrogen_storage
combined_df['Hydrogen Produced (kg)'] = 0  # Initialize hydrogen produced column
combined_df['Hydrogen Extracted (kg)'] = 0  # Initialize hydrogen extracted column
combined_df['Battery Storage (kWh)'] = 0  # Initialize battery storage
combined_df['External Power Used (kWh)'] = 0  # Initialize external power used
combined_df['Hydrogen Storage Level Ratio'] = 0  # Initialize hydrogen storage level ratio

# Iterate through each time step to determine hydrogen production, battery storage, or external power usage 
for index, row in combined_df.iterrows():
    surplus = row['PV_Output (kWh)'] + row['Wind_Output (kWh)'] - row['Energy_consumption (kWh)']
    combined_df.at[index, 'Surplus (kWh)'] = surplus
    
    # Conditions for hydrogen production and battery storage
    if surplus > 0:
        if surplus >= ely_energy:
            # Produce hydrogen and store the remaining surplus in the battery
            hydrogen_volume = ely_energy / spenergy_cons  # in Nm³
            hydrogen_produced = hydrogen_volume * mass_vol  # Convert Nm³ to kg
            battery_storage = surplus - ely_energy  # Store the rest in the battery
        else:
            # No hydrogen production, all surplus goes into the battery
            hydrogen_produced = 0
            battery_storage = surplus
    else:
        # No hydrogen production when surplus is negative
        hydrogen_produced = 0
        battery_storage = 0

    combined_df.at[index, 'Hydrogen Produced (kg)'] = hydrogen_produced
    combined_df.at[index, 'Battery Storage (kWh)'] = battery_storage

    # Update hydrogen storage tank only with produced hydrogen
    if hydrogen_produced > 0:
        if initial_hydrogen_storage + hydrogen_produced <= hydrogen_capacity:
            initial_hydrogen_storage += hydrogen_produced
        else:
            # If storage tank capacity is exceeded, only store up to the max capacity
            initial_hydrogen_storage = hydrogen_capacity
        
    combined_df.at[index, 'Storage Tank (kg)'] = initial_hydrogen_storage
    
    # Conditions for hydrogen extraction if surplus < 0
    if surplus < 0:
        # Calculate hydrogen needed to cover negative surplus
        total_power = abs(surplus)*100 / power_plant_efficiency
        hydrogen_needed = total_power/hydrogen_heating_value   # Convert surplus energy to hydrogen needed
        combined_df.at[index, 'Total Power CPH (kWh)'] = total_power

        # Check if there's enough hydrogen in the storage tank (at least 200 kg) to extract
        if initial_hydrogen_storage >= 100 + hydrogen_needed:
            # Extract hydrogen from storage
            initial_hydrogen_storage -= hydrogen_needed
            combined_df.at[index, 'Hydrogen Extracted (kg)'] = hydrogen_needed
        else:
            # If there isn't enough hydrogen in storage, use external power
            combined_df.at[index, 'External Power Used (kWh)'] = abs(surplus)
            combined_df.at[index, 'Hydrogen Extracted (kg)'] = 0
        

    # Update the hydrogen storage level ratio (maximum hydrogen capacity in the tank: 5000 kg)
    hydrogen_storage_ratio = initial_hydrogen_storage / hydrogen_capacity
    combined_df.at[index, 'Hydrogen Storage Level Ratio'] = hydrogen_storage_ratio
    # Update the storage tank level in the DataFrame
    combined_df.at[index, 'Storage Tank (kg)'] = initial_hydrogen_storage
    
    # Fill NaN values with 0 in combined_df
    combined_df.fillna(0, inplace=True)
  
    
# If extracted hydrogen is 0, then energy production by CPH is also 0
combined_df.loc[combined_df['Hydrogen Extracted (kg)'] == 0, 'Total Power CPH (kWh)'] = 0

# Calculate total renewable energy from PV and wind
combined_df['Renewable Energy (kWh)'] = combined_df['PV_Output (kWh)'] + combined_df['Wind_Output (kWh)']

# Calculate renewable energy used for plant energy consumption
combined_df['Renewable Energy for Plant (kWh)'] = np.where(
    (combined_df['External Power Used (kWh)'] > 0) & 
    (combined_df['Battery Storage (kWh)'] == 0) & 
    (combined_df['Hydrogen Extracted (kg)'] == 0),
    
    -(combined_df['External Power Used (kWh)'] - combined_df['Energy_consumption (kWh)']),
    
    np.where(
        (combined_df['PV_Output (kWh)'] + combined_df['Wind_Output (kWh)']) < combined_df['Energy_consumption (kWh)'],
        combined_df['PV_Output (kWh)'] + combined_df['Wind_Output (kWh)'], 
        combined_df['Energy_consumption (kWh)']))

# Ensure no negative values for renewable energy used for plant energy consumption
combined_df['Renewable Energy for Plant (kWh)'] = combined_df['Renewable Energy for Plant (kWh)'].clip(lower=0)

# Implement the conditional logic for 'Energy from Hydrogen (kWh)' with the additional condition for surplus
combined_df['Energy from Hydrogen (kWh)'] = combined_df.apply(
    lambda row: -row['Surplus (kWh)'] 
    if (row['External Power Used (kWh)'] == 0 and row['Hydrogen Extracted (kg)'] > 0 and row['Surplus (kWh)'] < 0) 
    else 0, axis=1)

# Calculate total energy consumed (this is already in the Energy_consumption column)
combined_df['Total Energy Consumed (kWh)'] = combined_df['Energy_consumption (kWh)']

# Calculate the autarky degree
combined_df['Autarky Degree (%)'] = ((combined_df['Renewable Energy for Plant (kWh)'] + combined_df['Energy from Hydrogen (kWh)']) / combined_df['Total Energy Consumed (kWh)']) * 100

# Replace any NaN or infinity values with 0 for clarity
combined_df['Autarky Degree (%)'].replace([np.inf, -np.inf], 0, inplace=True)
combined_df['Autarky Degree (%)'].fillna(0, inplace=True)


# Calculate the total annual values
total_renewable_energy_for_plant = combined_df['Renewable Energy for Plant (kWh)'].sum()
total_energy_from_hydrogen = combined_df['Energy from Hydrogen (kWh)'].sum()
total_energy_consumed = combined_df['Total Energy Consumed (kWh)'].sum() + combined_df['External Power Used (kWh)'].sum()
# Calculate energy from hydrogen produced (in kWh)
combined_df['Energy for Hydrogen Produced (kWh)'] = combined_df['Hydrogen Produced (kg)'] * spenergy_cons/mass_vol


# Calculate the annual autarky degree for pie chart
annual_autarky_degree = ((total_renewable_energy_for_plant + total_energy_from_hydrogen) / total_energy_consumed) * 100

# Replace any NaN or infinity values with 0 for clarity
annual_autarky_degree = 0 if np.isnan(annual_autarky_degree) or np.isinf(annual_autarky_degree) else annual_autarky_degree


"""Data preparation for the the visualsation with matplotlib"""
# Ensure the 'local_time' column is set as the index if not already done
combined_df['local_time'] = combined_df.index

# Add a new column for the month, extracted from the 'local_time'
combined_df['Month'] = combined_df['local_time'].dt.to_period('M')

# Group the data by month and sum the PV and Wind outputs for each month
monthly_pv_wind = combined_df.groupby('Month')[['PV_Output (kWh)', 'Wind_Output (kWh)']].sum()

# Plot the monthly data in a bar chart
monthly_pv_wind.plot(kind='bar', stacked=False, figsize=(10, 6))

# Set the title and labels for the plot
plt.title('Monthly PV and Wind Power Output (kWh)', fontsize=14)
plt.xlabel('Month', fontsize=12)
plt.ylabel('Power Output (kWh)', fontsize=12)

# Rotate the x-axis labels for better readability
plt.xticks(rotation=45)

# Show the plot
plt.tight_layout()
plt.show()


""""Data Preparation for Pie Chart"""
# Calculate total renewable energy ea according to each usage area for pie chart
total_plant_consumption = combined_df['Renewable Energy for Plant (kWh)'].sum()
total_battery_storage = combined_df['Battery Storage (kWh)'].sum()
total_hydrogen_production = combined_df['Energy for Hydrogen Produced (kWh)'].sum() # Convert kg to kWh

# Define labels and sizes for the pie chart
labels = ['Plant Consumption', 'Battery Storage', 'Hydrogen Production']
sizes = [total_plant_consumption, total_battery_storage, total_hydrogen_production]

# Plot the pie chart
plt.figure(figsize=(8, 8))
plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=['#4CAF50', '#FFD700', '#FF6347'])
plt.title('Distribution of Produced Renewable Energy by Use Areas (Excluding External Power)')
plt.show()

""""Data Preparation with additional power used for Pie Chart"""
# Calculate total renewable energy for each usage area
total_plant_consumption = combined_df['Renewable Energy for Plant (kWh)'].sum()
total_battery_storage = combined_df['Battery Storage (kWh)'].sum()
total_hydrogen_production = combined_df['Energy for Hydrogen Produced (kWh)'].sum()
total_external_power_used = combined_df['External Power Used (kWh)'].sum()  # Total external power used

# Define labels and sizes for the pie chart
labels = ['Plant Consumption', 'Battery Storage', 'Hydrogen Production', 'External Power Used']
sizes = [total_plant_consumption, total_battery_storage, total_hydrogen_production, total_external_power_used]

# Plot the pie chart
plt.figure(figsize=(8, 8))
plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, colors=['#4CAF50', '#FFD700', '#FF6347', '#4682B4'])
plt.title('Distribution of Energy by Use Areas (Including External Power Used)')
plt.show()

# Plot the distribution chart
plt.figure(figsize=(12, 6))
plt.plot(combined_df.index, combined_df['Hydrogen Storage Level Ratio'] * 100, color='lightblue', label='Hydrogen Storage Level Ratio (%)')
plt.title('Hourly Hydrogen Storage Level Ratio (%)')
plt.xlabel('Date and Time')
plt.ylabel('Hydrogen Storage Level Ratio (%)')
plt.xticks(rotation=45)

# Set x-axis major locator to display months
ax = plt.gca()
ax.xaxis.set_major_locator(mdates.MonthLocator())  # Set major ticks to months
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))  # Format to show month and year

# Highlight the maximum capacity line
plt.axhline(y=100, color='r', linestyle='--', label='Max Capacity (100%)')
plt.legend()
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.show()


"""Data preparation for the the visualisation with plotly"""
# Group the data by month for plotly visualisation and calculate the sum of PV and Wind outputs for each month
monthly_pv_wind = combined_df.groupby('Month')[['PV_Output (kWh)', 'Wind_Output (kWh)']].sum().reset_index()

# Convert 'Month' from Period to string for plotting
monthly_pv_wind['Month'] = monthly_pv_wind['Month'].astype(str)

# Plotly figure code
fig = px.bar(
    monthly_pv_wind.reset_index(),
    x='Month',
    y=['PV_Output (kWh)', 'Wind_Output (kWh)'],
    title='Monthly PV and Wind Power Output (kWh)',
    labels={'value': 'Power Output (kWh)', 'variable': 'Power Source'}
)

# Save the figure to an HTML file
fig.write_html("monthly_pv_wind_output.html")
webbrowser.open("monthly_pv_wind_output.html")


# Prepare the data for shaded area plot
fig = go.Figure()

# Add the PV output as a shaded area
fig.add_trace(go.Scatter(
    x=monthly_pv_wind.index.astype(str),
    y=monthly_pv_wind['PV_Output (kWh)'],
    fill='tozeroy',
    mode='none',
    name='PV Output (kWh)'
))

# Add the Wind output as a shaded area stacked on top of PV output
fig.add_trace(go.Scatter(
    x=monthly_pv_wind.index.astype(str),
    y=monthly_pv_wind['PV_Output (kWh)'] + monthly_pv_wind['Wind_Output (kWh)'],
    fill='tonexty',
    mode='none',
    name='Wind Output (kWh)'
))

# Customize layout
fig.update_layout(
    title='Monthly PV and Wind Power Output (kWh)',
    xaxis_title='Month',
    yaxis_title='Power Output (kWh)',
    template='plotly_white'
)

# Show the plot in a web browser
fig.write_html("monthly_pv_wind_area_output.html")
webbrowser.open("monthly_pv_wind_area_output.html")