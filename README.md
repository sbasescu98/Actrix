Environment setup:

1. Clone or open repository and navigate to the root folder (Actrix)

2. Only do first time running environment: Create virtual environment, in terminal, run: python -m venv venv 
Note: Depending on system, you may need to use python3 instead of python. 

3. Activate virtual environment
macOS in terminal run: source venv/bin/activate
windows in terminal run: venv\Scripts\Activate

4. Install dependencies (only necessary the first virtual environment is set up or requirements are updated)
In terminal, run: pip install -r requirements.txt

Run the Pipeline:
Pre-step: Sign up for an account with Fred and request and api key. Then, create a .env file and put this in one line: FRED_API_KEY="YOUR_API_KEY_HERE"

1. Run the data pull
Navigate to src directory
In terminal, run: python data_pulls.py
Note: This creates yield_data.csv in the data folder with the most up-to-date data

2. Launch API server
In terminal, run: uvicorn main:app --reload 

3. Test API
Navigate to http://127.0.0.1:8000/docs in your url, and test the endpoints 
Sample URL for get latest: http://127.0.0.1:8000/latest?country=US&maturity=1
Sample URL for get timeseries: http://127.0.0.1:8000/timeseries?country=US&maturity=10&start_date=2024-02-01&end_date=2024-02-24

View the Dashboard:
1. Ensure that the API is active (from the steps above)

2. In another terminal (make sure venv is activated) navigate to src file and run the command: streamlit run dashboard.py
Note: This opens a window in local browser to view the dashboard

Data Sources Used: 
FRED: constant maturity Treasury yields (1M, 3M, 6M, 1Y, 2Y, 5Y, 10Y, 30Y)
Bank of England (BoE): nominal par yields (5Y, 10Y, 20Y)

Important Design and Implementation Choices: 
1. Dataset Construction
In US Treasury data, no data on weekends are provided, and yields on bank holidays are provided as NaN (null). In BoE data, no data on weekends or bank holidays are provided. 

To account for this, I create a continuous date range between the specified start date and the present date. I then join the US Treasury data and BoE data onto these dates and forward fill the missing values. This means that the yield provided on each date is the last available data available (e.g. the yield on a non-trading day will have the same value as the most recently available trading-day yield, when markets were open). I also track which values are forward-filled in the boolean variable forward_filled_yield, which allows us to distinguish between true observations and data carried forward from before. 

In the BoE data pull, I had to include headers = {'User-Agent': 'Mozilla/5.0'} so that the browser didn't block the python code. There is probably a better way to do this, especially if this code were to be used in a production environment. 

2. Interpolation and Extrapolation
I use quadratic interpolation as the default interpolation method. I do this because only 3 data points were available from the BoE on nominal par yields (5Y, 10Y, 20Y), making it difficult or less accurate to fit a more advanced function to the data. Furthermore, if there is a request to calculate the yield on a maturity beyond the range of the data (< 5Y or >20Y for BoE data, or <1Mo or >30Y for FRED data), I apply a flat extrapolation, meaning the calculated yield is the same as the yield at the nearest data point. For example, if a yield for BoE data is requested with a maturity of 45Y, the function returns the same yield as the 20Y bond yield (this is to avoid spurious calculations using limited data points). Furthermore, I use the same methods for FRED data, despite having more data points which could make cubic or Nelson-Siegel methods more appropriate. This ensures that the methods are consistent across the two types of data. Note that the extrapolation is performed in the API calls, which calls the get_yield_curve function. The get_yield_curve function returns a BSpline object, which if called directly, returns the calculated yield according to the interpolation function and without performing flat extrapolation. 

3. API input validation
I use FastAPI's Query parameters to block edge cases that may produce errors (e.g. requires country input to be "US" or "UK", blocks requests with incorrect date ranges or maturities outside the 1D to 50Y range). 

What I would improve with more time: 
1. I would get more datapoints for the BoE data, so that a more complex interpolation method could be fit. 

2. I would implement the Nelson-Siegel interpolation method, and use it as a parameter in the curve calculation method so the user can specify which method they want to use. In general, it seems like this is the industry standard for interpolation and would handle the tails more effectively (e.g. reaches an asymptote instead of continuing upwards as with linear interpolation). 

3. I would reduce redundancy in some of the code to ensure the most-efficient run-times. For example, I could better standardize the way that dates are handled and ingested, to reduce the number of times the code converts strings to datetime objects or datetime objects to strings. While this does not add much latency now, it would be simpler to have one standard way of handling dates (though of course this dependends on the data sources, as FRED and BoE reference dates differently). I would also optimize memory management and how data is passed between functions to ensure fast return times without comprimising the data. For example, I currently use 
.copy() in the interpolation and API request functions to ensure the original data is not overwritten or altered. This introduces safety to the process but also adds to the memory usage. With more time, I would ensure these functions are being used optimally for run-time (which will be particularly important with API requests that are very large) while ensuring data integrity.

4. Streamlit Dashboard: The current dashboard is simple a prototype to show basic visualizations using the data. With more time, I would add better error catching and safeguarding of inputs, for example to ensure dates are being inputted in the correct format and giving the user more information with consistent error handling for edge cases. Furthermore, I would add more visualizations and customizations like a chart that compares spreads between markets. 

5. API calls: I would also implement a more efficient function to return the entire yield curve in one API call. Right now to create the yield curve visual in the dashboard.py file, I loop through a set number of maturities to calculate, and call the get latest API endpoint each time which manually constructs the yield curve. Instead, it would be better to create a new function and API endpoint that returns the whole yield curve once. This would reduce the number API calls and would be much more efficient to create the yield curve plot. 
