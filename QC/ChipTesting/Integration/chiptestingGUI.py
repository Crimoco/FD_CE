import os 
import sys
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import io
import time
from datetime import datetime
import queue

# Makes modules from adjacent subdirectories searchable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Takes standard console output and puts into a queue that this program will display with GUI
class InputOutput(io.TextIOBase): # Inherits io.TextIOBase so Python treats worker thread output as an object to insert into queue
    def __init__(self, queue, tag = "info"): # Takes in queue as argument and makes variable tag for coloring text during CLI output 
        self.queue = queue # Declares queue
        self.tag = tag # Declares tag
    
    def write(self, str):
        if str and str != "\n":
            self.queue.put((self.tag, str.rstrip("\n"))) # Intercepts print() calls and puts into queue
        elif str == "\n":
            pass
        return len(str) # returns number of characters written successfully to prevent error
    def flush(self): # Normally needed to push buffered text to print but no buffer here exists, thus doesn't do anything but please io.TextIOBase
        pass

# Blocks "worker" thread until user responds with GUI input
class GUIInputProvider:
    # Initializes prompt queue for multithreading and reply prompt as results from ask()
    def __init__(self, prompt_queue, reply_prompt):
        self.prompt_queue = prompt_queue
        self.reply_prompt = reply_prompt
    def ask(self, prompt = ""):
        self.prompt_queue.put(prompt) # Takes user input and drops into prompt queue 
        return self.reply_prompt.get() # Retrieves user input from prompt queue

# Actual GUI for the program
class ChipTestingGUI(tk.Tk):
    # Sets initial window parameters
    def __init__(self):
        super().__init__()
        self.title("DUNE Chip Testing QC")
        self.geometry('1500x1100')
        self.minsize(1100 , 750)

        self.output_queue = queue.Queue() # Carries print call from worker thread to a queue for CLI output
        self.input_queue = queue.Queue() # Carries any request for user input from worker thread to a queue for CLI output
        self.reply_queue = queue.Queue() # Carries response to user input request from main thread to a queue to send to worker thread

        self.worker = None # Holds down variable for thread.Threading() for when I define it as a thread as the program starts
        self.running = False # Track whether there is a current QC test going on and to prevent a second run 

        self.waiting_for_input = False # Variable to track when waiting for input. Trigger variable to send reply out of queue
        self.pending_prompt = "" # Holds prompt as a string in order to make reading prompt easier. Will use this for making buttons usable

    # Details of the UI itself
    def build_UI(self):
        style = ttk.Style(self)
        style.theme_use("default")

        # Details of top hotbar
        top_hotbar = ttk.Frame(self, relief = "groove")
        top_hotbar.pack(side = "top", fill = "x", padx = 6, pady= 4)
        
        ttk.Label(top_hotbar, text = "DUNE Chip Testing GC", font = ("Helvetica", 10, "Bold")).pack(side = "left", padx = 4, pady = 4)
        
        self.button_run = ttk.Button(top_hotbar, text = "▶ Play").pack(side = "left", padx = 4, pady = 4)
        self.button_abort = ttk.Button(top_hotbar, text  = "⏹ Abort").pack(side = "left", padx = 4, pady = 4)

        self.status = tk.StringVar(value = "Idle")
        ttk.Label(top_hotbar, textvariable = self.status, relief = "sunken", font = ("Helvetica", 10), width = 20).pack(side = "right", padx = 6, pady = 4)
        ttk.Label(top_hotbar, text = "Status:").pack(side = "right", padx = 4)

        # Creates tabs under hot bar
        tabs = ttk.Notebook(self)
        tabs.pack(fill = "both", expand = True, padx = 4, pady = 4)

        self.results_tab = ttk.Frame(tabs)
        self.set_up_tab = ttk.Frame(tabs)
        self.state_tab = ttk.Frame(tabs)

        tabs.add(self.results_tab, text = "Results")
        tabs.add(self.set_up_tab, text = "Set Up")
        tabs.add(self.state_tab, text = "State")

        self.build_results_tab()
        self.build_set_up_tab()
        self.build_state_tab()

    # Results tab (To be continued after design decided on)
    def build_results_tab(self):
        self

    # Set Up tab
    def build_set_up_tab(self):
        intro = ttk.LabelFrame(self.set_up_tab, text = "Set Up Confguration").pack(fill = "x", padx = 6, pady = 4)

        # Creates Frame for start up configuration as well as buttons for y/n or m/f
        row0 = ttk.Frame(intro).pack(fill = "x", padx = 6, pady = 4)
        ttk.Label(row0, text = "Simulation Mode:").grid(row = 0, column = 0, sticky = "w")
        self.simulation_variable = tk.StringVar(value = "n")
        ttk.Radiobutton(row0, text = "Yes", variable = self.simulation_variable, value = "y").grid(row = 0, column = 1, sticky = "w")
        ttk.Radiobutton(row0, text = "No", variable = self.simulation_variable, value = "n").grid(row = 0, column = 2, sticky = "w")

        ttk.Label(row0, text = "Bypass RTS:").grid(row = 1, column = 0, sticky = "w")
        self.bypass_rts_variable = tk.StringVar(value =  "n")
        ttk.Radiobutton(row0, text = "Yes", variable = self.bypass_rts_variable, value = "y").grid(row = 1, column = 1, sticky = "w")
        ttk.Radiobutton(row0, text = "No", variable = self.bypass_rts_variable, value = "n").grid(row = 1, column = 2, sticky = "w")

        ttk.Label(row0, text = "Populate mode:").grid(row = 2, column = 0, sticky = "w")
        self.populate_mode = tk.StringVar(value = "m")
        ttk.Radiobutton(row0, text = "Full tray", variable = self.populate_mode, value = "f").grid(row = 2, column = 1, sticky = "w")
        ttk.Radiobutton(row0, text = "Manual", variable = self.populate_mode, value = "m").grid(row = 2, column = 2, sticky = "w")

        data_entry_manual= ttk.LabelFrame(intro, text = "Manua Chip Data Entry (Use only when in manual populate mode)").pack(fill = "x", padx = 6, pady = 4)
        data_entry_headers = ["Tray", "Column", "Row", "DAT", "DAT Socket", "Label", "Delete"]

        # Creates tuple for each entry in data_entry_headers to create a column for each 
        for col, header in enumerate(data_entry_headers):
            ttk.Label(data_entry_manual, text = header, font= ("Helvetica", 10)).grid(row = 0, column = col, padx = 4, pady = 2, sticky = "w'")

        self.chip_rows = [] # Creates a dictionary to keep track of chip rows
        self.chip_row_frame = data_entry_manual # ensures that data_entry_manual can be search by future functions as data_entry_manual is a local variable
        self.chip_row_count = 0 # Keeps track of number of rows 

        # Creates button to add chip data rows or remove all
        row_buttons = ttk.Frame(intro)
        row_buttons.pack(fill = "x", padx = 6, pady = 4)
        ttk.Button(row_buttons, text = "+ Add Chip Data", command = self.add_chip_row).pack(side = "left", pady=2)
        ttk.Button(row_buttons, text = "- Clear All Chip Data", command = self.remove_all_rows).pack(side = "left", pady = 2)

        self.add_chip_row()
        self.add_chip_row()

    # Creates function to add chip rows
    def add_chip_row(self):
        current_row_count = self.chip_row_count + 1 # Turns to next available row number
        row_widgets = {} # Initializes dictionary for that will hold widgets for each row 
        ttk.Label(self.chip_row_frame, text = str(current_row_count)).grid(row = current_row_count, column = 0, padx = 4) # label for row number

        # Creates six drop down menus for each header
        for column_counter, (key, vals) in enumerate([
            ("Tray", ["1", "2"])
            ("Column", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
            ("Row", ["1", "2", "3", "4"])
            ("DAT", ["1", "2"])
            ("Socket", ["21", "22"])
            ("Label", ["CD0", "CD1"])

        ]):
            v = tk.StringVar(value = vals[0]) # Creates a variable v to hold onto current vals selection
            cb = ttk.Combobox(self.chip_row_frame, textvariable = v, value = vals, width = 12, state = "readonly") # Creates combo widget and forbids picking values out of list
            cb.grid(row = current_row_count, column = column_counter + 1, padx = 4, pady = 2) # places combo box in the right cell
            row_widgets[key] = v # Saves tk.StringVar under its field name in the dictionary (Useful to read value user picked)
        

        

    # State tab
    def build_state_tab(self):
        self




        


# Starts this program
if __name__ == "__main__":
    app = ChipTestingGUI()
    app.mainloop()






        



    

    