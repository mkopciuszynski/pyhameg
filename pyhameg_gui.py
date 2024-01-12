import tkinter as tk
import tkinter.messagebox as msgbox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta

import time
import serial
import io
import winsound

# Time distance between subsequent reading
gate_time = 5

# Serial port for HAMEG digital counter
ser = serial.Serial(
    port='COM4',
    baudrate=9600,
    timeout=1
)

# This value is subtracted from recorded frequency to keep the number short
zero_freq = 5.97e6


class Plotter:
    """
    This class is responsible for frequency plot
    """

    def __init__(self):

        self.fig = plt.Figure(figsize=(7, 8), dpi=100)
        self.axs = self.fig.subplots(2, 1, sharex=True)
        self.fig.subplots_adjust(wspace=0.0)

        self.finish_freq = 0.0
        self.start_freq = 0.0
        self.slope = 0.0

        self.time = []
        self.freq_data = []
        self.diff_data = []

        ax = self.axs[1]
        ax.set_xlabel('Time [s]')
        ax.set_ylabel('Diff [Hz/min]')
        ax = self.axs[0]
        ax.set_ylabel('Freq [Hz]')

    def update_plot(self, freq):
        self.time.append(len(self.time) * gate_time)
        self.freq_data.append(freq)
        if len(self.time) > 5:
            x_last = self.time[-5:]
            y_last = self.freq_data[-5:]
            slope, intercept = np.polyfit(x_last, y_last, 1)
            self.diff_data.append(slope * 60)
        else:
            self.diff_data.append(-0.0001)
        if len(self.time) > 50:
            x_last = self.time[-50:]
            y_last = self.freq_data[-50:]
            slope, intercept = np.polyfit(x_last, y_last, 1)
            self.slope = slope * 60
        ax = self.axs[0]
        ax.relim()
        ax.autoscale_view()
        ax.plot(self.time[-1], self.freq_data[-1], '.b')
        ax = self.axs[1]
        ax.relim()
        ax.autoscale_view()
        ax.plot(self.time[-1], self.diff_data[-1], '.r')
        self.fig.canvas.draw()

    def clear_plot(self):
        self.time = []
        self.freq_data = []
        self.diff_data = []
        ax = self.axs[1]
        ax.clear()
        ax.set_xlabel('Time [s]')
        ax.set_ylabel('Diff [Hz/min]')
        ax = self.axs[0]
        ax.clear()
        ax.set_ylabel('Freq [Hz]')

    def finish_line_plot(self, delta_freq):
        start_freq = self.freq_data[-1]
        self.finish_freq = start_freq - delta_freq
        self.start_freq = start_freq
        ax = self.axs[0]
        ax.axhline(y=start_freq - delta_freq)
        ax.axhline(y=start_freq)


class App:
    """
    Main class responsible for GUI building and looped reading
    """
    def __init__(self):

        self.delta_freq = None
        self.time_left = None
        self.freq_left = None
        self.plotter = Plotter()

        self.root = tk.Tk()
        self.root.title("Hameg Logger by MK")
        self.root.geometry("700x1000+0+0")

        self.canvas = FigureCanvasTkAgg(self.plotter.fig, master=self.root)
        self.canvas.get_tk_widget().pack()

        self.message_text = tk.Text(self.root, height=25, width=60)
        self.message_text.pack(side=tk.LEFT)

        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(side=tk.LEFT, padx=20, fill="x")

        self.reset_button = tk.Button(self.button_frame, text="Clear", width=10, command=self.button_reset)
        self.input_entry = tk.Entry(self.button_frame, width=10)
        self.start_button = tk.Button(self.button_frame, text="Start", width=10, command=self.button_start)
        self.exit_button = tk.Button(self.button_frame, text="Exit", width=10, command=self.exit_app)

        self.input_entry.grid(row=1, column=1, padx=2, pady=20)
        self.start_button.grid(row=1, column=2, padx=2, pady=20)

        self.reset_button.grid(row=2, column=1, padx=2, pady=20)
        self.exit_button.grid(row=2, column=2, padx=2, pady=20)

        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        self.update_loop()

    def exit_app(self):
        self.root.destroy()
        ser.close()

    def update_loop(self):

        current_time = datetime.now()
        self.message_text.delete(1.0, tk.END)
        self.message_text.insert(tk.END, current_time.strftime("%H:%M:%S%z"))
        self.message_text.insert(tk.END, ": ")

        last_freq = 0.0
        for i in range(5):
            if ser.isOpen():
                try:
                    ser.write("xmt\r".encode('ascii'))
                    time.sleep(0.1)
                    response = ser.read_until(expected='\r')
                    str_ind = response.find(b'MHz')
                    if str_ind > 0:
                        last_freq = float(response[0:str_ind - 1]) * 10 ** 6 - zero_freq
                        break
                    else:
                        time.sleep(0.1)
                except Exception as e1:
                    print(e1)
            else:
                print("cannot open serial port ")

        self.plotter.update_plot(last_freq)

        self.message_text.insert(tk.END, "\nLast freq Hz: ")
        self.message_text.insert(tk.END, "%.4f" % last_freq)
        self.message_text.insert(tk.END, "\nDiff Hz/min: ")
        self.message_text.insert(tk.END, "%.4f" % self.plotter.diff_data[-1])
        self.message_text.insert(tk.END, "\nSlope (last 50 points) Hz/min: ")
        self.message_text.insert(tk.END, "%.4f" % self.plotter.slope)
        self.message_text.insert(tk.END, "\n")

        if self.plotter.finish_freq > 0:

            self.freq_left = (self.plotter.freq_data[-1] - self.plotter.finish_freq)  # /plotter.diff_data[-1]
            self.time_left = -(self.plotter.freq_data[-1] - self.plotter.finish_freq) / self.plotter.diff_data[-1]

            self.message_text.insert(tk.END, "\nFreq left [Hz]: ")
            self.message_text.insert(tk.END, "%.2f" % self.freq_left)
            self.message_text.insert(tk.END, "\nTime left [min]: ")
            self.message_text.insert(tk.END, "%.2f" % self.time_left)
            if self.time_left < 1:
                winsound.Beep(2500, 100)
            if self.time_left < 0:
                winsound.Beep(2500, 1000)

        time_difference = datetime.now() - current_time
        new_time = int(time_difference.total_seconds() * 1000)
        new_time = 5000 if new_time > 5000 else new_time
        self.root.after(gate_time * 1000 - new_time, self.update_loop)

    def button_reset(self):
        self.plotter.clear_plot()
        self.message_text.insert(tk.END, "\n======Clear======\n")

    def button_start(self):
        self.message_text.insert(tk.END, "\n======Start======\n")
        self.delta_freq = float(self.input_entry.get())
        self.plotter.finish_line_plot(self.delta_freq)


app = App()
app.root.mainloop()
