import tkinter as tk
from tkinter import ttk
import pandas as pd
from SmartApi import SmartConnect
import pyotp
import requests
from datetime import date
import time

api_key = "GKo3lNCy"
totkey = "Q35KXP6XHLRYLJXFCOFTUQASA4"
userid = 'K448585'
pin = '5555'

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
token_df

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
nfo_greek_datas = {}
nfo_ce_pe = {}
nfo_ce_pe_filtered = {}

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

    old_column_names = nfo_datas[f"EXPIRY_CE_{i+1}"].columns
    nfo_datas[f"EXPIRY_CE_{i+1}"].columns = ["CE_EXCHG", "CE_TSYM", "CE_SYMTOKEN", "CE_LTP", "CE_O", "CE_H", "CE_L", "CE_C", "CE_LTRDQTY", "CE_FTIME", "CE_TTIME", "CE_NCHNG", "CE_PCHNG", "CE_AVGPRICE", "CE_TVOL", "CE_OI", "CE_LC", "CE_UC", "CE_TOTBUYQTY", "CE_TSELLQTY", "CE_52WH", "CE_52WL"]
    nfo_datas[f"EXPIRY_PE_{i+1}"].columns = ["PE_EXCHG", "PE_TSYM", "PE_SYMTOKEN", "PE_LTP", "PE_O", "PE_H", "PE_L", "PE_C", "PE_LTRDQTY", "PE_FTIME", "PE_TTIME", "PE_NCHNG", "PE_PCHNG", "PE_AVGPRICE", "PE_TVOL", "PE_OI", "PE_LC", "PE_UC", "PE_TOTBUYQTY", "PE_TSELLQTY", "PE_52WH", "PE_52WL"]
    nfo_datas[f"EXPIRY_CE_{i+1}"]["STRIKE"] = nfo_datas[f"EXPIRY_CE_{i+1}"]["CE_TSYM"].apply(lambda x: int(x[16:-2]))
    nfo_datas[f"EXPIRY_PE_{i+1}"]["STRIKE"] = nfo_datas[f"EXPIRY_PE_{i+1}"]["PE_TSYM"].apply(lambda x: int(x[16:-2]))
    nfo_datas[f"EXPIRY_CE_{i+1}"]["OTYPE"] = nfo_datas[f"EXPIRY_CE_{i+1}"]["CE_TSYM"].apply(lambda x: x[-2:])
    nfo_datas[f"EXPIRY_PE_{i+1}"]["OTYPE"] = nfo_datas[f"EXPIRY_PE_{i+1}"]["PE_TSYM"].apply(lambda x: x[-2:])

    # nfo_ce_pe[f"EXPIRY{i+1}"] = nfo_datas[f"EXPIRY_CE_{i+1}"].merge(nfo_datas[f"EXPIRY_PE_{i+1}"], on = "STRIKE", how = "inner", suffixes=("_CE", "_PE"))
    # nfo_ce_pe_filtered[f"EXPIRY{i+1}"] = nfo_ce_pe[f"EXPIRY{i+1}"][['CE_TVOL', 'CE_NCHNG', 'CE_PCHNG', 'CE_LTP', 'STRIKE', 'PE_LTP', 'PE_PCHNG', 'PE_NCHNG', 'PE_TVOL']]
    greek_param = {"name" : "BANKNIFTY", "expirydate" : expiries[i+1].strftime("%d%b%Y").upper()}
    greek_response = obj.optionGreek(greek_param)
    print(greek_response)
    nfo_greek_datas[f"EXPIRY_{i+1}"] = pd.DataFrame(greek_response['data'])
    time.sleep(0.15)

    nfo_greek_datas[f'EXPIRY_{i+1}'].columns = ['NAME', 'EXPIRY', 'STRIKE', 'OTYPE', 'DELTA', 'GAMMA', 'THETA', 'VEGA', 'IV', 'TRADVOL']
    nfo_greek_datas[f'EXPIRY_{i+1}']['STRIKE'] = nfo_greek_datas[f'EXPIRY_{i+1}']['STRIKE'].astype(float)
    nfo_greek_datas[f'EXPIRY_{i+1}']['STRIKE'] = nfo_greek_datas[f'EXPIRY_{i+1}']['STRIKE'].astype(int)

    greeks_ce = nfo_greek_datas[f'EXPIRY_{i+1}'][nfo_greek_datas[f'EXPIRY_{i+1}']['OTYPE'] == 'CE']
    greeks_pe = nfo_greek_datas[f'EXPIRY_{i+1}'][nfo_greek_datas[f'EXPIRY_{i+1}']['OTYPE'] == 'PE']
    nfo_greek_datas[f"EXPIRY_CE_{i+1}"] = nfo_datas[f"EXPIRY_CE_{i+1}"].merge(greeks_ce, on = "STRIKE", how = "inner", suffixes=("_CE", "_PE"))
    nfo_greek_datas[f"EXPIRY_PE_{i+1}"] = nfo_datas[f"EXPIRY_PE_{i+1}"].merge(greeks_pe, on = "STRIKE", how = "inner", suffixes=("_CE", "_PE"))

    nfo_ce_pe[f"EXPIRY_{i+1}"] = nfo_greek_datas[f"EXPIRY_CE_{i+1}"].merge(nfo_greek_datas[f"EXPIRY_PE_{i+1}"], on = "STRIKE", how = "inner", suffixes=("_CE", "_PE"))
    nfo_ce_pe[f"EXPIRY_{i+1}"]["PCR"] = round(nfo_ce_pe[f"EXPIRY_{i+1}"]["PE_OI"] / nfo_ce_pe[f"EXPIRY_{i+1}"]["CE_OI"], 2)
    nfo_ce_pe_filtered[f"{expiries[i]}"] = nfo_ce_pe[f"EXPIRY_{i+1}"][['CE_TVOL', 'IV_CE', 'VEGA_CE', 'GAMMA_CE', 'THETA_CE', 'DELTA_CE', 'CE_NCHNG', 'CE_PCHNG', 'CE_OI', 'CE_LTP', 'STRIKE', 'PCR', 'PE_LTP', 'PE_OI', 'PE_PCHNG', 'PE_NCHNG', 'DELTA_PE', 'THETA_PE', 'GAMMA_PE', 'VEGA_PE', 'IV_PE', 'PE_TVOL']]
    columns_to_round = ['IV_CE', 'VEGA_CE', 'THETA_CE', 'DELTA_CE', 'IV_PE', 'VEGA_PE', 'THETA_PE', 'DELTA_PE']
    # Explicitly round and assign the columns
    nfo_ce_pe_filtered[f"{expiries[i]}"].loc[:, columns_to_round] = nfo_ce_pe_filtered[f"{expiries[i]}"][columns_to_round].map(lambda x: round(float(x), 2))
    #nfo_ce_pe_filtered[f"{expiries[i]}"].loc[:, ['GAMMA_CE', 'GAMMA_PE']] = nfo_ce_pe_filtered[f"{expiries[i]}"][['GAMMA_CE', 'GAMMA_PE']].map(lambda x: round(float(x), 6))

class ExpiryTableApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Option Chain Viewer")

        # Use a modern and responsive layout
        self.root.geometry("1000x700")
        self.root.minsize(900, 600)

        # Styling
        style = ttk.Style()
        style.configure("TLabel", font=("Helvetica", 12), background="#2E3440", foreground="#D8DEE9")
        style.configure("TCombobox", font=("Helvetica", 12))
        style.configure("Treeview", font=("Helvetica", 10), rowheight=25, fieldbackground="#3B4252", background="#3B4252", foreground="#D8DEE9")
        style.configure("Treeview.Heading", font=("Helvetica", 12, "bold"), background="#4C566A", foreground="#ECEFF4")
        style.map("Treeview.Heading", background=[("active", "#5E81AC")])

        # Header frame
        header_frame = tk.Frame(root, bg="#424752")
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        # Call and Put labels
        call_label = tk.Label(
            header_frame, text="CALL", bg="#A3BE8C", fg="white",
            font=("Helvetica", 16, "bold"), padx=10, pady=5, relief="ridge"
        )
        call_label.pack(side=tk.LEFT, padx=10)

        put_label = tk.Label(
            header_frame, text="PUT", bg="#BF616A", fg="white",
            font=("Helvetica", 16, "bold"), padx=10, pady=5, relief="ridge"
        )
        put_label.pack(side=tk.RIGHT, padx=10)

        # Dropdown for expiry selection
        self.selected_expiry = tk.StringVar()
        self.selected_expiry.set(expiries[0])

        dropdown = ttk.Combobox(
            header_frame, textvariable=self.selected_expiry,
            values=expiries[:3], state="readonly"
        )
        dropdown.pack(side=tk.TOP, pady=5)
        dropdown.bind("<<ComboboxSelected>>", self.update_table)
        
        # Bindings and reset for dropdown
        dropdown.bind("<<ComboboxSelected>>", lambda _: self.reset_sort_and_update_table())

        # Frame for table
        self.table_frame = tk.Frame(root, bg="#2E3440")
        self.table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Sort order for each column
        self.sort_order = {}

        # Initialize table
        self.tree = None
        self.setup_table()
        self.update_table()

    def setup_table(self):
        # Create Treeview
        columns = list(nfo_ce_pe_filtered[f"{expiries[0]}"].columns)
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings")

        # Add column headers with sorting
        for col in columns:
            self.tree.heading(col, text=col, anchor=tk.CENTER, command=lambda c=col: self.sort_column(c))
            self.tree.column(col, anchor=tk.CENTER, width=120)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add scrollbar
        scrollbarH = ttk.Scrollbar(self.table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(xscroll=scrollbarH.set)
        scrollbarH.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def sort_column(self, col):
        # Get the current selected expiry
        selected_expiry = self.selected_expiry.get()
        
        # Get the data for the current expiry
        selected_data = nfo_ce_pe_filtered[selected_expiry]

        # Determine the sort order for the column
        if col not in self.sort_order or self.sort_order[col] == "desc":
            self.sort_order[col] = "asc"
            sorted_data = selected_data.sort_values(by=col, ascending=True)
        else:
            self.sort_order[col] = "desc"
            sorted_data = selected_data.sort_values(by=col, ascending=False)

        # Update the table with the sorted data
        self.update_table(sorted_data)

    def update_table(self, data=None):
        # Clear existing rows in the table
        for row in self.tree.get_children():
            self.tree.delete(row)

        # Fetch data based on the selected expiry if not provided
        if data is None:
            selected_expiry = self.selected_expiry.get()
            data = nfo_ce_pe_filtered[selected_expiry]

        # Insert rows into the table
        for _, row in data.iterrows():
            self.tree.insert("", tk.END, values=row.tolist())

    def reset_sort_and_update_table(self):
        # Reset the sorting state
        self.sort_order.clear()
        
        # Update table with unsorted data for the newly selected expiry
        self.update_table()

if __name__ == "__main__":
    root = tk.Tk()
    app = ExpiryTableApp(root)
    root.configure(bg="#545F74")
    root.mainloop()