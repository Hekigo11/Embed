#!/usr/bin/env python3
"""
LAB 8: GUI-Based Environmental Monitoring System
Ashfall Monitoring with Tkinter GUI and Sensor Integration

Sensors:
- DHT11: Temperature & Humidity (GPIO 4)
- Sound Sensor: Digital D0 (GPIO 17)
- Soil Moisture Sensor: Digital D0 (GPIO 27)

Logic:
Dry soil (D0=HIGH) → Heavy ash (high PM2.5)
Wet soil (D0=LOW)  → Clean air (low PM2.5)
"""

import tkinter as tk
import time
import csv
import os
import adafruit_dht
import RPi.GPIO as GPIO
from datetime import datetime
import random

# ========== GPIO SETUP ==========
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

DHT_PIN = 4
SOUND_PIN = 17
SOIL_PIN = 27

GPIO.setup(SOUND_PIN, GPIO.IN)
GPIO.setup(SOIL_PIN, GPIO.IN)

dht_sensor = adafruit_dht.DHT11(DHT_PIN)

# ========== CSV SETUP ==========
CSV_FILE = "lab8_sensor_data.csv"
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Timestamp", "Temp (°C)", "Humidity (%)",
            "Soil Status", "Sound Detected", "PM2.5 (µg/m³)",
            "Air Quality", "Tremor (m/s²)", "Tremor Status", "Errors"
        ])

# ========== STATUS HELPERS ==========
def get_air_quality(pm25):
    if pm25 <= 50:
        return "SAFE"
    elif pm25 <= 150:
        return "MODERATE"
    elif pm25 <= 250:
        return "UNHEALTHY"
    elif pm25 <= 350:
        return "VERY UNHEALTHY"
    else:
        return "HAZARDOUS"

def get_tremor_status(tremor):
    if tremor < 0.01:
        return "NORMAL"
    elif tremor < 0.02:
        return "MINOR"
    elif tremor < 0.05:
        return "MODERATE"
    else:
        return "STRONG"

# ========== MAIN CLASS ==========
class AshfallMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Ashfall Monitoring System - Lab 8")
        self.root.geometry("500x350")
        self.root.resizable(False, False)

        # Variables
        self.prev_tremor = 0.01
        self.error_count = 0

        # GUI Labels
        self.temp_var = tk.StringVar(value="Temp: -- °C")
        self.hum_var = tk.StringVar(value="Humidity: -- %")
        self.soil_var = tk.StringVar(value="Soil: --")
        self.sound_var = tk.StringVar(value="Sound: --")
        self.pm25_var = tk.StringVar(value="PM2.5: -- µg/m³")
        self.air_var = tk.StringVar(value="Air Quality: --")
        self.tremor_var = tk.StringVar(value="Tremor: -- m/s²")
        self.tremor_status_var = tk.StringVar(value="Tremor Status: --")
        self.error_var = tk.StringVar(value="Errors: 0")

        # GUI Layout
        row = 0
        for label in [
            self.temp_var, self.hum_var, self.soil_var, self.sound_var,
            self.pm25_var, self.air_var, self.tremor_var,
            self.tremor_status_var, self.error_var
        ]:
            tk.Label(root, textvariable=label, font=("Arial", 12)).pack(anchor="w", padx=20, pady=3)
            row += 1

        # Start the continuous loop
        self.update_sensors()

    def update_sensors(self):
        """Read sensors, update GUI, and log data."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- DHT11 ---
        try:
            temp = dht_sensor.temperature
            hum = dht_sensor.humidity
        except Exception as e:
            temp = None
            hum = None
            self.error_count += 1
            print(f"DHT11 Error: {e}")

        # --- Soil Moisture ---
        soil_digital = GPIO.input(SOIL_PIN)
        soil_dry = bool(soil_digital)
        soil_status = "DRY (0-20%)" if soil_dry else "WET (80-100%)"

        # --- Sound Sensor ---
        sound_digital = GPIO.input(SOUND_PIN)
        sound_detected = bool(sound_digital)

        # --- Simulated PM2.5 & Tremor ---
        pm25 = round(random.uniform(400, 500), 1) if soil_dry else round(random.uniform(0, 50), 1)
        tremor = round(self.prev_tremor + 0.02, 3) if sound_detected else round(self.prev_tremor * 0.8, 3)
        tremor = max(0.001, min(tremor, 0.10))
        self.prev_tremor = tremor

        # --- Classify Status ---
        air_status = get_air_quality(pm25)
        tremor_status = get_tremor_status(tremor)

        # --- Update GUI ---
        self.temp_var.set(f"Temp: {temp:.1f} °C" if temp else "Temp: N/A")
        self.hum_var.set(f"Humidity: {hum:.1f} %" if hum else "Humidity: N/A")
        self.soil_var.set(f"Soil: {soil_status}")
        self.sound_var.set(f"Sound: {'YES' if sound_detected else 'NO'}")
        self.pm25_var.set(f"PM2.5: {pm25} µg/m³")
        self.air_var.set(f"Air Quality: {air_status}")
        self.tremor_var.set(f"Tremor: {tremor:.3f} m/s²")
        self.tremor_status_var.set(f"Tremor Status: {tremor_status}")
        self.error_var.set(f"Errors: {self.error_count}")

        # --- Log to CSV ---
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp, temp, hum, soil_status, sound_detected,
                pm25, air_status, tremor, tremor_status, self.error_count
            ])

        # Schedule next update (every 5 seconds)
        self.root.after(5000, self.update_sensors)

# ========== MAIN EXECUTION ==========
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = AshfallMonitor(root)
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        dht_sensor.exit()
        GPIO.cleanup()
        print("Clean exit.")
