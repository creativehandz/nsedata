import threading
import tkinter as tk
from tkinter import ttk
import pandas as pd
import pyotp
import requests
from datetime import datetime
import time
from playwright.sync_api import Playwright, sync_playwright
from urllib.parse import parse_qs, urlparse, quote
import pyotp

class DataFetcher:
    def __init__(self, api_key, secret_key, totkey, pin, redirect_url, mobile_num):
        self.secret_key = secret_key
        self.redirect_url = redirect_url
        self.api_key = api_key
        self.TOTP_KEY = totkey
        self.AUTH_URL = None
        self.mobile_num = mobile_num
        self.pin = pin
        self.access_token = None
        self.obj = None
        self.token_df = None
        self.bnf_ltp = None
        self.nfo_ce_pe_filtered = {}
        self.expiries = None
        self.atm_price = None
        self.initialize_connection()

    def initialize_connection(self):
        # self.obj = SmartConnect(api_key=self.api_key)
        # data = self.obj.generateSession(self.userid, self.pin, pyotp.TOTP(self.totkey).now())
        # self.refreshToken = data['data']['refreshToken']
        # self.obj.getProfile(self.refreshToken)
        rurl_encode = quote(self.redirect_url, safe="")
        self.AUTH_URL = f"https://api-v2.upstox.com/login/authorization/dialog?response_type=code&client_id={self.api_key}&redirect_uri={rurl_encode}"
        with sync_playwright() as playwright:
            code = self.run(playwright)
        url = 'https://api-v2.upstox.com/login/authorization/token'
        headers = {
            'accept': 'application/json',
            'Api-Version' : '2.0',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'code' : code,
            'client_id' : self.api_key,
            'client_secret' : self.secret_key,
            'redirect_uri' : self.redirect_url,
            'grant_type' : 'authorization_code'
        }

        response = requests.post(url, headers = headers, data = data)
        json_response = response.json()
        self.access_token = json_response['access_token']


        opt_C_url = "https://api.upstox.com/v2/option/contract"
        headers = {
            'Accept' : 'application/json',
            'Api-Version' : '2.0',
            'Authorization' : f'Bearer {self.access_token}'
        }

        params = {
            "instrument_key" : 'NSE_INDEX|Nifty Bank',
        }
        response = requests.get(opt_C_url, headers=headers, params=params)

        self.expiries = sorted(pd.DataFrame(response.json()['data'])['expiry'].unique().tolist())
        response = None

    def run(self, playwright: Playwright) -> None:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        redirect_url = None
        
        def handle_request(request):
            nonlocal redirect_url
            # Might want to add specific URL patterns here
            if 'code=' in request.url:
                redirect_url = request.url
                # print(f"Captured URL: {request.url}")
        
        page.on("request", handle_request)
        
        # Navigate and perform actions
        page.goto(self.AUTH_URL)
        page.locator("#mobileNum").fill(self.mobile_num)
        page.get_by_role("button", name="Get OTP").click()
        
        otp = pyotp.TOTP(self.TOTP_KEY).now()
        page.locator("#otpNum").fill(otp)
        page.get_by_role("button", name="Continue").click()
        
        page.get_by_label("Enter 6-digit PIN").fill(self.pin)
        page.get_by_role("button", name="Continue").click()
        
        # Wait for navigation and any redirects to complete
        page.wait_for_load_state("networkidle")
        
        # Give some time for the final request to be processed
        page.wait_for_timeout(5000)  # 5 seconds wait
        
        if redirect_url:
            parsed = urlparse(redirect_url)
            code = parse_qs(parsed.query)['code'][0]
            context.close()
            browser.close()
            return code
        else:
            context.close()
            browser.close()
            raise Exception("Failed to capture the redirect URL with code")
    
    def fetch_market_data(self):
        try :
            for expiry in self.expiries[:2]:
                # print(f"Expiry : {expiry}")
                opt_url = "https://api.upstox.com/v2/option/chain"
                headers = {
                    'Accept' : 'application/json',
                    'Api-Version' : '2.0',
                    'Authorization' : f'Bearer {self.access_token}'
                }
                # print(f"access_token {self.access_token}\n\n")
                params = {
                    "instrument_key" : 'NSE_INDEX|Nifty Bank',
                    "expiry_date" : expiry
                }
                response = requests.get(opt_url, headers=headers, params=params)
                # print(f"response_data :  {response.json()['data']}\n\n")
                # Provided JSON data
                data = response.json()['data']

                # Flatten JSON and create DataFrame
                flattened_data = []
                for item in data:
                    base = {
                        "expiry": item["expiry"],
                        "strike_price": item["strike_price"],
                        "underlying_key": item["underlying_key"],
                        "underlying_spot_price": item["underlying_spot_price"]
                    }
                    
                    # Call options
                    call_data = {f" {k.upper()}": v for k, v in item["call_options"]["market_data"].items()}
                    call_greeks = {f" {k.upper()}": v for k, v in item["call_options"]["option_greeks"].items()}
                    
                    # Put options
                    put_data = {f"{k.upper()}": v for k, v in item["put_options"]["market_data"].items()}
                    put_greeks = {f"{k.upper()}": v for k, v in item["put_options"]["option_greeks"].items()}
                    
                    # Combine
                    row = {**base, **call_data, **call_greeks, **put_data, **put_greeks}
                    flattened_data.append(row)

                df = pd.DataFrame(flattened_data)
                # print(df.head())
                df.sort_values(by = 'strike_price', ascending=True, inplace = True)
                spot = float(df.iloc[0, 3])
                self.bnf_ltp = spot
                atm_strike = (int(spot/100) * 100) + 100 if spot%100 > 50 else (int(spot/100) * 100)
                self.atm_price = atm_strike
                # print(f"ATM_STRIKE : {atm_strike}\n\n")
                df.columns = [col.upper() for col in df.columns]
                df.rename(columns = {"STRIKE_PRICE" : "STRIKE"}, inplace=True)
                df['PCR'] = round(df['OI'] / df[' OI'], 4)
                df['PCR'] = df['PCR'].apply(lambda x: f"{x:.4f}")
                df['PCR'] = df['PCR'].astype(float)
                df = df[[' VOLUME', ' VEGA', ' THETA', ' GAMMA',' DELTA', ' IV', ' OI', ' LTP',
                            'STRIKE', 'PCR', 'LTP', 'OI', 'IV', 'DELTA', 'GAMMA', 'THETA', 'VEGA', 'VOLUME']]

                self.nfo_ce_pe_filtered[f'{expiry}'] = df.copy()
                index_atmA = self.nfo_ce_pe_filtered[f'{expiry}'][self.nfo_ce_pe_filtered[f'{expiry}']['STRIKE'] == atm_strike].index
                index_atm = int(index_atmA[0])
                self.nfo_ce_pe_filtered[f'{expiry}'] = self.nfo_ce_pe_filtered[f'{expiry}'].loc[index_atm-5:index_atm+5,:]
                # print(self.nfo_ce_pe_filtered[f'{expiry}'].head())
            return True
            
        except Exception as e:
            print(f"Error in fetch_market_data: {e}")
            return False

class ExpiryTableApp:
    def __init__(self, root, data_fetcher):
        """
        Initialize the ExpiryTableApp with root window and data fetcher.
        
        Args:
            root: tk.Tk instance - The root window
            data_fetcher: DataFetcher instance - Handles all market data operations
        """
        # Basic setup
        self.root = root
        self.data_fetcher = data_fetcher
        self.root.title("Option Chain Viewer")
        
        # Initialize variables
        self.tree = None
        self.header_frame = None
        self.table_frame = None
        self.call_label = None
        self.put_label = None
        self.market_status = None
        self.last_update = None
        self.expiry_dropdown = None
        self.selected_expiry = None
        self.sort_order = {}
        self.columns = None
        
        # Auto-update control
        self.update_thread = None
        self.running = True
        self.update_interval = 1000  # 1 second during market hours
        self.check_interval = 60000  # 1 minute outside market hours
        self.last_update_time = None
        
        # Initialize UI
        self.setup_ui()
        
        # Configure update mechanism
        self.start_auto_update()
        
        # Configure cleanup
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Initial data update
        self.update_table()

    def on_closing(self):
        """Handle application closing."""
        self.running = False
        if hasattr(self, 'blink_after_id') and self.blink_after_id is not None:
            self.root.after_cancel(self.blink_after_id)
        if self.update_thread:
            self.update_thread.join(timeout=1.0)
        self.root.destroy()

    def start_auto_update(self):
        """Start the auto-update thread."""
        def update_loop():
            while self.running:
                try:
                    current_time = datetime.now().time()
                    market_start = datetime.strptime("09:14:00", "%H:%M:%S").time()
                    market_end = datetime.strptime("15:35:00", "%H:%M:%S").time()
                    
                    if market_start <= current_time <= market_end:
                        # During market hours
                        if self.data_fetcher.fetch_market_data():
                            self.root.after(0, self.update_table)
                        time.sleep(self.update_interval / 1000)  # Convert to seconds
                    else:
                        # Outside market hours
                        time.sleep(self.check_interval / 1000)  # Convert to seconds
                        
                except Exception as e:
                    print(f"Error in update loop: {e}")
                    time.sleep(5)  # Wait before retrying on error
        
        self.update_thread = threading.Thread(target=update_loop, daemon=True)
        self.update_thread.start()

    def is_market_hours(self):
        """Check if current time is during market hours."""
        current_time = datetime.now().time()
        market_start = datetime.strptime("09:15:00", "%H:%M:%S").time()
        market_end = datetime.strptime("15:30:00", "%H:%M:%S").time()
        return market_start <= current_time <= market_end

    def setup_ui(self):
        # Configure root window
        self.root.geometry("1000x700")
        self.root.minsize(900, 600)

        # Configure styles
        style = ttk.Style()
        style.configure("TLabel", font=("Helvetica", 12), background="#2E3440", foreground="#D8DEE9")
        style.configure("TCombobox", font=("Helvetica", 12))
        style.configure("Treeview", font=("Helvetica", 10), rowheight=40, fieldbackground="#2E3440", 
                            background="#2E3440", foreground="#FFFFFF")
        style.configure("Treeview.Heading", font=("Helvetica", 12, "bold"), 
                    background="#4C566A", foreground="#404040")
        style.map("Treeview.Heading", background=[("active", "#5E81AC")])

        # Header frame
        self.header_frame = tk.Frame(self.root, bg="#424752")
        self.header_frame.pack(fill=tk.X, padx=10, pady=10)

        # Call label
        self.call_label = tk.Label(
            self.header_frame, text="CALL", bg="#A3BE8C", fg="white",
            font=("Helvetica", 16, "bold"), padx=10, pady=5, relief="ridge"
        )
        self.call_label.pack(side=tk.LEFT, padx=10)

        # Put label
        self.put_label = tk.Label(
            self.header_frame, text="PUT", bg="#BF616A", fg="white",
            font=("Helvetica", 16, "bold"), padx=10, pady=5, relief="ridge"
        )
        self.put_label.pack(side=tk.RIGHT, padx=10)

        # Market status indicator
        self.market_status = tk.Label(
            self.header_frame, text="Market Closed", bg="#BF616A", fg="white",
            font=("Helvetica", 12, "bold"), padx=10, pady=5, relief="ridge"
        )
        self.market_status.pack(side=tk.RIGHT, padx=10)

        # Last update time
        self.last_update = tk.Label(
            self.header_frame, text="Last Update: --:--:--", bg="#4C566A", fg="white",
            font=("Helvetica", 12), padx=10, pady=5, relief="ridge"
        )
        self.last_update.pack(side=tk.RIGHT, padx=10)

        # Spot Price
        self.spot_price = tk.Label(
            self.header_frame, text="Spot Price 00000.0", bg="#4C566A", fg="white",
            font=("Helvetica", 12), padx=10, pady=5, relief="ridge"
        )
        self.spot_price.pack(side=tk.RIGHT, padx=10)

        # Dropdown for expiry selection
        self.selected_expiry = tk.StringVar()
        if self.data_fetcher.expiries:
            self.selected_expiry.set(self.data_fetcher.expiries[0])

        self.expiry_dropdown = ttk.Combobox(
            self.header_frame, textvariable=self.selected_expiry,
            values=self.data_fetcher.expiries[:2] if self.data_fetcher.expiries else [],
            state="readonly"
        )
        self.expiry_dropdown.pack(side=tk.TOP, pady=5)
        self.expiry_dropdown.bind("<<ComboboxSelected>>", lambda _: self.reset_sort_and_update_table())

        # Table frame
        self.table_frame = tk.Frame(self.root, bg="#2E3440")
        self.table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Sort order dictionary
        self.sort_order = {}

        # Setup table
        self.setup_table()

    def setup_table(self):
        if not self.data_fetcher.nfo_ce_pe_filtered or not self.data_fetcher.expiries:
            return

        # Create Treeview with columns
        columns = list(self.data_fetcher.nfo_ce_pe_filtered[f"{self.data_fetcher.expiries[0]}"].columns)
        self.columns = columns
        self.columns.remove("PCR")
        self.tree = ttk.Treeview(self.table_frame, columns=columns, show="headings")

        # Configure column headers with sorting
        for col in columns:
            self.tree.heading(col, text=col, anchor=tk.CENTER,
                            command=lambda c=col: self.sort_column(c))
            # Dynamically adjust column width to fit content
            max_width = max([len(str(row[col])) for row in self.data_fetcher.nfo_ce_pe_filtered[f"{self.data_fetcher.expiries[0]}"].to_dict('records')] + [len(col)])
            self.tree.column(col, anchor=tk.CENTER, width=max_width * 7)  # 7 pixels per character approx.

        # # Add vertical scrollbar
        # scrollbar = ttk.Scrollbar(self.table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        # self.tree.configure(yscroll=scrollbar.set)
        # scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # # Add horizontal scrollbar
        # scrollbarH = ttk.Scrollbar(self.table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        # self.tree.configure(xscroll=scrollbarH.set)
        # scrollbarH.pack(side=tk.BOTTOM, fill=tk.X)

        # Pack the tree
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree.tag_configure('atm', background='#5E81AC')  # ATM normal color
        self.tree.tag_configure('atm_blink', background='#88C0D0')  # ATM blink color
        
        self.tree.column("STRIKE", anchor=tk.CENTER)  # Center-align STRIKE column

        # Initialize blink state
        self.blink_state = False
        self.blink_after_id = None

    def sort_column(self, col):
        # Get current expiry and data
        selected_expiry = self.selected_expiry.get()
        selected_data = self.data_fetcher.nfo_ce_pe_filtered.get(selected_expiry)
        
        if selected_data is None:
            return

        # Toggle sort order
        if col not in self.sort_order or self.sort_order[col] == "desc":
            self.sort_order[col] = "asc"
            sorted_data = selected_data.sort_values(by=col, ascending=True)
        else:
            self.sort_order[col] = "desc"
            sorted_data = selected_data.sort_values(by=col, ascending=False)

        # Update table with sorted data
        self.update_table(sorted_data)
    
    def toggle_blink(self):
        """Toggle the blink state of ATM row"""
        if not self.running:
            return
            
        self.blink_state = not self.blink_state

        # Update all ATM rows
        for item in self.tree.get_children():
            if 'atm' in self.tree.item(item)['tags']:
                current_tags = list(self.tree.item(item)['tags'])
                if self.blink_state:
                    if 'atm' in current_tags:
                        current_tags.remove('atm')
                    if 'atm_blink' not in current_tags:
                        current_tags.append('atm_blink')
                else:
                    if 'atm_blink' in current_tags:
                        current_tags.remove('atm_blink')
                    if 'atm' not in current_tags:
                        current_tags.append('atm')
                self.tree.item(item, tags=current_tags)
    
        # Schedule next blink
        self.blink_after_id = self.root.after(500, self.toggle_blink)  # Blink every 500ms

    def update_table(self, data=None):
        try:
            # Clear existing rows
            if hasattr(self, 'tree') and self.tree:
                for row in self.tree.get_children():
                    self.tree.delete(row)

            # Update market status indicator
            if self.is_market_hours():
                self.market_status.config(text="Market Open", bg="#A3BE8C")
            else:
                self.market_status.config(text="Market Closed", bg="#BF616A")

            # Update last update time
            current_time = datetime.now().strftime("%H:%M:%S")
            self.last_update.config(text=f"Last Update: {current_time}")

            #Update last bnf price
            self.spot_price.config(text=f"BANKNIFTY SPOT: {self.data_fetcher.bnf_ltp}")

            # Get data based on selected expiry if not provided
            if data is None:
                selected_expiry = self.selected_expiry.get()
                if not selected_expiry or selected_expiry not in self.data_fetcher.nfo_ce_pe_filtered:
                    return
                data = self.data_fetcher.nfo_ce_pe_filtered[selected_expiry]
            
            # Start blinking if not already started
            if not hasattr(self, 'blink_after_id') or self.blink_after_id is None:
                self.toggle_blink()

            # Update expiry dropdown values if needed
            if self.data_fetcher.expiries:
                current_values = list(self.expiry_dropdown['values'])
                if current_values != self.data_fetcher.expiries[:2]:
                    self.expiry_dropdown['values'] = self.data_fetcher.expiries[:2]

            for index, row in enumerate(self.data_fetcher.nfo_ce_pe_filtered[selected_expiry].to_dict('records')):
                # Determine row tags based on price changes
                tags_list = []
                # Format STRIKE column to include both STRIKE and PCR
                strike_value = row['STRIKE']
                pcr_value = row['PCR']
                formatted_strike = f"{strike_value}\nPCR: {pcr_value}"  # Combine STRIKE and PCR values
                row['STRIKE'] = formatted_strike  # Update row data
                values = [row[col] for col in self.columns]  # Prepare row values

                if hasattr(self.data_fetcher, 'atm_price') and float(strike_value) == float(self.data_fetcher.atm_price):
                    tags_list.append('atm' if not self.blink_state else 'atm_blink')
                    # Convert list to tuple before inserting
                    tags = tuple(tags_list)
                    self.tree.insert("", tk.END, values=values, tags=tags)
                else:
                    self.tree.insert("", "end", values=values, tags=("row",))
            
            avgs = []
            for col in self.columns:
                if col != "STRIKE" and col != " LTP" and col != "LTP":
                    if col == "VOLUME" or col == " VOLUME" or col == "OI" or col == " OI":
                        avgs.append(int(self.data_fetcher.nfo_ce_pe_filtered[selected_expiry][col].mean()))
                    else:
                        avgs.append(self.data_fetcher.nfo_ce_pe_filtered[selected_expiry][col].mean().round(4))
                else:
                    if col == "STRIKE":
                        avgs.append("<- AVG ->")
                    else:
                        avgs.append("")
            self.tree.insert("", "end", values=avgs, tags=("row",))
        
        except Exception as e:
            print(f"Error updating table: {e}")

    def reset_sort_and_update_table(self):
        # Reset sorting state
        self.sort_order.clear()
        # Update table with unsorted data
        self.update_table()

def main():
    # Your API credentials
    api_key = "52747e17-6115-41b8-b71b-5484ef1c2548"
    secret_key = "9353qqzteu"
    ridrect_url = "https://www.google.co.in/"
    mobile_num = '8559034400'
    TOTP_KEY = 'Q3ZR2OEMVSHAHFUHFSNR72FNU3STTD5G'
    PIN = '242424'

    # Initialize data fetcher
    data_fetcher = DataFetcher(api_key, secret_key, TOTP_KEY, PIN, ridrect_url, mobile_num)
    # data_fetcher.fetch_token_data()
    data_fetcher.fetch_market_data()

    # Create and run the UI
    root = tk.Tk()
    app = ExpiryTableApp(root, data_fetcher)
    root.configure(bg="#545F74")
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()