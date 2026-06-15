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
        self.build_UI()


    # Details of the UI itself
    def build_UI(self):
        style = ttk.Style(self)
        style.theme_use("default")

        # Details of top hotbar
        top_hotbar = ttk.Frame(self, relief = "groove")
        top_hotbar.pack(side = "top", fill = "x", padx = 6, pady= 4)
        
        ttk.Label(top_hotbar, text = "DUNE Chip Testing GC", font = ("Helvetica", 10, "bold")).pack(side = "left", padx = 4, pady = 4)
        
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

    # Results tab
    def build_results_tab(self):
        intro = self.results_tab
        out_frame = ttk.LabelFrame(intro, text = "Live CLI Output")
        out_frame.pack(fill = "y", expand = False, padx= 6, pady = 2)

        # Creates console on right-hand side of GUI
        self.output = scrolledtext.ScrolledText(
            out_frame, state = "disabled", wrap = "word", 
            font = ("Helvetica", 9), height = 22
        )
        self.output.pack(fill = "both", expand = True, padx = 4, pady = 4)

        # Configures console text to differentiate between information types
        self.output.tag_configure("info", foreground = "white")
        self.output.tag_configure("error", foreground = "red")
        self.output.tag_configure("prompt", foreground = "blue", font = ("Courier", 9, "bold"))
        self.output.tag_configure("answer", foreground = "white", font = ("Courier", 9, "bold"))
        self.output.tag_configure("state", foreground = "orange", font = ("Courier", 9, "bold"))

        self.input_frame = ttk.LabelFrame(intro, text = "Input Required")
        self.input_frame.pack(fill = "x", padx = 6, pady = 6)

        self.prompt_label = ttk.Label(self.input_frame, textvariable = self.answer_var, font = ("Courier", 10), width = 15, wraplength = 900, justify = "right") # Remember self.answer_var for input func
        self.prompt_label.pack(anchor = "w", padx = 6, pady = 6)

        input_row = ttk.Frame(self.input_frame)
        input_row.pack(fill = "x", padx = 6, pady = 6)

        self.answer_var = tk.StringVar()
        self.answer_entry = ttk.Entry(input_row, textvariable = self.answer_var, font = ("Courier", 10), width  = 15)
        self.answer_entry.pack(side = "left", pady = 6)
        self.submit_button = ttk.Button(input_row, text = "Submit", command = self.submit_answer, state = "disabled") # self.submit_answer to be a function that passed text into response_queue
        self.submit_button.pack(side = "left")

        self.set_input_active(False) # To initialize with input frame collapsed


    # Set Up tab
    def build_set_up_tab(self):
        intro = ttk.LabelFrame(self.set_up_tab, text = "Set Up Confguration")
        intro.pack(fill = "x", padx = 6, pady = 4)

        # Creates Frame for start up configuration as well as buttons for y/n or m/f
        row0 = ttk.Frame(intro)
        row0.pack(fill = "x", padx = 6, pady = 4)

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


        self.chip_row_frame = ttk.LabelFrame(intro, text = "Manua Chip Data Entry (Use only when in manual populate mode)").pack(fill = "x", padx = 6, pady = 4)
        data_entry_headers = ["Tray", "Column", "Row", "DAT", "DAT Socket", "Label", "Delete"]


        self.chip_row_frame = ttk.LabelFrame(intro, text = "Manual Chip Data Entry (Use only when in manual populate mode)")
        self.chip_row_frame.pack(fill = "x", padx = 6, pady = 4)
        
        data_entry_headers = ["#", "Tray", "Column", "Row", "DAT", "DAT Socket", "Label", "Delete"]
        # Creates tuple for each entry in data_entry_headers to create a column for each 
        for col, header in enumerate(data_entry_headers):
            ttk.Label(self.chip_row_frame, text = header, font= ("Helvetica", 10)).grid(row = 0, column = col, padx = 4, pady = 2, sticky = "w")

        self.chip_rows = [] # Creates a dictionary to keep track of each chip rows
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
            ("Tray", ["1", "2"]),
            ("Column", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]),
            ("Row", ["1", "2", "3", "4"]),
            ("DAT", ["1", "2"]),
            ("Socket", ["21", "22"]),
            ("Label", ["CD0", "CD1"])

        ]):
            v = tk.StringVar(value = vals[0]) # Creates a variable v to hold onto current vals selection
            cb = ttk.Combobox(self.chip_row_frame, textvariable = v, value = vals, width = 12, state = "readonly") # Creates combo widget and forbids picking values out of list
            cb.grid(row = current_row_count, column = column_counter + 1, padx = 4, pady = 2) # places combo box in the right cell
            row_widgets[key] = v # Saves tk.StringVar under its field name in the dictionary (Useful to read value user picked)

        def remove(row_idx = current_row_count - 1):
            self.chip_rows.pop(row_idx) # Removes row's dictionary of StringVars from chip_rows
            # Rebuilds the display so that lower rows move upward
            for w in self.chip_row_frame.grid_slaves(): # Returns every widget currently placed in chip_row_frame
                if int(w.grid_info()["row"]) > 0: # Checks if row is not the header row
                    w.destroy() # destroys chip row's widgets
            self.chip_row_count = 0
            tmp = list(self.chip_rows) # Temporarily copies chip_rows into a temp list to keep chip_row data after deletion
            self.chip_rows = []
            # Loops through saved rows to re-add into chip_rows to reset row number that will be displayed in column
            for rd in tmp:
                self.add_chip_row_from_dict(rd) 

        ttk.Button(self.chip_row_frame, text = "X", width = 2, command = remove).grid(row = current_row_count, column = 7, padx = 4)
        self.chip_rows.append(row_widgets) 
        self.chip_row_count += 1

    def add_chip_row_from_dict(self, d):
        self.add_chip_row()
        last = self.chip_rows[-1]
        for k, v in d.items(): 
            last[k].set(v.get() if hasattr(v, "get") else v) # Checks if value has a get() method then extracts to put into new widget
            
    
    def remove_all_rows(self):
        for w in self.chip_row_frame.grid_slaves():
            if int(w.grid_info()["row"]) > 0:
                w.destroy
        self.chip_rows = []
        self.chip_row_count = 0
    
    # Returns list of dictionaries from chip_rows to forward to RTSStateMachine
    def get_chip_list(self):
        result = []
        for rd in self.chip_rows:
            result.append({k: rd[k].get() for k in rd})
        return result

    # State tab
    def build_state_tab(self):
        return
    
    def set_input_active(self, active, prompt = ""): # Input/Output helper to determine if waiting for input boxed is turned off or on and sets up if on
        self.waiting_for_input = active
        if active: 
            self.prompt_label.configure(text=f"{prompt}")
            self.answer_var.set("")
            self.submit_button.configure(state = "normal")
            self.answer_entry.configure(state = "normal")
            self.answer_entry.focus_set()
        else:
            self.prompt_label.configure(text = "{Watiing for program to ask for input}")
            self.submit_button.configure(state = "disabled")
            self.answer_entry.configure(state = "disabled")
        self.pending_prompt = prompt

    def submit_answer(self): # Takes input and makes sure there is an answer, then sanitizes it for send_answer
        if not self.waiting_for_input:
            return
        answer = self.answer_var.get().strip().lower()
        if not answer: # Do not do anything if no actual answer is inputted
            return
        self.send_answer(answer)
    
    def send_answer(self, answer): # Sends answer to worker thread 
        if not self.running:
            return
        self.append_output(f" > {answer}", "answer") # self.append_ouput will write to CLI with color and timestamp
        self.reply_queue.put(answer) # Puts answer into reply queue
        self.set_input_active(False) # 
    
    def append_output(self, text, tag = "info"):
        self.output.configure(state = "normal")
        timestamp = datetime.now().strftime("%H:%M:%S") # creates timestamp in Hour:Minute:Second




# Starts this program
if __name__ == "__main__":
    app = ChipTestingGUI()
    app.mainloop()


    