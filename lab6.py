#!/usr/bin/env python3
"""
LAB 6: Sensor Data Logging System
Ashfall Monitoring - Post-Volcanic Eruption

Sensors:
- DHT11: Temperature & Humidity
- Sound Sensor: Simulates tremor/vibration detection

Outputs:
- sensor_data.csv with timestamps
"""

import time
import csv
from datetime import datetime
import board
import adafruit_dht
from gpiozero import Button
import os

# ============================================
# SENSOR CONFIGURATION
# ============================================

# DHT11 Configuration
DHT_PIN = board.D4  # GPIO 4
dht_device = adafruit_dht.DHT11(DHT_PIN)

# Sound Sensor Configuration (Digital Output)
SOUND_PIN = 17  # GPIO 17
sound_sensor = Button(SOUND_PIN, pull_up=False, bounce_time=0.1)

# CSV File Configuration
CSV_FILE = "sensor_data.csv"
LOG_INTERVAL = 5  # seconds between readings

# ============================================
# SIMULATION PARAMETERS
# ============================================

# Convert sensor readings to simulated disaster metrics
def calculate_pm25(temp, humidity):
    """
    Simulate PM2.5 based on temperature and humidity
    Logic: Hot + Dry = More ash in air
    
    Formula: PM2.5 = (temp * 5) + ((100 - humidity) * 3)
    Range: 0-500 µg/m³
    """
    if temp is None or humidity is None:
        return None
    
    pm25 = (temp * 5) + ((100 - humidity) * 3)
    pm25 = max(0, min(500, pm25))  # Clamp between 0-500
    return round(pm25, 1)

def calculate_tremor(sound_detected, previous_tremor=0.01):
    """
    Simulate tremor intensity based on sound detection
    Logic: Loud sound = Ground shaking
    
    Range: 0.001 - 0.10 m/s²
    """
    if sound_detected:
        # Sound detected = tremor spike
        tremor = round(previous_tremor + 0.02, 3)
        tremor = min(tremor, 0.10)  # Max tremor
    else:
        # Decay back to baseline
        tremor = round(previous_tremor * 0.8, 3)
        tremor = max(tremor, 0.001)  # Minimum baseline
    
    return tremor

# ============================================
# CSV SETUP
# ============================================

def initialize_csv():
    """Create CSV file with headers if it doesn't exist"""
    file_exists = os.path.isfile(CSV_FILE)
    
    with open(CSV_FILE, 'a', newline='') as csvfile:
        fieldnames = [
            'Timestamp',
            'Temperature_C',
            'Humidity_%',
            'Sound_Detected',
            'Simulated_PM25',
            'Simulated_Tremor_ms2',
            'Air_Quality_Status',
            'Tremor_Status'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
            print(f"✓ Created new CSV file: {CSV_FILE}")
        else:
            print(f"✓ Appending to existing CSV: {CSV_FILE}")

# ============================================
# DATA LOGGING
# ============================================

def get_air_quality_status(pm25):
    """Classify air quality based on PM2.5"""
    if pm25 is None:
        return "UNKNOWN"
    elif pm25 <= 50:
        return "SAFE"
    elif pm25 <= 150:
        return "MODERATE"
    elif pm25 <= 250:
        return "UNHEALTHY"
    elif pm25 <= 350:
        return "VERY_UNHEALTHY"
    else:
        return "HAZARDOUS"

def get_tremor_status(tremor):
    """Classify tremor intensity"""
    if tremor is None:
        return "UNKNOWN"
    elif tremor < 0.01:
        return "NORMAL"
    elif tremor < 0.02:
        return "MINOR"
    elif tremor < 0.05:
        return "MODERATE"
    else:
        return "STRONG"

def read_and_log_data(previous_tremor):
    """Read all sensors and log to CSV"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Read DHT11
    try:
        temperature = dht_device.temperature
        humidity = dht_device.humidity
    except RuntimeError as e:
        print(f"⚠️  DHT11 read error: {e}")
        temperature = None
        humidity = None
    
    # Read Sound Sensor
    sound_detected = sound_sensor.is_pressed  # True if sound detected
    
    # Calculate simulated values
    pm25 = calculate_pm25(temperature, humidity)
    tremor = calculate_tremor(sound_detected, previous_tremor)
    
    # Get status classifications
    air_status = get_air_quality_status(pm25)
    tremor_status = get_tremor_status(tremor)
    
    # Prepare data row
    data_row = {
        'Timestamp': timestamp,
        'Temperature_C': f"{temperature:.1f}" if temperature else "N/A",
        'Humidity_%': f"{humidity:.1f}" if humidity else "N/A",
        'Sound_Detected': "YES" if sound_detected else "NO",
        'Simulated_PM25': f"{pm25:.1f}" if pm25 else "N/A",
        'Simulated_Tremor_ms2': f"{tremor:.3f}",
        'Air_Quality_Status': air_status,
        'Tremor_Status': tremor_status
    }
    
    # Write to CSV
    with open(CSV_FILE, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=data_row.keys())
        writer.writerow(data_row)
    
    # Print to console
    print(f"\n{'='*60}")
    print(f"🕐 {timestamp}")
    print(f"{'='*60}")
    print(f"🌡️  Temperature:    {temperature}°C" if temperature else "🌡️  Temperature:    N/A")
    print(f"💧 Humidity:       {humidity}%" if humidity else "💧 Humidity:       N/A")
    print(f"🔊 Sound Detected: {'YES ⚠️ ' if sound_detected else 'NO'}")
    print(f"🌫️  PM2.5:          {pm25} µg/m³ [{air_status}]" if pm25 else "🌫️  PM2.5:          N/A")
    print(f"📳 Tremor:         {tremor} m/s² [{tremor_status}]")
    print(f"{'='*60}")
    
    return tremor  # Return for next iteration

# ============================================
# MAIN LOOP
# ============================================

def main():
    """Main logging loop"""
    print("\n" + "="*60)
    print("🌋 ASHFALL MONITORING - DATA LOGGING SYSTEM")
    print("   Lab 6: Sensor Data Logger")
    print("="*60)
    print(f"📊 Logging to: {CSV_FILE}")
    print(f"⏱️  Interval: {LOG_INTERVAL} seconds")
    print(f"🌡️  Sensor 1: DHT11 (Temperature & Humidity)")
    print(f"🔊 Sensor 2: Sound Sensor (Tremor Simulation)")
    print("="*60)
    print("\n⌨️  Press Ctrl+C to stop logging\n")
    
    # Initialize CSV
    initialize_csv()
    
    # Initialize tremor baseline
    current_tremor = 0.01
    
    try:
        while True:
            current_tremor = read_and_log_data(current_tremor)
            time.sleep(LOG_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Logging stopped by user")
        print(f"✓ Data saved to: {CSV_FILE}")
    
    finally:
        dht_device.exit()
        print("✓ Sensors cleaned up")
        print("="*60)

if __name__ == "__main__":
    main()