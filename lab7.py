#!/usr/bin/env python3
"""
LAB 7: GUI Data Visualization System
Ashfall Monitoring - Data Viewer

Features:
- Figma-inspired color scheme
- Real-time data table
- Multi-sensor graph plotting
- CSV data loading from Lab 6
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import os
from datetime import datetime

# ============================================
# FIGMA COLOR PALETTE
# ============================================

COLORS = {
    'bg_dark': '#2C1810',       # Dark brown background
    'bg_light': '#FFF5E6',      # Cream/beige
    'accent_red': '#C74B50',    # Red accent
    'accent_orange': '#DDA86A', # Orange headers
    'accent_peach': '#E5B299',  # Light peach
    'text_dark': '#2C1810',     # Dark text
    'text_light': '#8B6F47',    # Light brown text
    'safe': '#2ecc71',          # Green
    'moderate': '#f39c12',      # Yellow
    'unhealthy': '#e67e22',     # Orange
    'danger': '#e74c3c'         # Red
}

# ============================================
# MAIN APPLICATION
# ============================================

class AshfallDataViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Ashfall Monitoring - Data Viewer (Lab 7)")
        self.root.geometry("1200x800")
        self.root.configure(bg=COLORS['bg_light'])
        
        # Data storage
        self.df = None
        self.csv_file = "sensor_data.csv"
        
        # Auto-refresh
        self.auto_refresh = tk.BooleanVar(value=False)
        
        # Build GUI
        self.create_header()
        self.create_controls()
        self.create_data_table()
        self.create_graph()
        self.create_status_bar()
        
        # Load initial data
        self.load_data()
    
    # ----------------------------------------
    # HEADER SECTION
    # ----------------------------------------
    
    def create_header(self):
        """Create orange header bar"""
        header_frame = tk.Frame(self.root, bg=COLORS['accent_orange'], height=80)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)
        
        # Title
        title_label = tk.Label(
            header_frame,
            text="ASHFALL MONITORING - DATA VIEWER",
            font=("Helvetica", 24, "bold"),
            bg=COLORS['accent_orange'],
            fg='white'
        )
        title_label.pack(pady=20)
    
    # ----------------------------------------
    # CONTROL BUTTONS
    # ----------------------------------------
    
    def create_controls(self):
        """Create control buttons"""
        control_frame = tk.Frame(self.root, bg=COLORS['bg_light'])
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Load CSV Button
        load_btn = tk.Button(
            control_frame,
            text="Load CSV",
            command=self.load_data,
            bg=COLORS['accent_orange'],
            fg='white',
            font=("Helvetica", 12, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        load_btn.pack(side=tk.LEFT, padx=5)
        
        # Refresh Button
        refresh_btn = tk.Button(
            control_frame,
            text="Refresh",
            command=self.refresh_data,
            bg=COLORS['accent_peach'],
            fg=COLORS['text_dark'],
            font=("Helvetica", 12, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Clear Button
        clear_btn = tk.Button(
            control_frame,
            text="Clear",
            command=self.clear_data,
            bg=COLORS['accent_red'],
            fg='white',
            font=("Helvetica", 12, "bold"),
            padx=20,
            pady=10,
            relief=tk.FLAT,
            cursor="hand2"
        )
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Auto-refresh checkbox
        auto_check = tk.Checkbutton(
            control_frame,
            text="Auto-refresh (5s)",
            variable=self.auto_refresh,
            command=self.toggle_auto_refresh,
            bg=COLORS['bg_light'],
            font=("Helvetica", 11),
            selectcolor=COLORS['accent_peach']
        )
        auto_check.pack(side=tk.LEFT, padx=20)
        
        # Record count label
        self.record_label = tk.Label(
            control_frame,
            text="Records: 0",
            bg=COLORS['bg_light'],
            fg=COLORS['text_light'],
            font=("Helvetica", 11)
        )
        self.record_label.pack(side=tk.RIGHT, padx=10)
    
    # ----------------------------------------
    # DATA TABLE
    # ----------------------------------------
    
    def create_data_table(self):
        """Create scrollable data table"""
        # Container frame
        table_container = tk.Frame(self.root, bg=COLORS['bg_light'])
        table_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Label
        table_label = tk.Label(
            table_container,
            text="SENSOR DATA (Last 50 Readings)",
            font=("Helvetica", 14, "bold"),
            bg=COLORS['bg_light'],
            fg=COLORS['text_dark']
        )
        table_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Table frame with scrollbar
        table_frame = tk.Frame(table_container, bg='white')
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        
        # Treeview (table)
        self.tree = ttk.Treeview(
            table_frame,
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set,
            selectmode='browse',
            height=10
        )
        
        v_scrollbar.config(command=self.tree.yview)
        h_scrollbar.config(command=self.tree.xview)
        
        # Pack scrollbars and tree
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Define columns
        columns = ('Time', 'Temp', 'Humid', 'Soil', 'Ash Level', 'PM2.5', 'Tremor', 'Air Status')
        self.tree['columns'] = columns
        
        # Format columns
        self.tree.column('#0', width=0, stretch=tk.NO)  # Hide first column
        self.tree.column('Time', width=150, anchor=tk.W)
        self.tree.column('Temp', width=80, anchor=tk.CENTER)
        self.tree.column('Humid', width=80, anchor=tk.CENTER)
        self.tree.column('Soil', width=100, anchor=tk.CENTER)
        self.tree.column('Ash Level', width=100, anchor=tk.CENTER)
        self.tree.column('PM2.5', width=90, anchor=tk.CENTER)
        self.tree.column('Tremor', width=90, anchor=tk.CENTER)
        self.tree.column('Air Status', width=130, anchor=tk.CENTER)
        
        # Create headings
        self.tree.heading('#0', text='')
        self.tree.heading('Time', text='Timestamp')
        self.tree.heading('Temp', text='Temp (°C)')
        self.tree.heading('Humid', text='Humid (%)')
        self.tree.heading('Soil', text='Soil Status')
        self.tree.heading('Ash Level', text='Ash Level')
        self.tree.heading('PM2.5', text='PM2.5')
        self.tree.heading('Tremor', text='Tremor')
        self.tree.heading('Air Status', text='Air Quality')
        
        # Style treeview
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'Treeview',
            background='white',
            foreground=COLORS['text_dark'],
            rowheight=30,
            fieldbackground='white',
            font=('Helvetica', 10)
        )
        style.configure('Treeview.Heading', font=('Helvetica', 11, 'bold'))
        style.map('Treeview', background=[('selected', COLORS['accent_peach'])])
    
    # ----------------------------------------
    # GRAPH SECTION
    # ----------------------------------------
    
    def create_graph(self):
        """Create matplotlib graph"""
        # Container
        graph_container = tk.Frame(self.root, bg=COLORS['bg_light'])
        graph_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Label
        graph_label = tk.Label(
            graph_container,
            text="REAL-TIME SENSOR TRENDS",
            font=("Helvetica", 14, "bold"),
            bg=COLORS['bg_light'],
            fg=COLORS['text_dark']
        )
        graph_label.pack(anchor=tk.W, pady=(0, 10))
        
        # Create figure
        self.fig = Figure(figsize=(10, 4), dpi=100, facecolor=COLORS['bg_light'])
        self.ax1 = self.fig.add_subplot(121)  # Left: PM2.5 & Temperature
        self.ax2 = self.fig.add_subplot(122)  # Right: Tremor & Humidity
        
        # Canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    # ----------------------------------------
    # STATUS BAR
    # ----------------------------------------
    
    def create_status_bar(self):
        """Create bottom status bar"""
        status_frame = tk.Frame(self.root, bg=COLORS['accent_orange'], height=40)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready | No data loaded",
            bg=COLORS['accent_orange'],
            fg='white',
            font=("Helvetica", 10)
        )
        self.status_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.update_time_label = tk.Label(
            status_frame,
            text="",
            bg=COLORS['accent_orange'],
            fg='white',
            font=("Helvetica", 10)
        )
        self.update_time_label.pack(side=tk.RIGHT, padx=20, pady=10)
    
    # ----------------------------------------
    # DATA OPERATIONS
    # ----------------------------------------
    
    def load_data(self):
        """Load data from CSV"""
        if not os.path.exists(self.csv_file):
            messagebox.showwarning(
                "File Not Found", 
                f"CSV file not found: {self.csv_file}\n\n"
                "Please run Lab 6 first to generate data."
            )
            self.status_label.config(text="No CSV file found")
            return
        
        try:
            # Read CSV
            self.df = pd.read_csv(self.csv_file)
            
            # Update table
            self.update_table()
            
            # Update graph
            self.update_graph()
            
            # Update status
            record_count = len(self.df)
            self.record_label.config(text=f"Records: {record_count}")
            self.status_label.config(text=f"✓ Loaded {record_count} records from {self.csv_file}")
            self.update_time_label.config(text=f"Last update: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV:\n{str(e)}")
            self.status_label.config(text=f"Error loading CSV")
    
    def refresh_data(self):
        """Refresh data from CSV"""
        self.load_data()
    
    def clear_data(self):
        """Clear table and graph"""
        # Clear table
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Clear graph
        self.ax1.clear()
        self.ax2.clear()
        self.canvas.draw()
        
        # Clear data
        self.df = None
        
        # Update status
        self.record_label.config(text="Records: 0")
        self.status_label.config(text="Cleared | No data loaded")
        self.update_time_label.config(text="")
    
    def update_table(self):
        """Update table with latest data"""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if self.df is None or len(self.df) == 0:
            return
        
        # Get last 50 rows
        display_df = self.df.tail(50)
        
        # Insert rows
        for idx, row in display_df.iterrows():
            # Extract time from timestamp
            time_str = row['Timestamp'].split(' ')[1] if ' ' in row['Timestamp'] else row['Timestamp']
            
            # Get air quality status for color coding
            air_status = row.get('Air_Quality_Status', 'UNKNOWN')
            
            values = (
                time_str,
                row.get('Temperature_C', 'N/A'),
                row.get('Humidity_%', 'N/A'),
                row.get('Soil_Moisture_Status', 'N/A'),
                row.get('Ash_Accumulation_Level', 'N/A'),
                row.get('Simulated_PM25', 'N/A'),
                row.get('Simulated_Tremor_ms2', 'N/A'),
                air_status
            )
            
            # Insert with tag for coloring
            self.tree.insert('', tk.END, values=values, tags=(air_status,))
        
        # Configure tags for colors
        self.tree.tag_configure('SAFE', background='#d4edda')
        self.tree.tag_configure('MODERATE', background='#fff3cd')
        self.tree.tag_configure('UNHEALTHY', background='#f8d7da')
        self.tree.tag_configure('VERY_UNHEALTHY', background='#f5c6cb')
        self.tree.tag_configure('HAZARDOUS', background='#f1aeb5')
    
    def update_graph(self):
        """Update graphs with data"""
        if self.df is None or len(self.df) == 0:
            return
        
        # Clear axes
        self.ax1.clear()
        self.ax2.clear()
        
        # Get last 50 data points
        plot_df = self.df.tail(50)
        
        # Extract data
        timestamps = range(len(plot_df))
        temps = pd.to_numeric(plot_df['Temperature_C'], errors='coerce')
        pm25 = pd.to_numeric(plot_df['Simulated_PM25'], errors='coerce')
        humidity = pd.to_numeric(plot_df['Humidity_%'], errors='coerce')
        tremor = pd.to_numeric(plot_df['Simulated_Tremor_ms2'], errors='coerce')
        
        # GRAPH 1: Temperature & PM2.5
        ax1_twin = self.ax1.twinx()
        
        line1 = self.ax1.plot(timestamps, temps, color=COLORS['accent_orange'], 
                               linewidth=2, marker='o', markersize=4, label='Temperature (°C)')
        line2 = ax1_twin.plot(timestamps, pm25, color=COLORS['accent_red'], 
                               linewidth=2, marker='s', markersize=4, label='PM2.5 (µg/m³)')
        
        self.ax1.set_xlabel('Reading Index', fontsize=10, color=COLORS['text_dark'])
        self.ax1.set_ylabel('Temperature (°C)', fontsize=10, color=COLORS['accent_orange'])
        ax1_twin.set_ylabel('PM2.5 (µg/m³)', fontsize=10, color=COLORS['accent_red'])
        self.ax1.set_title('Temperature & Air Quality', fontsize=12, fontweight='bold', color=COLORS['text_dark'])
        
        self.ax1.tick_params(axis='y', labelcolor=COLORS['accent_orange'])
        ax1_twin.tick_params(axis='y', labelcolor=COLORS['accent_red'])
        self.ax1.grid(True, alpha=0.3)
        
        # Combine legends
        lines1, labels1 = self.ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        self.ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
        
        # GRAPH 2: Humidity & Tremor
        ax2_twin = self.ax2.twinx()
        
        line3 = self.ax2.plot(timestamps, humidity, color=COLORS['safe'], 
                               linewidth=2, marker='o', markersize=4, label='Humidity (%)')
        line4 = ax2_twin.plot(timestamps, tremor * 1000, color=COLORS['moderate'], 
                               linewidth=2, marker='^', markersize=4, label='Tremor (×10⁻³ m/s²)')
        
        self.ax2.set_xlabel('Reading Index', fontsize=10, color=COLORS['text_dark'])
        self.ax2.set_ylabel('Humidity (%)', fontsize=10, color=COLORS['safe'])
        ax2_twin.set_ylabel('Tremor (×10⁻³ m/s²)', fontsize=10, color=COLORS['moderate'])
        self.ax2.set_title('Humidity & Seismic Activity', fontsize=12, fontweight='bold', color=COLORS['text_dark'])
        
        self.ax2.tick_params(axis='y', labelcolor=COLORS['safe'])
        ax2_twin.tick_params(axis='y', labelcolor=COLORS['moderate'])
        self.ax2.grid(True, alpha=0.3)
        
        # Combine legends
        lines3, labels3 = self.ax2.get_legend_handles_labels()
        lines4, labels4 = ax2_twin.get_legend_handles_labels()
        self.ax2.legend(lines3 + lines4, labels3 + labels4, loc='upper left', fontsize=9)
        
        # Adjust layout
        self.fig.tight_layout()
        self.canvas.draw()
    
    # ----------------------------------------
    # AUTO-REFRESH
    # ----------------------------------------
    
    def toggle_auto_refresh(self):
        """Toggle auto-refresh functionality"""
        if self.auto_refresh.get():
            self.status_label.config(text="Auto-refresh enabled")
            self.auto_refresh_loop()
        else:
            self.status_label.config(text="⏸Auto-refresh disabled")
    
    def auto_refresh_loop(self):
        """Auto-refresh data every 5 seconds"""
        if self.auto_refresh.get():
            self.refresh_data()
            self.root.after(5000, self.auto_refresh_loop)  # 5 seconds

# ============================================
# MAIN ENTRY POINT
# ============================================

def main():
    root = tk.Tk()
    app = AshfallDataViewer(root)
    root.mainloop()

if __name__ == "__main__":
    main()