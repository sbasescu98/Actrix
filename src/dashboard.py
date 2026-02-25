import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta


# Setup connection to server
API_URL = 'http://127.0.0.1:8000'

st.title("Market Data Dashboard")

# Sidebar for User Inputs
st.sidebar.header("Settings")

# Set parameters
selected_markets = st.sidebar.multiselect("Markets", ["US", "UK"], default=["US", "UK"])
maturity = st.sidebar.number_input("Maturity (Years)", 1/365, 50.0, 10.0)

# Section: Historical Chart
st.header(f"Historical Yields For {maturity}Y Maturity")

# Date inputs
start_dt = st.text_input("Start Date", value="2024-02-01")
end_dt = st.text_input("End Date", value=datetime.today().strftime('%Y-%m-%d'))

start_dt_obj = pd.to_datetime(start_dt)
end_dt_obj = pd.to_datetime(end_dt)

try:
    all_ts = []
    for country in selected_markets:
        params = {
            "country": country, 
            "maturity": maturity, 
            "start_date": start_dt, 
            "end_date": end_dt
        }
        response = requests.get(f"{API_URL}/timeseries", params=params)
        
        if response.status_code == 200: # If successful request
            df_temp = pd.DataFrame(response.json()["data"])
            df_temp['Country'] = country
            all_ts.append(df_temp)
    
    if all_ts:
        df_final = pd.concat(all_ts)
        df_final['date'] = pd.to_datetime(df_final['date'])
        
        fig = px.line(df_final, x='date', y='yield', color='Country')
        st.plotly_chart(fig, width='content')
    else:
        st.info("Select a market and valid dates to see history.")
        
except Exception as e:
    st.error("Output failed. Please ensure inputs are correct or try again later.")

# Section: The Yield Curve
st.subheader("Current Yield Curve Snapshot")

# Points to draw the curve
maturity_points = [0.1, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 50]
yield_list = []

for market in selected_markets:
    for maturity in maturity_points:
        try:
            response = requests.get(f"{API_URL}/latest", params={"country": market, "maturity": maturity})
            if response.status_code == 200:
                yield_list.append(response.json())
        except Exception as e:
            st.error("Error loading data. Try again.")

if yield_list:
    df = pd.DataFrame(yield_list)
    fig = px.line(df, x='maturity', y='yield', color='country', markers=True)
    st.plotly_chart(fig, width='stretch')

else:
    st.write("Output failed. Please ensure inputs are correct or try again later.")