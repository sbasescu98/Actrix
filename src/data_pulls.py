import pandas as pd
import numpy as np
from datetime import datetime
import requests
import io
from fredapi import Fred
import os
from dotenv import load_dotenv


########################################################
### Part 1: Data Ingestion
########################################################

# Function to fetch FRED data from start_date to present, for the given mapping of desired maturities
def get_fred_data(start_date, mapping):
    
    # Set up API
    load_dotenv()  # loads variables from .env into environment

    FRED_API_KEY= os.getenv("FRED_API_KEY")
    
    fred = Fred(api_key=FRED_API_KEY)

    # Set to store datasets
    all_data = []

    # Create a calendar df with all dates (including weekends)
    full_calendar = pd.date_range(start=start_date, end=pd.Timestamp.now(), freq='D')
    full_cal_df = pd.DataFrame({'date': full_calendar})

    for maturity, code in mapping.items():
        series = fred.get_series(code, observation_start=start_date) #Get series data beginning on the start date
        df = series.to_frame()
        df_clean = df.reset_index(names=['date']) # reset the index which contains the date 
        df_clean.rename(columns={df_clean.columns[1]: "yield"}, inplace=True) # name the yield col

        # Merge data into full calendar dataset to ensure continuous dates
        df_clean = pd.merge(full_cal_df, df_clean, on='date', how='left')

        df_clean['maturity'] = maturity 
        df_clean['maturity_code'] = code
        df_clean['country'] = 'US'
        df_clean['instrument'] = 'Treasury'
        df_clean['forward_filled_yield'] = df_clean['yield'].isna() # Add a boolean col to track if yield was missing in original data pull
        df_clean['yield'] = df_clean['yield'].ffill() # Handle NA's by forward filling (weekends, holidays, other missing data)
        all_data.append(df_clean)
    
    combined_df = pd.concat(all_data)

    # Drop any rows that are NaN in the yield column (will only be leading dates, if they are missing)
    combined_df = combined_df.dropna(subset=['yield'])
    return combined_df

def get_boe_data(start_date, boe_codes, boe_mapping):

    ### Convert start date in format 2024-01-01 to format 01/Jan/2024 - needed for url request
    # 1. Parse string into a date object
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')

    # 2. Format into dd/Mon/yyyy
    # %d is day, %b is abbreviated month (Jan), %Y is 4-digit year
    start_date_formatted = start_date_obj.strftime('%d/%b/%Y')

    # Get today's date in same format
    today_date_formatted = pd.Timestamp.now().strftime('%d/%b/%Y')

    base_url = 'https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp'

    parameters = {
        'csv.x': 'yes', # sends a file
        'Datefrom': start_date_formatted,
        'Dateto': today_date_formatted,
        'SeriesCodes': boe_codes,
        'CSVF': 'TN', # Tabular (dates in rows), no titles
        'UsingCodes': 'Y', 
        'VPD': 'Y', # Includes provisional (latest) data
        'VFD': 'N' # Excludes observation footnotes
    }

    # Gets the url 
    boe_response = requests.get(base_url, params=parameters, headers = {'User-Agent': 'Mozilla/5.0'}) # Need the headers to get around BoE access denied message 

    # Convert response from text to a virtual file using io and read into a dataframe
    boe_data = pd.read_csv(io.StringIO(boe_response.text))

    # Rename DATE to date to match US Treasury df
    boe_data.rename(columns={'DATE': 'date'}, inplace=True)

    # Create a calendar df with all dates (including weekends)
    full_calendar = pd.date_range(start=start_date, end=pd.Timestamp.now(), freq='D')
    full_cal_df = pd.DataFrame({'date': full_calendar})

    # Merge data into full calendar dataset to ensure continuous dates
    boe_data['date'] = pd.to_datetime(boe_data['date'])
    boe_data = pd.merge(full_cal_df, boe_data, on='date', how='left')

    # Convert data from wide to long format
    boe_data_long = boe_data.melt(
        id_vars=['date'], # keep this col
        var_name='maturity_code',  # name for new column
        value_name='yield' # Name for the values column
    )
    # Map the maturity codes to their maturities
    boe_data_long['maturity'] = boe_data_long['maturity_code'].map(boe_mapping)

    #### Do the forward filling for missing dates:
    ## Sort by maturity and date so the fill flows forward in time for each bond
    boe_data_long = boe_data_long.sort_values(['maturity', 'date'])

    ## Add flag for whether original data was missing / weekend
    boe_data_long['forward_filled_yield'] = boe_data_long['yield'].isna() # Add a boolean col to track if yield was missing in original data pull

    ## Group by maturity and fill within that maturity's data
    boe_data_long['yield'] = boe_data_long.groupby('maturity')['yield'].ffill()

    # Create other necessary cols
    boe_data_long['country'] = 'UK'
    boe_data_long['instrument'] = 'Gilt'

    # Drop any rows that are NaN in the yield column (will only be leading dates, if they are missing)
    boe_data_long = boe_data_long.dropna(subset=['yield'])

    return boe_data_long


# Script to pull and combine datasets
def main():
    # Define start date for data pull (YYYY-MM-DD)
    start_date = '2024-02-01'

    ########### Fred Codes
    FRED_API_KEY = "321f65e8b2e164822e29c084dc55e23e"
    fred = Fred(api_key=FRED_API_KEY)

    # Map Fred maturity length to code (years)
    fred_mapping = {
    0.083: 'DGS1MO', # 1 Month (1/12 of a year)
    0.25:  'DGS3MO', # 3 Month
    0.5:   'DGS6MO', # 6 Month
    1.0:   'DGS1', # 1 Year
    2.0:   'DGS2', # 2 Years
    5.0:   'DGS5', # 5 Years
    10.0:  'DGS10', # 10 Years
    30.0:  'DGS30' # 30 Years
    }

    # Get FRED data
    fred_data = get_fred_data(start_date, fred_mapping)

    ########### BOE Codes
    boe_codes = "IUDSNPY,IUDMNPY,IUDLNPY"

    boe_mapping = {
        'IUDSNPY': 5, # 5 Yr
        'IUDMNPY': 10, # 10 Yr
        'IUDLNPY': 20 # 20 Yr
    }

    # Get BOE data
    boe_data = get_boe_data(start_date, boe_codes, boe_mapping)

    # Combine the dataframes for fred and boe
    combined_df = pd.concat([fred_data, boe_data])

    # Store data as csv in data folder
    combined_df.to_csv('yield_data.csv', index=False)

if __name__ == "__main__":
    main()

