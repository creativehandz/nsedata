from SmartApi import SmartConnect
import pyotp
import pandas as pd
import requests
from datetime import date
import time

obj = SmartConnect(api_key = api_key)
data = obj.generateSession(userid,pin,pyotp.TOTP(totkey).now())

refreshToken = data['data']['refreshToken']
res = obj.getProfile(refreshToken)

#logic to load symbol tokens
url_symbol_master = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
response_json = requests.get(url_symbol_master).json()
token_df = pd.DataFrame(response_json)
token_df['expiry'] = pd.to_datetime(token_df['expiry'], format = 'mixed').apply(lambda x: x.date())
token_df = token_df.astype({'strike' : float})
token_df['strike'] = token_df['strike'] / 100

# Fetch spot price for CE and PE determination
# Fetch only index symbols for further drill down
banknifty_name = "BANKNIFTY"
index_symbols = token_df[(token_df.instrumenttype == "AMXIDX")]
banknifty_token = index_symbols[index_symbols['name'] == banknifty_name].iloc[0,0]

bnf_ltp = obj.ltpData('NSE', banknifty_name, banknifty_token)
bnf_ltp = bnf_ltp['data']['ltp']

expiries = token_df[(token_df.name == banknifty_name) & (token_df.instrumenttype == 'OPTIDX')]['expiry'].sort_values().unique().tolist()

strike_list = token_df[(token_df.name == banknifty_name) & (token_df.instrumenttype == 'OPTIDX') & (token_df.expiry == expiries[0])]['strike'].sort_values().to_list()
strike_diff = strike_list[22] - strike_list[20]
strike_delta = []
for strike_price in strike_list:
    strike_delta.append(abs(bnf_ltp - strike_price))

min_strike_delta = min(strike_delta)
atm_strike = strike_list[strike_delta.index(min_strike_delta)]

strike_list = []
for i in range(1,13):
     strike_list.append(float(atm_strike - (i * strike_diff)))
for i in range(1,13):
     strike_list.append(float(atm_strike + (i * strike_diff)))
	 
expiry_data_sep = {}
count = 0
for expiry in expiries[:3]:
    expiry_data_sep[f"OPT_CE_{count+1}"] = token_df[(token_df.strike.isin(strike_list)) & (token_df.symbol.str.endswith("CE")) & (token_df.name == banknifty_name) & (token_df.instrumenttype == "OPTIDX") & (token_df.expiry == expiries[count])]
    expiry_data_sep[f"OPT_PE_{count+1}"] = token_df[(token_df.strike.isin(strike_list)) & (token_df.symbol.str.endswith("PE")) & (token_df.name == banknifty_name) & (token_df.instrumenttype == "OPTIDX") & (token_df.expiry == expiries[count])]
    count += 1

nfo_datas = {}
for i in range(len(expiries[:3])):
    ce_token = expiry_data_sep[f"OPT_CE_{i+1}"]['token'].to_list()
    pe_token = expiry_data_sep[f"OPT_PE_{i+1}"]['token'].to_list()

    exchangeTokens = {
        "NSE" :[],
        "NFO" : ce_token
    }
    nfo_datas[f"EXPIRY_CE_{i+1}"] = pd.DataFrame(obj.getMarketData("FULL", exchangeTokens)['data']['fetched']).drop('depth', axis=1)

    exchangeTokens = {
        "NSE" :[],
        "NFO" : pe_token
    }
    nfo_datas[f"EXPIRY_PE_{i+1}"] = pd.DataFrame(obj.getMarketData("FULL", exchangeTokens)['data']['fetched']).drop('depth', axis=1)
	
nfo_greek_datas = {}
for i in expiries[:3]:
    greek_param = {"name" : "BANKNIFTY", "expirydate" : i.strftime("%d%^b%Y")}
    greek_response = obj.optionGreek(greek_param)
    print(i.strftime("%d%^b%Y"))
    print(greek_response)
    time.sleep(0.3)
