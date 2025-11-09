#!/usr/bin/env python3
"""
LAB 6: Sensor Data Logging System
Ashfall Monitoring - Post-Volcanic Eruption

Sensors:
- DHT11: Temperature & Humidity (GPIO 4)
- Sound Sensor: Digital output (GPIO 17)
- Soil Moisture: Digital output D0 (GPIO 27)

Logic: Dry soil (D0=HIGH) = Heavy ash = High PM2.5
       Wet soil (D0=LOW) = No ash = Low PM2.5

Outputs:
- sensor_data.csv with timestamps
"""

import time
import csv
from datetime import datetime
import board
import adafruit_dht
import RPi.GPIO as GPIO
import os

# ============================================
# GPIO SETUP
# ============================================

# Use BCM pin numbering
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# ============================================
# SENSOR CONFIGURATION
# ============================================

# DHT11 Configuration
DHT_PIN = board.D4  # GPIO 4
dht_device = adafruit_dht.DHT11(DHT_PIN)

# Sound Sensor Configuration (Digital Output D0)
SOUND_PIN = 17  # GPIO 17
GPIO.setup(SOUND_PIN, GPIO.IN)

# Soil Moisture Sensor (Digital Output D0)
SOIL_PIN = 27  # GPIO 27
GPIO.setup(SOIL_PIN, GPIO.IN)

# CSV File Configuration
CSV_FILE = "sensor_data.csv"
LOG_INTERVAL = 5  # seconds between readings

# ============================================
# CALIBRATION/MAPPING
# ============================================

# Digital soil sensor mapping:
# D0 = HIGH (1) → Dry soil → Heavy ash
# D0 = LOW (0)  → Wet soil → No ash

def calculate_pm25_from_soil(soil_is_dry):
    """
    Convert digital soil sensor to simulated PM2.5
    
    Logic: 
    - Dry (D0=HIGH) = Heavy ash = High PM2.5 (400-500 range)
    - Wet (D0=LOW)  = No ash = Low PM2.5 (0-50 range)
    
    Returns: PM2.5 in µg/m³
    """
    if soil_is_dry is None:
        return None
    
    if soil_is_dry:
        # Dry = Heavy ash (add some variation)
        import random
        pm25 = 400 + random.uniform(0, 100)
    else:
        # Wet = Clean air
        import random
        pm25 = random.uniform(0, 50)
    
    return round(pm25, 1)

def get_ash_accumulation_level(soil_is_dry):
    """
    Get qualitative ash accumulation based on soil sensor
    
    Returns: (level, description)
    """
    if soil_is_dry is None:
        return "UNKNOWN", "Sensor error"
    
    if soil_is_dry:
        return "HEAVY", "Dry conditions - Thick ash layer detected"
    else:
        return "NONE", "Moist conditions - No significant ash"

def get_soil_moisture_status(soil_is_dry):
    """
    Convert digital reading to descriptive moisture level
    
    Returns: moisture description
    """
    if soil_is_dry is None:
        return "ERROR"
    elif soil_is_dry:
        return "DRY (0-20%)"
    else:
        return "WET (80-100%)"

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
        # Decay back to baselineS
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
            'Soil_Digital_Reading',
            'Soil_Moisture_Status',
            'Sound_Detected',
            'Ash_Accumulation_Level',
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
# STATUS CLASSIFICATION
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

# ============================================
# DATA LOGGING
# ============================================

def read_and_log_data(previous_tremor):
    """Read all sensors and log to CSV"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Read DHT11
    try:
        temperature = dht_device.temperature
        humidity = dht_device.humidity
    except RuntimeError as e:
        print(f"DHT11 read error: {e}")
        temperature = None
        humidity = None
    
    # Read Soil Moisture Sensor (Digital D0)
    try:
        soil_digital = GPIO.input(SOIL_PIN)  # 1 = Dry, 0 = Wet
        soil_is_dry = bool(soil_digital)
        soil_status = get_soil_moisture_status(soil_is_dry)
    except Exception as e:
        print(f"Soil sensor read error: {e}")
        soil_digital = None
        soil_is_dry = None
        soil_status = "ERROR"
    
    # Read Sound Sensor (Digital D0)
    try:
        sound_digital = GPIO.input(SOUND_PIN)  # 1 = Sound detected
        sound_detected = bool(sound_digital)
    except Exception as e:
        print(f"Sound sensor read error: {e}")
        sound_detected = False
    
    # Calculate derived values
    pm25 = calculate_pm25_from_soil(soil_is_dry)
    ash_level, ash_desc = get_ash_accumulation_level(soil_is_dry)
    tremor = calculate_tremor(sound_detected, previous_tremor)
    
    # Get status classifications
    air_status = get_air_quality_status(pm25)
    tremor_status = get_tremor_status(tremor)
    
    # Prepare data row
    data_row = {
        'Timestamp': timestamp,
        'Temperature_C': f"{temperature:.1f}" if temperature else "N/A",
        'Humidity_%': f"{humidity:.1f}" if humidity else "N/A",
        'Soil_Digital_Reading': "DRY" if soil_is_dry else "WET" if soil_is_dry is not None else "N/A",
        'Soil_Moisture_Status': soil_status,
        'Sound_Detected': "YES" if sound_detected else "NO",
        'Ash_Accumulation_Level': ash_level,
        'Simulated_PM25': f"{pm25:.1f}" if pm25 else "N/A",
        'Simulated_Tremor_ms2': f"{tremor:.3f}",
        'Air_Quality_Status': air_status,
        'Tremor_Status': tremor_status
    }
    
    # Write to CSV
    with open(CSV_FILE, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=data_row.keys())
        writer.writerow(data_row)
    
    # Print to console with ash visualization
    print(f"\n{'='*70}")
    print(f"{timestamp}")
    print(f"{'='*70}")
    print(f"Temperature:      {temperature:.1f}C" if temperature else "Temperature:      N/A")
    print(f"Humidity:         {humidity:.1f}%" if humidity else "Humidity:         N/A")
    print(f"Soil Sensor:      {soil_status} (Digital: {'HIGH' if soil_is_dry else 'LOW'})")
    print(f"Sound Detected:   {'YES' if sound_detected else 'NO'}")
    print(f"{'─'*70}")
    print(f"Ash Level:        {ash_level} - {ash_desc}")
    print(f"PM2.5 (simulated): {pm25:.0f} ug/m³ [{air_status}]" if pm25 else "PM2.5:            N/A")
    print(f"Tremor:           {tremor:.3f} m/s² [{tremor_status}]")
    print(f"{'='*70}")
    
    return tremor  # Return for next iteration

# ============================================
# MAIN LOOP
# ============================================

def main():
    """Main logging loop"""
    print("\n" + "="*70)
    print("ASHFALL MONITORING - DATA LOGGING SYSTEM")
    print("   Lab 6: Sensor Data Logger with Digital Soil Moisture")
    print("="*70)
    print(f"Logging to: {CSV_FILE}")
    print(f"Interval: {LOG_INTERVAL} seconds")
    print(f"Sensor 1: DHT11 (Temperature & Humidity) - GPIO 4")
    print(f"ensor 2: Soil Moisture Digital (D0) - GPIO 27")
    print(f" Sensor 3: Sound Sensor Digital (D0) - GPIO 17")
    print("="*70)
    print("\n SENSOR LOGIC:")
    print("   • Dry soil (D0=HIGH) = Heavy ash = High PM2.5")
    print("   • Wet soil (D0=LOW)  = No ash    = Low PM2.5")
    print("="*70)
    # print("\n WIRING CHECK:")
    # print("   DHT11:  VCC→3.3V, GND→GND, DATA→GPIO4")
    # print("   Soil:   VCC→5V, GND→GND, D0→GPIO27")
    # print("   Sound:  VCC→5V, GND→GND, D0→GPIO17")
    # print("="*70)
    print("\nPress Ctrl+C to stop logging\n")
    
    # Initialize CSV
    initialize_csv()
    
    # Initialize tremor baseline
    current_tremor = 0.01
    
    try:
        while True:
            current_tremor = read_and_log_data(current_tremor)
            time.sleep(LOG_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n Logging stopped by user")
        print(f"Data saved to: {CSV_FILE}")
    
    finally:
        dht_device.exit()
        GPIO.cleanup()
        print("Sensors cleaned up")
        print("="*70)

if __name__ == "__main__":
    main()
