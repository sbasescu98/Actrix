import pandas as pd
import numpy as np
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Query
from scipy.interpolate import make_interp_spline

########################################################
### Part 2 - Interpolation Curve
########################################################


# Returns the yield curve given the yield dataset, target_date, and country
# Calculates the interoplations using linear method (k=2) is quadratic by default, change to k=1 for linear or k=3 for cubic
# Returns a spline object which can be used to calculate yield for a given maturity
def get_yield_curve(yield_data, target_date, country, k=2):

    # Filter to target date and country
    curve_data = yield_data[(yield_data['date'] == pd.to_datetime(target_date)) & (yield_data['country'] == country)].copy()

    maturities = curve_data['maturity']
    yields = curve_data['yield']
 
    curve = make_interp_spline(maturities, yields, k=k)

    return curve


########################################################
### Part 3: Rest API Endpoints
########################################################
yield_data = pd.read_csv('yield_data.csv') # Read in data from store
yield_data['date'] = pd.to_datetime(yield_data['date']) # Ensure it is datetime

# Set up API
app = FastAPI(title="Actrix API")

# 1. Latest Yield: GET /latest
@app.get("/latest")
def get_latest(country: str = Query(..., pattern="^(US|UK)$"), maturity: float = Query(..., ge=1/365, le=50)): # Restrict to US or UK for country, and maturity between 1D and 50Y

    # Get new dataframe filtered down to country 
    country_df = yield_data[(yield_data['country'] == country)].copy()

    # Get rows that are not forward filled (original data)
    original_rows = country_df[~country_df["forward_filled_yield"]]

    # Get date of latest original data
    latest_date = original_rows["date"].max()

    # Get yield curve
    curve = get_yield_curve(country_df, latest_date, country)

    # Calculate upper and lower maturity bounds to clip maturity calculations to if outside range
    # Get max maturity 
    max_maturity = country_df['maturity'].max()

    # Get min maturity 
    min_maturity = country_df['maturity'].min()

    # Get yield for given maturity
    interpolated_yield = float(curve(maturity))

    # If outside data range, clip maturity values to be to the nearest maturity (flat extrapolation)
    if(maturity > max_maturity):
        interpolated_yield = float(curve(max_maturity))
    elif(maturity < min_maturity):
        interpolated_yield = float(curve(min_maturity))
    
    return {
        "date": latest_date.strftime("%Y-%m-%d"),
        "country": country,
        "maturity": maturity,
        "yield": round(interpolated_yield, 4)
    }

# 2. Timeseries Yield: GET /timeseries
@app.get("/timeseries")
def get_timeseries(country: str = Query(..., pattern="^(US|UK)$"), maturity: float = Query(..., ge=1/365, le=50), start_date = Query(..., description = "YYYY-MM-DD format"), end_date = Query(..., description = "YYYY-MM-DD format")): 

    # Validate date logic
    try:
        start_date_obj = pd.to_datetime(start_date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start_date format. Please use YYYY-MM-DD format.")

    try:
        end_date_obj = pd.to_datetime(end_date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid end_date format. Please use YYYY-MM-DD format.")

    start_date_obj = pd.to_datetime(start_date)
    end_date_obj = pd.to_datetime(end_date)

    # Check end)date comes after or on same day as start_date
    if start_date_obj > end_date_obj:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid range: Start date ({start_date}) must be before end date ({end_date})."
    )

    # Get new dataframe filtered down to country and date range
    filtered_df = yield_data[(yield_data['country'] == country) & (yield_data['date'] >= pd.to_datetime(start_date)) & (yield_data['date'] <= pd.to_datetime(end_date))].copy() 

    # Throw Exception if dataset is empty
    if filtered_df.empty:
        raise HTTPException(status_code=404, detail="No data found for this country and date range.")

    # Empty array to store calculated yield values
    data = []

    # Calculate upper and lower maturity bounds to clip maturity calculations to if outside range
    # Get max maturity 
    max_maturity = filtered_df['maturity'].max()

    # Get min maturity 
    min_maturity = filtered_df['maturity'].min()

    # Loop through date range
    for date in filtered_df['date'].unique():
        # Get yield curve
        curve = get_yield_curve(filtered_df, date, country)
        # Get yield for given maturity
        interpolated_yield = float(curve(maturity))
        # If outside data range, manually set value to the yield for the nearest maturity (flat extrapolation)
        if(maturity > max_maturity):
            interpolated_yield = float(curve(max_maturity))
        elif(maturity < min_maturity):
            interpolated_yield = float(curve(min_maturity))

        # Append to list with date
        data.append({"date": pd.Timestamp(date).strftime("%Y-%m-%d"), "yield": round(interpolated_yield, 4)})

    return {
        "country": country,
        "maturity": maturity,
        "data": data
    }