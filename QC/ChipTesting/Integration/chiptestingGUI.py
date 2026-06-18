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

# Takes usual console output and puts into a queue that this program will display with GUI
class InputOutput(io.TextIOBase): # Inherits io.TextIOBase so Python treats worker thread output as an object to insert into queue
    def __init__(self, queue, tag = "info"): # Takes in queue as argument and makes variable tag for coloring text during CLI output 
        self.queue = queue # Declares queue
        self.tag = tag # Declares tag
    
    def write(self, str):
        if str and str != "\n":
            self.queue.put((self.tag, str.rstrip("\n"))) # Intercepts print() calls and puts into queue
        elif str == "\n":
            pass
        return len(str) # Returns number of characters written successfully to prevent error
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
        
        ttk.Label(top_hotbar, text = "DUNE Chip Testing QC", font = ("Helvetica", 10, "bold")).pack(side = "left", padx = 4, pady = 4)
        
        self.run_button = ttk.Button(top_hotbar, text = "▶ Run", state = "normal", command = self.run)
        self.run_button.pack(side = "left", padx = 4, pady = 4)
        self.abort_button = ttk.Button(top_hotbar, text  = "⏹ Abort", state = "disabled", command = self.abort)
        self.abort_button.pack(side = "left", padx = 4, pady = 4)

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
        out_frame.pack(fill = "both", expand = True, padx= 6, pady = 2)

        # Creates console on right-hand side of GUI
        self.output = scrolledtext.ScrolledText(
            out_frame, state = "disabled", wrap = "word", 
            font = ("Helvetica", 9), height = 22
        )
        self.output.pack(fill = "both", expand = True, padx = 4, pady = 4)

        # Configures console text to differentiate between information types
        self.output.tag_configure("info", foreground = "white", font = ("Courier", 9))
        self.output.tag_configure("error", foreground = "red", font = ("Courier", 9))
        self.output.tag_configure("prompt", foreground = "blue", font = ("Courier", 9, "bold"))
        self.output.tag_configure("answer", foreground = "white", font = ("Courier", 9, "bold"))
        self.output.tag_configure("state", foreground = "orange", font = ("Courier", 9, "bold"))

        self.input_frame = ttk.LabelFrame(intro, text = "Input Required")
        self.input_frame.pack(fill = "both", padx = 6, pady = 6)

        self.answer_var = tk.StringVar()
        self.prompt_label = ttk.Label(self.input_frame, textvariable = self.answer_var, font = ("Courier", 10), width = 15, wraplength = 900, justify = "left") # Remember self.answer_var for input func
        self.prompt_label.pack(anchor = "w", padx = 6, pady = 6)

        input_row = ttk.Frame(self.input_frame)
        input_row.pack(fill = "x", padx = 6, pady = 6)

        self.answer_entry = ttk.Entry(input_row, textvariable = self.answer_var, font = ("Courier", 10), width  = 40)
        self.answer_entry.pack(side = "left", pady = 6)
        self.submit_button = ttk.Button(input_row, text = "Submit", command = self.submit_answer, state = "disabled") # self.submit_answer to be a function that passed text into response_queue
        self.submit_button.pack(side = "right")

        self.set_input_active(False) # To initialize with input frame without any text


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
        self.populate_mode = tk.StringVar(value = "f")
        ttk.Radiobutton(row0, text = "Full tray", variable = self.populate_mode, value = "f", command  = self.show_start_pos_frame).grid(row = 2, column = 1, sticky = "w")
        ttk.Radiobutton(row0, text = "Manual", variable = self.populate_mode, value = "m", command  = self.show_start_pos_frame).grid(row = 2, column = 2, sticky = "w")
        ttk.Radiobutton(row0, text = "Partial", variable = self.populate_mode, value = "p", command  = self.show_start_pos_frame).grid(row = 2, column  = 3, sticky = "w")
        ttk.Radiobutton(row0, text = "Retest Tray", variable = self.populate_mode, value = "r", command  = self.show_start_pos_frame).grid(row = 2, column  = 4, sticky = "w")
        ttk.Radiobutton(row0, text = "Retest Partial Tray", variable = self.populate_mode, value = "rp", command  = self.show_start_pos_frame).grid(row = 2, column  = 5, sticky = "w")

        self.start_pos_frame = ttk.LabelFrame(intro, text = "Start Position")
        pos_row = ttk.Frame(self.start_pos_frame)
        pos_row.pack(fill = "x", padx = 6, pady = 6)
        
        ttk.Label(pos_row, text = "Tray:").grid(row = 0, column = 0, sticky = "w", pady = 4)
        self.start_tray = tk.StringVar(value = "1")
        ttk.Combobox(pos_row, textvariable = self.start_tray, values = ["1", "2"], width = 5, state = "readonly").grid(row = 0, column = 1, padx = 12)
        
        ttk.Label(pos_row, text = "Column:").grid(row = 0, column = 3, sticky = "w", pady = 4)
        self.start_column = tk.StringVar(value = "1")
        ttk.Combobox(pos_row, textvariable = self.start_column, values = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"], width = 5, state = "readonly").grid(row = 0, column = 4, padx = 12)

        ttk.Label(pos_row, text = "Row:").grid(row = 0, column = 5, sticky = "w", pady = 4)
        self.start_row = tk.StringVar(value = "1")
        ttk.Combobox(pos_row, textvariable = self.start_row, values = ["1", "2", "3", "4"], width = 5, state = "readonly").grid(row = 0, column = 6, padx = 12)

        ttk.Label(pos_row, text = "DAT:").grid(row = 0, column = 7, sticky = "w", pady = 4)
        self.start_DAT = tk.StringVar(value = "1")
        ttk.Combobox(pos_row, textvariable = self.start_DAT, values = ["1", "2"], width = 5, state = "readonly").grid(row = 0, column = 8, padx = 12)

        self.start_pos_frame.pack_forget()


        self.chip_row_frame = ttk.LabelFrame(intro, text = "Manual Chip Data Entry (Use only when in manual populate mode)").pack(fill = "x", padx = 6, pady = 4)
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

    def show_start_pos_frame(self):
        mode = self.populate_mode.get()
        if mode in ("p", "rp"):
            self.start_pos_frame.pack(fill = "x", padx = 6, pady = 4)
        else:
            self.start_pos_frame.pack_forget()
            
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
            ("DAT Socket", ["21", "22"]),
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

    # Helper method for remove() so that row below deleted row can be moved up
    def add_chip_row_from_dict(self, d):
        self.add_chip_row()
        last = self.chip_rows[-1]
        for k, v in d.items(): 
            last[k].set(v.get()) # Extracts StringVar() to set in brand new empty chip row
            
    
    def remove_all_rows(self):
        for w in self.chip_row_frame.grid_slaves():
            if int(w.grid_info()["row"]) > 0:
                w.destroy()
        self.chip_rows = []
        self.chip_row_count = 0
    
    # Returns list of dictionaries from chip_rows to forward to RTSStateMachine
    def get_chip_list(self):
        result = []
        for rd in self.chip_rows:
            result.append({k: rd[k].get() for k in rd}) # From each row in self.chip_rows, call .get() on each widget's StringVar() to retrieve selected value
        return result

    # State tab (Remember to create this for later)
    def build_state_tab(self):
        return
    
    # Input/Output helper to determine if waiting for input box is turned off or on and sets up if on
    def set_input_active(self, active, prompt = ""): 
        self.waiting_for_input = active
        if active: 
            self.prompt_label.configure(text=f"{prompt}")
            self.answer_var.set("")
            self.submit_button.configure(state = "normal")
            self.answer_entry.configure(state = "normal")
            self.answer_entry.focus_set()
        else:
            self.prompt_label.configure(text = "{Waiting for program to ask for input}")
            self.submit_button.configure(state = "disabled")
            self.answer_entry.configure(state = "disabled")
        self.pending_prompt = prompt

    # Takes input and makes sure there is an answer, then sanitizes it for send_answer
    def submit_answer(self): 
        if not self.waiting_for_input:
            return
        answer = self.answer_var.get().strip().lower()
        if not answer: # Do not do anything if there is no input
            return
        self.send_answer(answer)
    
    # Sends answer to worker thread
    def send_answer(self, answer):  
        if not self.running:
            return
        self.append_output(f" > {answer}", "answer") # self.append_ouput will write to CLI with color and timestamp
        self.reply_queue.put(answer) # Puts answer into reply queue
        self.set_input_active(False) # Ends active input session to disable text input while RTS State Machine runs
    
    # Adds response onto CLI with a timestamp 
    def append_output(self, text, tag = "info"): # Creates timestamp in Hour:Minute:Second
        self.output.configure(state = "normal") # Allows for text to be written on CLI
        timestamp = datetime.now().strftime("%H:%M:%S") 
        self.output.insert("end", f"{timestamp} {text}\n", tag) # Prints time stamp, space, text and labels information type for coloring
        self.output.see("end") # Scrolls down to end of CLI as would a real terminal
        self.output.configure(state = "disabled") #

    # 
    def run(self):
        # Checks to see if there is already a session in progress, and refuse to start if there is one
        if self.running:
            return
        self.running = True
        self.status.set("Running")
        self.run_button.configure(state = "disabled")
        self.abort_button.configure(state = "normal")

        set_up_answers = {
            "simulation_mode_answer": self.simulation_variable.get(),
            "bypass_rts_answer": self.bypass_rts_variable.get(),
            "populate_mode_answer": self.populate_mode.get(),
            "start_tray": self.start_tray.get(),
            "start_column": self.start_column.get(),
            "start_row": self.start_row.get(),
            "start_DAT": self.start_DAT.get()
        }

        chip_list = self.get_chip_list() if self.simulation_variable.get() == "m" else None # Saves self.chip_rows so that chip information modified afterward will not mess with program

        self.worker = threading.Thread( 
            target = self.worker_thread, # Has self.worker_thread be the function of self.worker (what the thread should execute and behave)
            args = (set_up_answers, chip_list), 
            daemon = True # Declare self.worker as a daemon so that process shuts of when window is deleted

        )
        self.worker.start()
        
    def abort(self):
        if not self.running:
            return
        self.append_output("Aborted, sending exit request")
        self.running = False
        self.status.set("Aborted")
        self.run_button.configure(state = "normal")
        self.abort_button.configure()
        self.set_input_active(False)
        return
    
    # This thread inserts start up questions into queue preloaded, puts stdout and stderr into output queue
    def worker_thread(self, set_up_answers, chip_list):
        startup_queue = queue.Queue()
        startup_queue.put(set_up_answers["simultation_mode_answer"]) 
        startup_queue.put(set_up_answers["bypass_rts_answer"])
        startup_queue.put(set_up_answers["populate_mode_answer"])

        if set_up_answers["populate_mode_answer"] == "m" and chip_list: # If populate mode is set to manual and there is a chip_list specified
            # Loads every inputted value for each header for each chip into startup_queue (So that we can have the values autoloaded for prompts)
            for i, chip in enumerate(chip_list):   
                startup_queue.put(chip.get("Tray"))
                startup_queue.put(chip.get("Column"))
                startup_queue.put(chip.get("Row"))
                startup_queue.put(chip.get("DAT"))
                startup_queue.put(chip.get("DAT Socket"))
                startup_queue.put(chip.get("Label"))
                if i < len(chip_list) - 1:
                    startup_queue.put("y")
                else:
                    startup_queue.put("n")
        
        if set_up_answers["populate_mode_answer"] == "r" or "rp":
            startup_queue.put(set_up_answers["start_tray"])
            startup_queue.put(set_up_answers["start_column"])
            startup_queue.put(set_up_answers["start_row"])
            startup_queue.put(set_up_answers["start_DAT"])


            provider = GUIInputProvider(self.input_queue, self.reply_queue) # Creates the live GUI input provider

            # Answer start up prompts such as "Run in simulation mode", "Bypass RTS?", "Population mode"
            def gui_input(prompt = ""):
                if not startup_queue.empty():
                    answer = startup_queue.get()
                    self.output_queue.put(("info", f"[auto] {prompt.strip()}"))
                    self.output_queue.put(("answer", f" >  {answer}"))
                    return answer
                self.output_queue.put(("prompt", prompt.strip()))
                return provider.ask(prompt)



        return


# Starts this program
if __name__ == "__main__":
    app = ChipTestingGUI()
    app.mainloop()


    