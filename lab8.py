
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from datetime import datetime
import csv
import os

# Hardware libraries
try:
    import board
    import adafruit_dht
    import RPi.GPIO as GPIO
    from gpiozero import RGBLED, LED, Buzzer
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("WARNING: Hardware libraries not available - Running in simulation mode")

# ============================================
# CONFIGURATION
# ============================================

COLORS = {
    'bg_dark': '#2C1810',
    'bg_light': '#FFF5E6',
    'accent_red': '#C74B50',
    'accent_orange': '#DDA86A',
    'accent_peach': '#E5B299',
    'text_dark': '#2C1810',
    'text_light': '#8B6F47',
    'safe': '#2ecc71',
    'moderate': '#f39c12',
    'unhealthy': '#e67e22',
    'danger': '#e74c3c'
}

# Hardware Pins
DHT_PIN = board.D4 if HARDWARE_AVAILABLE else None
SOUND_PIN = 17
SOIL_PIN = 27

# RGB LED pins (Common Cathode)
RGB_RED_PIN = 18
RGB_GREEN_PIN = 23
RGB_BLUE_PIN = 24

# Actuator pins
BUZZER_PIN = 25
BEACON_PIN = 22

# Data files
SENSOR_LOG = "lab8_sensor_log.csv"
REPORT_LOG = "lab8_user_reports.csv"
PERF_LOG = "lab8_performance_log.csv"

# ============================================
# SENSOR HANDLER
# ============================================

class SensorHandler:
    """Handles all sensor reading and data processing (based on lab6_2 logic)"""

    def __init__(self):
        self.running = False

        # Current sensor values
        self.temperature = None
        self.humidity = None
        self.sound_detected = False
        self.soil_is_dry = False
        self.ash_level = "UNKNOWN"
        self.pm25 = None
        self.tremor = 0.01

        # Performance metrics
        self.read_count = 0
        self.error_count = 0
        self.last_read_time = None
        self.last_cycle_ms = 0.0
        self.avg_cycle_ms = 0.0
        self.perf_log_interval = 20

        # Keep last known good DHT values
        self._last_temp_ok = None
        self._last_humid_ok = None

        # Initialize hardware
        if HARDWARE_AVAILABLE:
            try:
                # GPIO setup mirrors lab6_2
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(SOUND_PIN, GPIO.IN)
                GPIO.setup(SOIL_PIN, GPIO.IN)

                self.dht = adafruit_dht.DHT11(DHT_PIN)
                print("Sensors initialized: DHT11, Sound (GPIO), Soil (GPIO)")
            except Exception as e:
                print(f"Sensor initialization error: {e}")
                self.dht = None
                # GPIO still usable for digital reads if import succeeded
        else:
            self.dht = None

    def start(self):
        """Start continuous sensor reading"""
        self.running = True
        thread = threading.Thread(target=self._read_loop, daemon=True)
        thread.start()
        print("Sensor reading thread started")

    def stop(self):
        """Stop sensor reading"""
        self.running = False
        if HARDWARE_AVAILABLE and self.dht:
            try:
                self.dht.exit()
            except Exception:
                pass
        if HARDWARE_AVAILABLE:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    def _read_loop(self):
        """Continuous reading loop"""
        while self.running:
            try:
                _t0 = time.perf_counter()
                self._read_sensors()
                self._calculate_derived_values()
                self._log_data()
                self.read_count += 1
                self.last_read_time = datetime.now()
                # perf
                self.last_cycle_ms = (time.perf_counter() - _t0) * 1000.0
                # simple moving average
                if self.avg_cycle_ms == 0:
                    self.avg_cycle_ms = self.last_cycle_ms
                else:
                    self.avg_cycle_ms = (self.avg_cycle_ms * 0.9) + (self.last_cycle_ms * 0.1)

                # periodic performance log
                if self.read_count % self.perf_log_interval == 0:
                    self._log_performance()

                time.sleep(3)
            except Exception as e:
                self.error_count += 1
                print(f"Sensor read error: {e}")
                time.sleep(5)

    def _read_sensors(self):
        """Read physical sensors - lab6_2 logic"""
        import random

        if HARDWARE_AVAILABLE:
            # DHT11 with small retry loop (lab6_2 reliability improvement)
            if self.dht:
                success = False
                for _ in range(3):
                    try:
                        t = self.dht.temperature
                        h = self.dht.humidity
                        if t is not None and h is not None:
                            self.temperature = t
                            self.humidity = h
                            self._last_temp_ok = t
                            self._last_humid_ok = h
                            success = True
                            break
                    except RuntimeError as e:
                        # Typical transient error; retry shortly
                        time.sleep(0.2)
                    except Exception as e:
                        print(f"Unexpected DHT error: {e}")
                        break
                if not success:
                    # Keep last known good values if available
                    if self._last_temp_ok is not None:
                        self.temperature = self._last_temp_ok
                    if self._last_humid_ok is not None:
                        self.humidity = self._last_humid_ok

            # Sound sensor (digital input) — match lab6_2 mapping
            try:
                sound_digital = GPIO.input(SOUND_PIN)
                self.sound_detected = bool(sound_digital)
            except Exception as e:
                print(f"Sound sensor error: {e}")

            # Soil moisture (digital input) — HIGH->DRY, LOW->WET (lab6_2)
            try:
                soil_digital = GPIO.input(SOIL_PIN)
                self.soil_is_dry = bool(soil_digital)
            except Exception as e:
                print(f"Soil sensor error: {e}")
        else:
            # Simulation mode (same behaviour as lab6_2)
            self.temperature = 28 + random.uniform(0, 8)
            self.humidity = 70 + random.uniform(-10, 10)
            self.sound_detected = random.random() < 0.1
            self.soil_is_dry = random.random() < 0.3
            print(f"[SIM] T={self.temperature:.1f}C H={self.humidity:.1f}% Soil={'DRY' if self.soil_is_dry else 'WET'} Sound={'YES' if self.sound_detected else 'NO'}")

    def _calculate_derived_values(self):
        """Calculate PM2.5 and tremor from available sensors (lab6_2 mapping)."""
        import random

        # PM2.5 mapping derived from digital soil reading (lab6_2 logic):
        # Dry soil -> Heavy ash -> High PM2.5 (400-500)
        # Wet soil -> No ash -> Low PM2.5 (0-50)
        if self.soil_is_dry is None:
            self.pm25 = None
            self.ash_level = "UNKNOWN"
        elif self.soil_is_dry:
            self.pm25 = round(400 + random.uniform(0, 100), 1)
            self.ash_level = "HEAVY"
        else:
            self.pm25 = round(random.uniform(0, 50), 1)
            self.ash_level = "NONE"

        # Tremor (lab6_2 calculate_tremor behaviour)
        if self.sound_detected:
            trem = round(self.tremor + 0.02, 3)
            self.tremor = min(trem, 0.10)
        else:
            trem = round(self.tremor * 0.8, 3)
            self.tremor = max(trem, 0.001)
        
        print(f"[CALC] PM2.5={self.pm25} Ash={self.ash_level} Tremor={self.tremor:.3f}")

    def _log_data(self):
        """Log sensor data to CSV"""
        if not os.path.exists(SENSOR_LOG):
            with open(SENSOR_LOG, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Temperature_C', 'Humidity_%',
                    'Soil_Digital_Reading', 'Soil_Status', 'Ash_Level', 'Simulated_PM25_ugm3',
                    'Sound_Detected', 'Simulated_Tremor_ms2',
                    'Air_Quality_Status', 'Tremor_Status',
                    'Read_Count', 'Errors', 'Cycle_ms', 'Avg_Cycle_ms'
                ])
        
        air_status, _ = self.get_air_quality_status()
        tremor_status, _ = self.get_tremor_status()
        
        with open(SENSOR_LOG, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                f"{self.temperature:.1f}" if self.temperature else "N/A",
                f"{self.humidity:.1f}" if self.humidity else "N/A",
                "DRY" if self.soil_is_dry else "WET",
                "DRY" if self.soil_is_dry else "WET",
                self.ash_level,
                f"{self.pm25:.1f}" if self.pm25 else "N/A",
                "YES" if self.sound_detected else "NO",
                f"{self.tremor:.3f}",
                air_status,
                tremor_status,
                self.read_count,
                self.error_count,
                round(self.last_cycle_ms, 2),
                round(self.avg_cycle_ms, 2)
            ])

    def _log_performance(self):
        """Append a lightweight performance line every N cycles."""
        header = [
            'Timestamp', 'Read_Count', 'Errors', 'Cycle_ms', 'Avg_Cycle_ms'
        ]
        if not os.path.exists(PERF_LOG):
            with open(PERF_LOG, 'w', newline='') as f:
                csv.writer(f).writerow(header)
        with open(PERF_LOG, 'a', newline='') as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                self.read_count,
                self.error_count,
                round(self.last_cycle_ms, 2),
                round(self.avg_cycle_ms, 2)
            ])
    def get_air_quality_status(self):
        """Get air quality classification"""
        if self.pm25 is None:
            return "UNKNOWN", COLORS['text_light']
        elif self.pm25 <= 50:
            return "SAFE", COLORS['safe']
        elif self.pm25 <= 150:
            return "MODERATE", COLORS['moderate']
        elif self.pm25 <= 250:
            return "UNHEALTHY", COLORS['unhealthy']
        else:
            return "HAZARDOUS", COLORS['danger']

    def get_tremor_status(self):
        """Get tremor classification"""
        if self.tremor < 0.01:
            return "NORMAL", COLORS['safe']
        elif self.tremor < 0.02:
            return "MINOR", COLORS['moderate']
        elif self.tremor < 0.05:
            return "MODERATE", COLORS['unhealthy']
        else:
            return "STRONG", COLORS['danger']

    def get_ash_status_color(self):
        """Get color for ash level"""
        if self.ash_level == "NONE":
            return COLORS['safe']
        elif self.ash_level == "LIGHT":
            return COLORS['moderate']
        elif self.ash_level == "MODERATE":
            return COLORS['unhealthy']
        else:
            return COLORS['danger']

# ============================================
# HARDWARE CONTROLLER
# ============================================

class HardwareController:
    """Controls RGB LED, Buzzer, and Beacon"""
    
    def __init__(self):
        if HARDWARE_AVAILABLE:
            try:
                # RGB LED (Common Cathode)
                self.rgb = RGBLED(
                    red=RGB_RED_PIN,
                    green=RGB_GREEN_PIN,
                    blue=RGB_BLUE_PIN,
                    active_high=True
                )
                
                # Buzzer
                self.buzzer = Buzzer(BUZZER_PIN)
                
                # Beacon LED
                self.beacon = LED(BEACON_PIN)
                
                # Turn off everything initially
                self.rgb.off()
                self.buzzer.off()
                self.beacon.off()
                
                print("Hardware outputs initialized: RGB LED, Buzzer, Beacon")
            except Exception as e:
                print(f"Hardware output error: {e}")
                self.rgb = None
                self.buzzer = None
                self.beacon = None
        else:
            self.rgb = None
            self.buzzer = None
            self.beacon = None
    
    def set_rgb_color(self, status):
        """Set RGB LED based on air quality status"""
        if not self.rgb:
            return
        
        try:
            if status == "SAFE":
                self.rgb.color = (0, 1, 0)  # Green
            elif status == "MODERATE":
                self.rgb.color = (1, 1, 0)  # Yellow
            elif status == "UNHEALTHY":
                self.rgb.color = (1, 0.5, 0)  # Orange
            elif status == "HAZARDOUS":
                self.rgb.color = (1, 0, 0)  # Red
            else:
                self.rgb.off()
        except:
            pass
    
    def alert_beep(self, pattern='single'):
        """Trigger buzzer alert"""
        if not self.buzzer:
            return
        
        def beep_thread():
            try:
                if pattern == 'single':
                    self.buzzer.beep(on_time=0.1, off_time=0.1, n=1, background=False)
                elif pattern == 'double':
                    self.buzzer.beep(on_time=0.1, off_time=0.1, n=2, background=False)
                elif pattern == 'urgent':
                    self.buzzer.beep(on_time=0.15, off_time=0.1, n=3, background=False)
            except:
                pass
        
        threading.Thread(target=beep_thread, daemon=True).start()
    
    def set_beacon(self, state, blink=False):
        """Control beacon LED"""
        if not self.beacon:
            return
        
        try:
            if state and blink:
                self.beacon.blink(on_time=0.5, off_time=0.5)
            elif state:
                self.beacon.on()
            else:
                self.beacon.off()
        except:
            pass
    
    def cleanup(self):
        """Clean up GPIO"""
        try:
            if self.rgb:
                self.rgb.off()
            if self.buzzer:
                self.buzzer.off()
            if self.beacon:
                self.beacon.off()
        except:
            pass

# ============================================
# MAIN KIOSK APPLICATION
# ============================================

class AshfallKiosk:
    """Main kiosk application with 2 pages"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Ashfall Monitoring Kiosk - Lab 8")
        self.root.geometry("1024x600")
        self.root.configure(bg=COLORS['bg_light'])
        
        # Initialize systems
        self.sensors = SensorHandler()
        self.hardware = HardwareController()
        self.start_time = datetime.now()
        
        # Current page
        self.current_page = None
        
        # Create main container
        self.main_container = tk.Frame(self.root, bg=COLORS['bg_light'])
        self.main_container.pack(fill=tk.BOTH, expand=True)
        
        # Start with dashboard
        self.show_dashboard()
        
        # Start sensor reading
        self.sensors.start()
        
        # Start update loop
        self.update_loop()
    
    def clear_page(self):
        """Clear current page"""
        for widget in self.main_container.winfo_children():
            widget.destroy()
    
    def show_dashboard(self):
        """Show Page 1: Dashboard"""
        self.clear_page()
        self.current_page = "dashboard"
        DashboardPage(self.main_container, self)
    
    def show_report(self):
        """Show Page 2: Report Conditions"""
        self.clear_page()
        self.current_page = "report"
        ReportPage(self.main_container, self)
    
    def update_loop(self):
        """Continuous update of GUI and hardware"""
        if self.current_page == "dashboard":
            # Update hardware outputs based on sensors
            status, _ = self.sensors.get_air_quality_status()
            self.hardware.set_rgb_color(status)
            
            # Beacon and buzzer for hazardous conditions
            if status == "HAZARDOUS" or self.sensors.tremor > 0.05:
                self.hardware.set_beacon(True, blink=True)
                if self.sensors.read_count % 10 == 0:  # Beep every 30 seconds
                    self.hardware.alert_beep('urgent')
            elif status in ["UNHEALTHY", "VERY_UNHEALTHY"]:
                self.hardware.set_beacon(True, blink=False)
            else:
                self.hardware.set_beacon(False)
        
        # Schedule next update
        self.root.after(1000, self.update_loop)
    
    def cleanup(self):
        """Cleanup on exit"""
        self.sensors.stop()
        self.hardware.cleanup()

# ============================================
# PAGE 1: DASHBOARD
# ============================================

class DashboardPage:
    """Real-time monitoring dashboard"""
    
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.build_page()
        self.update_data()
    
    def build_page(self):
        """Build dashboard UI"""
        # Header
        header = tk.Frame(self.parent, bg=COLORS['accent_orange'], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = tk.Label(
            header,
            text="ASHFALL MONITORING KIOSK",
            font=("Arial", 18, "bold"),
            bg=COLORS['accent_orange'],
            fg='white'
        )
        title.pack(side=tk.LEFT, padx=20, pady=20)
        
        location = tk.Label(
            header,
            text="Barangay Upper Bicutan",
            font=("Arial", 11),
            bg=COLORS['accent_orange'],
            fg='white'
        )
        location.pack(side=tk.RIGHT, padx=20, pady=20)
        
        # Sensor cards container
        cards_frame = tk.Frame(self.parent, bg=COLORS['bg_light'])
        cards_frame.pack(fill=tk.X, padx=20, pady=15)
        
        # Create 4 sensor cards
        self.create_sensor_card(cards_frame, "Air Qual", "pm25", 0, 0)
        self.create_sensor_card(cards_frame, "Temp", "temp", 0, 1)
        self.create_sensor_card(cards_frame, "Humidity", "humidity", 1, 0)
        self.create_sensor_card(cards_frame, "Quake", "tremor", 1, 1)
        
        # Ash indicator
        ash_frame = tk.Frame(self.parent, bg=COLORS['bg_light'])
        ash_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ash_card = tk.Frame(
            ash_frame,
            bg=COLORS['accent_peach'],
            height=70
        )
        ash_card.pack(fill=tk.X, pady=5)
        ash_card.pack_propagate(False)
        
        ash_title = tk.Label(
            ash_card,
            text="ASH ACCUMULATION (Soil Moisture Sensor)",
            font=("Arial", 11, "bold"),
            bg=COLORS['accent_peach'],
            fg=COLORS['text_dark']
        )
        ash_title.pack(side=tk.LEFT, padx=15)
        
        self.soil_status_var = tk.StringVar(value="--")
        self.ash_level_var = tk.StringVar(value="Loading...")
        
        soil_label = tk.Label(
            ash_card,
            textvariable=self.soil_status_var,
            font=("Arial", 14, "bold"),
            bg=COLORS['accent_peach'],
            fg=COLORS['text_dark']
        )
        soil_label.pack(side=tk.LEFT, padx=15)
        
        self.ash_level_label = tk.Label(
            ash_card,
            textvariable=self.ash_level_var,
            font=("Arial", 13, "bold"),
            bg=COLORS['accent_peach']
        )
        self.ash_level_label.pack(side=tk.RIGHT, padx=15)
        
        # Alert banner
        self.alert_frame = tk.Frame(
            self.parent,
            bg=COLORS['danger'],
            height=50
        )
        self.alert_frame.pack(fill=tk.X, padx=20, pady=10)
        self.alert_frame.pack_propagate(False)
        
        self.alert_label = tk.Label(
            self.alert_frame,
            text="CURRENT ALERT: System starting...",
            font=("Arial", 11, "bold"),
            bg=COLORS['danger'],
            fg='white'
        )
        self.alert_label.pack(pady=12)
        
        # Hardware status
        hw_frame = tk.Frame(self.parent, bg=COLORS['bg_light'])
        hw_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(
            hw_frame,
            text="Hardware Status:",
            font=("Arial", 10, "bold"),
            bg=COLORS['bg_light'],
            fg=COLORS['text_dark']
        ).pack(side=tk.LEFT, padx=5)
        
        self.hw_status_var = tk.StringVar(value="Initializing...")
        tk.Label(
            hw_frame,
            textvariable=self.hw_status_var,
            font=("Arial", 9),
            bg=COLORS['bg_light'],
            fg=COLORS['text_light']
        ).pack(side=tk.LEFT, padx=5)
        
        # Navigation buttons
        nav_frame = tk.Frame(self.parent, bg=COLORS['bg_light'])
        nav_frame.pack(fill=tk.X, padx=20, pady=15)
        
        report_btn = tk.Button(
            nav_frame,
            text="Report\nLocation",
            command=self.app.show_report,
            bg=COLORS['accent_orange'],
            fg='white',
            font=("Arial", 11, "bold"),
            width=18,
            height=3,
            relief=tk.FLAT,
            cursor="hand2"
        )
        report_btn.grid(row=0, column=0, padx=8)
        
        for idx, text in enumerate(["Customize\nAlerts", "Health\nChecklist", "Safety\nPlanner"], start=1):
            btn = tk.Button(
                nav_frame,
                text=text,
                command=lambda: messagebox.showinfo("Info", "Available in full version"),
                bg=COLORS['accent_peach'],
                fg=COLORS['text_dark'],
                font=("Arial", 11, "bold"),
                width=18,
                height=3,
                relief=tk.FLAT,
                cursor="hand2"
            )
            btn.grid(row=0, column=idx, padx=8)
    
    def create_sensor_card(self, parent, label, sensor_type, row, col):
        """Create individual sensor card"""
        card = tk.Frame(
            parent,
            bg=COLORS['accent_peach'],
            width=230,
            height=110
        )
        card.grid(row=row, column=col, padx=12, pady=8, sticky="nsew")
        card.grid_propagate(False)
        
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        
        lbl = tk.Label(
            card,
            text=label,
            font=("Arial", 13, "bold"),
            bg=COLORS['accent_peach'],
            fg=COLORS['text_dark']
        )
        lbl.pack(pady=(8, 3))
        
        value_var = tk.StringVar(value="--")
        value_label = tk.Label(
            card,
            textvariable=value_var,
            font=("Arial", 22, "bold"),
            bg=COLORS['accent_peach'],
            fg=COLORS['text_dark']
        )
        value_label.pack()
        
        status_var = tk.StringVar(value="Loading...")
        status_label = tk.Label(
            card,
            textvariable=status_var,
            font=("Arial", 10, "bold"),
            bg=COLORS['accent_peach']
        )
        status_label.pack(pady=(3, 8))
        
        if not hasattr(self, 'cards'):
            self.cards = {}
        
        self.cards[sensor_type] = {
            'value': value_var,
            'status': status_label,
            'status_text': status_var
        }
    
    def update_data(self):
        """Update dashboard with latest sensor data"""
        temp = self.app.sensors.temperature
        humid = self.app.sensors.humidity
        pm25 = self.app.sensors.pm25
        tremor = self.app.sensors.tremor
        soil_dry = self.app.sensors.soil_is_dry
        ash_level = self.app.sensors.ash_level
        
        # DEBUG: Print what GUI sees
        print(f"[GUI] T={temp} H={humid} PM={pm25} Tremor={tremor}")
        
        # Update PM2.5
        if pm25 is not None:
            self.cards['pm25']['value'].set(f"{pm25:.0f} ug/m3")
            status, color = self.app.sensors.get_air_quality_status()
            self.cards['pm25']['status_text'].set(status)
            self.cards['pm25']['status'].config(fg=color)
        
        # Update Temperature
        if temp is not None:
            self.cards['temp']['value'].set(f"{temp:.0f}C")
            if temp > 35:
                self.cards['temp']['status_text'].set("HIGH")
                self.cards['temp']['status'].config(fg=COLORS['unhealthy'])
            else:
                self.cards['temp']['status_text'].set("Normal")
                self.cards['temp']['status'].config(fg=COLORS['safe'])
        
        # Update Humidity
        if humid is not None:
            self.cards['humidity']['value'].set(f"{humid:.0f}%")
            if humid > 80:
                self.cards['humidity']['status_text'].set("High")
                self.cards['humidity']['status'].config(fg=COLORS['moderate'])
            elif humid < 40:
                self.cards['humidity']['status_text'].set("Low")
                self.cards['humidity']['status'].config(fg=COLORS['moderate'])
            else:
                self.cards['humidity']['status_text'].set("Normal")
                self.cards['humidity']['status'].config(fg=COLORS['safe'])
        
        # Update Tremor
        self.cards['tremor']['value'].set(f"{tremor:.2f} m/s2")
        status, color = self.app.sensors.get_tremor_status()
        self.cards['tremor']['status_text'].set(status)
        self.cards['tremor']['status'].config(fg=color)
        
        # Update Soil/Ash
        self.soil_status_var.set(f"Soil: {'DRY' if soil_dry else 'WET'}")
        self.ash_level_var.set(f"Ash: {ash_level}")
        ash_color = self.app.sensors.get_ash_status_color()
        self.ash_level_label.config(fg=ash_color)
        
        # Update alert banner
        air_status, _ = self.app.sensors.get_air_quality_status()
        tremor_status, _ = self.app.sensors.get_tremor_status()
        
        if air_status == "HAZARDOUS" or tremor_status == "STRONG":
            self.alert_frame.config(bg=COLORS['danger'])
            self.alert_label.config(
                bg=COLORS['danger'],
                text=f"ALERT: {air_status} air quality detected"
            )
        elif air_status in ["UNHEALTHY"]:
            self.alert_frame.config(bg=COLORS['unhealthy'])
            self.alert_label.config(
                bg=COLORS['unhealthy'],
                text=f"CAUTION: {air_status} air quality"
            )
        else:
            self.alert_frame.config(bg=COLORS['safe'])
            self.alert_label.config(
                bg=COLORS['safe'],
                text="Conditions normal - No alerts active"
            )
        
      
        hw_text = f"RGB: {'ON' if self.app.hardware.rgb else 'OFF'} | "
        hw_text += f"Buzzer: {'ON' if self.app.hardware.buzzer else 'OFF'} | "
        hw_text += f"Beacon: {'ON' if self.app.hardware.beacon else 'OFF'} | "
        hw_text += f"Reads: {self.app.sensors.read_count} | Errors: {self.app.sensors.error_count}"
        self.hw_status_var.set(hw_text)
        
       
        self.parent.after(2000, self.update_data)

# ============================================
# PAGE 2: REPORT CONDITIONS
# ============================================

class ReportPage:
    """Community reporting form"""
    
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.build_page()
    
    def build_page(self):
        """Build report form UI"""
        # Header
        header = tk.Frame(self.parent, bg=COLORS['accent_orange'], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        back_btn = tk.Button(
            header,
            text="< Back",
            command=self.app.show_dashboard,
            bg=COLORS['accent_orange'],
            fg='white',
            font=("Arial", 11, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            borderwidth=0
        )
        back_btn.pack(side=tk.LEFT, padx=20, pady=20)
        
        title = tk.Label(
            header,
            text="Report your location",
            font=("Arial", 18, "bold"),
            bg=COLORS['accent_orange'],
            fg='white'
        )
        title.pack(side=tk.LEFT, padx=15, pady=20)
        
        # Scrollable content
        canvas = tk.Canvas(self.parent, bg=COLORS['bg_light'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=COLORS['bg_light'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    
        self.ash_thickness = tk.StringVar(value="None")
        self.roof_status = tk.StringVar(value="Manageable")
        self.respiratory = tk.BooleanVar(value=False)
        
       
        self.create_section(
            scrollable_frame,
            "Ash thickness",
            [("None", "None"), ("Light", "Light"), ("Moderate", "Moderate"), ("Heavy", "Heavy")],
            self.ash_thickness
        )
        
  
        self.create_section(
            scrollable_frame,
            "Roof Accumulation Status",
            [("None", "None"), ("Manageable", "Manageable"), ("Dangerous", "Dangerous"), ("Collapsed", "Collapsed")],
            self.roof_status
        )
        
     
        resp_frame = tk.Frame(scrollable_frame, bg=COLORS['bg_light'])
        resp_frame.pack(fill=tk.X, padx=25, pady=15)
        
        resp_label = tk.Label(
            resp_frame,
            text="Respiratory Symptoms",
            font=("Arial", 13, "bold"),
            bg=COLORS['bg_light'],
            fg=COLORS['text_dark']
        )
        resp_label.pack(anchor=tk.W, pady=(0, 8))
        
        resp_check = tk.Checkbutton(
            resp_frame,
            text="Experiencing breathing difficulty or coughing",
            variable=self.respiratory,
            bg=COLORS['bg_light'],
            font=("Arial", 11),
            selectcolor=COLORS['accent_peach']
        )
        resp_check.pack(anchor=tk.W)
        
        # Submit Button
        submit_frame = tk.Frame(scrollable_frame, bg=COLORS['bg_light'])
        submit_frame.pack(pady=30)
        
        submit_btn = tk.Button(
            submit_frame,
            text="SUBMIT REPORT",
            command=self.submit_report,
            bg=COLORS['safe'],
            fg='white',
            font=("Arial", 14, "bold"),
            padx=35,
            pady=12,
            relief=tk.FLAT,
            cursor="hand2"
        )
        submit_btn.pack()
    
    def create_section(self, parent, title, options, variable):
        """Create a radio button section"""
        section_frame = tk.Frame(parent, bg=COLORS['bg_light'])
        section_frame.pack(fill=tk.X, padx=25, pady=15)
        
        title_label = tk.Label(
            section_frame,
            text=title,
            font=("Arial", 13, "bold"),
            bg=COLORS['bg_light'],
            fg=COLORS['text_dark']
        )
        title_label.pack(anchor=tk.W, pady=(0, 8))
        
        options_frame = tk.Frame(section_frame, bg=COLORS['bg_light'])
        options_frame.pack(anchor=tk.W)
        
        for text, value in options:
            rb = tk.Radiobutton(
                options_frame,
                text=text,
                variable=variable,
                value=value,
                bg=COLORS['bg_light'],
                font=("Arial", 11),
                selectcolor=COLORS['accent_peach']
            )
            rb.pack(side=tk.LEFT, padx=12)
    
    def submit_report(self):
        """Submit the report to CSV"""
        # Initialize report CSV if needed
        if not os.path.exists(REPORT_LOG):
            with open(REPORT_LOG, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Ash_Thickness', 'Roof_Status',
                    'Respiratory_Issues', 'Reporter_Location'
                ])
        
        # Append report
        with open(REPORT_LOG, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                self.ash_thickness.get(),
                self.roof_status.get(),
                "YES" if self.respiratory.get() else "NO",
                "Barangay Upper Bicutan"
            ])
        
        # Beep confirmation
        self.app.hardware.alert_beep('double')
        
        # Show confirmation
        messagebox.showinfo(
            "Report Submitted",
            "Thank you! Your report has been submitted.\n\n"
            "The barangay officials have been notified."
        )
        
        # Return to dashboard
        self.app.show_dashboard()

# ============================================
# MAIN ENTRY POINT
# ============================================

def main():
    """Main application entry"""
    root = tk.Tk()
    app = AshfallKiosk(root)
    
    def on_closing():
        if messagebox.askokcancel("Quit", "Stop the monitoring system?"):
            app.cleanup()
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    print("\n" + "="*60)
    print("ASHFALL MONITORING KIOSK - LAB 8")
    print("="*60)
    print("System started successfully")
    print("Dashboard loading...")
    print("\nHardware Mapping:")
    print("  DHT11 -> Simulates DHT22 (Temp & Humidity)")
    print("  Soil Sensor -> Simulates PM2.5 (Ash detection)")
    print("  Sound Sensor -> Simulates Seismic (Tremor detection)")
    print("\nActuators:")
    print("  RGB LED -> Air quality indicator")
    print("  Buzzer -> Audio alerts")
    print("  Beacon LED -> Visual warning")
    print("="*60 + "\n")
    
    root.mainloop()

if __name__ == "__main__":
    main()
