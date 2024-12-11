import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from nselib import derivatives
import pandas as pd
from datetime import datetime

fo_derivatives = derivatives.nse_live_option_chain("BANKNIFTY")

# Data extracted time taken for storing logic
fo_derivatives['Time'] = pd.to_datetime(fo_derivatives['Fetch_Time']).dt.strftime("%H:%M")

expiry_dates = list(pd.to_datetime(fo_derivatives['Expiry_Date']).dt.strftime("%d-%m-%Y").unique())

# Convert date strings to datetime objects
date_objects = [datetime.strptime(date, "%d-%m-%Y") for date in expiry_dates]

# Get current date
current_date = datetime.now()

# Find the closest date
closest_date = min(date_objects, key=lambda d: abs(d - current_date))

# Convert closest date back to string if needed
closest_date_expiry = closest_date.strftime("%d-%m-%Y")

print(f"The closest date to the current date is: {closest_date_expiry}")


fo_derivatives['Expiry_Date'] = pd.to_datetime(fo_derivatives['Expiry_Date']).dt.strftime("%d-%m-%Y")
fo_derivatives_filtered = fo_derivatives[fo_derivatives['Expiry_Date'] == closest_date_expiry]
fo_derivatives_filtered.reset_index(inplace = True, drop = True)

fo_derivatives_CE = fo_derivatives_filtered[["Symbol", "Expiry_Date", "CALLS_OI", "CALLS_Chng_in_OI", "CALLS_Volume", "CALLS_IV", "CALLS_LTP", "CALLS_Net_Chng", "CALLS_Bid_Qty", "CALLS_Bid_Price", "CALLS_Ask_Price", "CALLS_Ask_Qty","Strike_Price"]]
fo_derivatives_PE = fo_derivatives_filtered[["Symbol", "Expiry_Date", "PUTS_OI", "PUTS_Chng_in_OI", "PUTS_Volume", "PUTS_IV", "PUTS_LTP", "PUTS_Net_Chng", "PUTS_Bid_Qty", "PUTS_Bid_Price", "PUTS_Ask_Price", "PUTS_Ask_Qty","Strike_Price"]]

# Initialize data with default no_of_results
no_of_results = 3 # Top x number of results to be shown

def process_data(no_of_results):
    # Replace `fo_derivatives_CE` and `fo_derivatives_PE` with your actual dataframes
    top_ce_strikes = fo_derivatives_CE.sort_values(by='CALLS_OI', ascending=False).iloc[:no_of_results, -1].to_list()
    top_ce_oi = fo_derivatives_CE.sort_values(by='CALLS_OI', ascending=False).iloc[:no_of_results, 2].to_list()
    avg_ce_oi = int(fo_derivatives_CE['CALLS_OI'].mean())
    top_ce_chg_oi_strikes = fo_derivatives_CE.sort_values(by='CALLS_Chng_in_OI', ascending=False).iloc[:no_of_results, -1].to_list()
    top_ce_chg_oi = fo_derivatives_CE.sort_values(by='CALLS_Chng_in_OI', ascending=False).iloc[:no_of_results, 3].to_list()
    avg_chg_ce_oi = int(fo_derivatives_CE.sort_values('CALLS_Chng_in_OI', ascending=False).iloc[:no_of_results, 3].mean())

    top_pe_strikes = fo_derivatives_PE.sort_values(by='PUTS_OI', ascending=False).iloc[:no_of_results, -1].to_list()
    top_pe_oi = fo_derivatives_PE.sort_values(by='PUTS_OI', ascending=False).iloc[:no_of_results, 2].to_list()
    avg_pe_oi = int(fo_derivatives_PE['PUTS_OI'].mean())
    top_pe_chg_oi_strikes = fo_derivatives_PE.sort_values(by='PUTS_Chng_in_OI', ascending=False).iloc[:no_of_results, -1].to_list()
    top_pe_chg_oi = fo_derivatives_PE.sort_values(by='PUTS_Chng_in_OI', ascending=False).iloc[:no_of_results, 3].to_list()
    avg_chg_pe_oi = int(fo_derivatives_PE.sort_values('PUTS_Chng_in_OI', ascending=False).iloc[:no_of_results, 3].mean())

    # the value returned from here will reflect in the UI the top # no of results are shown here
    return {
        "top_ce_strikes": top_ce_strikes,
        "top_ce_oi": top_ce_oi,
        "top_pe_strikes": top_pe_strikes,
        "top_pe_oi": top_pe_oi,
        "top_ce_chg_oi_strikes": top_ce_chg_oi_strikes,
        "top_ce_chg_oi": top_ce_chg_oi,
        "top_pe_chg_oi_strikes": top_pe_chg_oi_strikes,
        "top_pe_chg_oi": top_pe_chg_oi
    }


current_data = process_data(no_of_results)

# Create main application window
root = tk.Tk()
root.title("Options Dashboard")
root.geometry("1200x800")
root.configure(bg="#1f2937")

# Apply modern styles to tabs using ttk.Style
style = ttk.Style()
style.theme_use('default')
style.configure('TNotebook.Tab', background='#374151', foreground='white', font=('Helvetica', 12, 'bold'), padding=[10, 5])
style.map('TNotebook.Tab', background=[('selected', '#4B5563')], foreground=[('selected', '#F3F4F6')])

# Adjust Notebook layout
notebook = ttk.Notebook(root, style='TNotebook')
notebook.pack(expand=True, fill="both", padx=20, pady=20)

# Function to refresh the charts
def refresh_charts():
    global current_data, canvas_pie, canvas_bar
    current_data = process_data(no_of_results_var.get())

    # Update pie charts
    for ax in axs.flat:
        ax.clear()

    axs[0, 0].pie(current_data['top_ce_oi'], labels=current_data['top_ce_strikes'], autopct="%1.1f%%", startangle=90, colors=["#1f77b4", "#aec7e8", "#c7d5e8"])
    axs[0, 0].set_title("Top CE OI by Strikes", fontsize=12, fontweight="bold")

    axs[0, 1].pie(current_data['top_pe_oi'], labels=current_data['top_pe_strikes'], autopct="%1.1f%%", startangle=90, colors=["#ff7f0e", "#ffbb78", "#ffd8b1"])
    axs[0, 1].set_title("Top PE OI by Strikes", fontsize=12, fontweight="bold")

    axs[1, 0].pie(current_data['top_ce_chg_oi'], labels=current_data['top_ce_chg_oi_strikes'], autopct="%1.1f%%", startangle=90, colors=["#2ca02c", "#98df8a", "#c7e9c0"])
    axs[1, 0].set_title("Change in CE OI by Strikes", fontsize=12, fontweight="bold")

    axs[1, 1].pie(current_data['top_pe_chg_oi'], labels=current_data['top_pe_chg_oi_strikes'], autopct="%1.1f%%", startangle=90, colors=["#9467bd", "#c5b0d5", "#dadaeb"])
    axs[1, 1].set_title("Change in PE OI by Strikes", fontsize=12, fontweight="bold")

    canvas_pie.draw()

    # Update bar charts
    for ax in axs_bar.flat:
        ax.clear()

    axs_bar[0, 0].bar(current_data['top_ce_strikes'], current_data['top_ce_oi'], color=["#1f77b4", "#6baed6", "#9ecae1"], edgecolor="black")
    axs_bar[0, 0].set_title("Top CE OI by Strikes", fontsize=12, fontweight="bold")
    axs_bar[0, 0].set_ylabel("Open Interest")
    axs_bar[0, 0].set_xlabel("Strikes")

    axs_bar[0, 1].bar(current_data['top_pe_strikes'], current_data['top_pe_oi'], color=["#ff7f0e", "#fdae6b", "#fdd0a2"], edgecolor="black")
    axs_bar[0, 1].set_title("Top PE OI by Strikes", fontsize=12, fontweight="bold")
    axs_bar[0, 1].set_ylabel("Open Interest")
    axs_bar[0, 1].set_xlabel("Strikes")

    axs_bar[1, 0].bar(current_data['top_ce_chg_oi_strikes'], current_data['top_ce_chg_oi'], color=["#2ca02c", "#98df8a", "#c7e9c0"], edgecolor="black")
    axs_bar[1, 0].set_title("Change in CE OI by Strikes", fontsize=12, fontweight="bold")
    axs_bar[1, 0].set_ylabel("Change in Open Interest")
    axs_bar[1, 0].set_xlabel("Strikes")

    axs_bar[1, 1].bar(current_data['top_pe_chg_oi_strikes'], current_data['top_pe_chg_oi'], color=["#9467bd", "#c5b0d5", "#dadaeb"], edgecolor="black")
    axs_bar[1, 1].set_title("Change in PE OI by Strikes", fontsize=12, fontweight="bold")
    axs_bar[1, 1].set_ylabel("Change in Open Interest")
    axs_bar[1, 1].set_xlabel("Strikes")

    canvas_bar.draw()

# Tab 1: Settings
tab_settings = tk.Frame(notebook, bg="#1f2937")
notebook.add(tab_settings, text="Settings")

# Dropdown and Set Button
settings_frame = tk.Frame(tab_settings, bg="#1f2937")
settings_frame.pack(pady=20)

# TAB1 variables are listed here
no_of_results_label = tk.Label(settings_frame, text="Number of Strikes:", font=("Helvetica", 12), fg="white", bg="#1f2937")
no_of_results_label.grid(row=0, column=0, padx=10, pady=5)

no_of_results_var = tk.IntVar(value=3)
no_of_results_dropdown = ttk.Combobox(settings_frame, textvariable=no_of_results_var, state="readonly", values=[1, 2, 3, 4, 5], font=("Helvetica", 12))
no_of_results_dropdown.grid(row=0, column=1, padx=10, pady=5)

set_button = tk.Button(settings_frame, text="Set", command=refresh_charts, font=("Helvetica", 12), bg="#4B5563", fg="white", relief="raised")
set_button.grid(row=0, column=2, padx=10, pady=5)

# Tab 2: Pie Charts
tab1 = tk.Frame(notebook, bg="#1f2937")
notebook.add(tab1, text="Strike Pie")

# Create a Matplotlib figure for pie charts
fig, axs = plt.subplots(2, 2, figsize=(12, 10))

# Embed pie charts in Tab 2
canvas_pie = FigureCanvasTkAgg(fig, master=tab1)
canvas_pie_widget = canvas_pie.get_tk_widget()
canvas_pie_widget.pack()

# Tab 3: Bar Charts
tab2 = tk.Frame(notebook, bg="#1f2937")
notebook.add(tab2, text="Strike Bar Chart")

# Create a Matplotlib figure for bar charts
fig_bar, axs_bar = plt.subplots(2, 2, figsize=(14, 10))

# Embed bar charts in Tab 3
canvas_bar = FigureCanvasTkAgg(fig_bar, master=tab2)
canvas_bar_widget = canvas_bar.get_tk_widget()
canvas_bar_widget.pack()

# Now refresh the charts (This is used for filter update control to reflect the changes in the UI)
refresh_charts()

# Pack the updated widgets into display object
canvas_bar_widget = canvas_bar.get_tk_widget()
canvas_bar_widget.pack()

# Initialize bar charts
refresh_charts()

# Run the application
root.mainloop()

