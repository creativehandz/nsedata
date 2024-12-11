# importing necessary libraries for data processing
from nselib import derivatives
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

def collect_data(from_date, to_date):
    # This function helps to collect all the data and store it
    data_collected = derivatives.option_price_volume_data("BANKNIFTY", "OPTIDX", from_date = from_date, to_date = to_date)
    # data_collected.to_csv(f"OPT_FUT_{from_date}_{to_date}.csv")
    return data_collected

# once the date has been fetched then data has to be filtered based on date and
datenow = datetime.now()
date_3_years_back = datenow - relativedelta(years = 3)
date_3_years_back = date_3_years_back.strftime("%d-%m-%Y")
datenow = datenow.strftime("%d-%m-%Y")
fno_data = collect_data(date_3_years_back, datenow) # function call

print("Current Date:", datenow)
print("Date 3 Years Back:", date_3_years_back)

fno_data['TIMESTAMP'] = pd.to_datetime(fno_data['TIMESTAMP']).dt.strftime("%d-%m-%Y")
fno_data['EXPIRY_DT'] = pd.to_datetime(fno_data['EXPIRY_DT']).dt.strftime("%d-%m-%Y")
fno_data.to_csv(f"OPT_FUT_{date_3_years_back}_{datenow}.csv")