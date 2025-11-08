#!/usr/bin/env python3
"""
LAB 6: Sensor Data Logging System
Ashfall Monitoring - Post-Volcanic Eruption

Sensors:
- DHT11: Temperature & Humidity
- Sound Sensor: Simulates tremor/vibration detection
- Soil Moisture: Simulates ash accumulation/PM2.5 levels

Logic: More ash → Soil becomes drier → Lower moisture reading
       Dry soil = Heavy ashfall conditions

Outputs:
- sensor_data.csv with timestamps
"""

import time
import csv
from datetime import datetime
import board
import adafruit_dht
from gpiozero import Button, MCP3008
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

# Soil Moisture Sensor (Analog via MCP3008)
# Using SPI with MCP3008 ADC
SOIL_CHANNEL = 0  # CH0 on MCP3008
soil_sensor = MCP3008(channel=SOIL_CHANNEL)

# CSV File Configuration
CSV_FILE = "sensor_data.csv"
LOG_INTERVAL = 5  # seconds between readings

# ============================================
# CALIBRATION VALUES
# ============================================

# Soil Moisture Calibration
# You need to calibrate your specific sensor:
# - Dry in air (no moisture) = ~1.0 (100%)
# - Fully wet (in water) = ~0.0 (0%)

SOIL_DRY = 0.95   # Sensor value when completely dry (heavy ash)
SOIL_WET = 0.20   # Sensor value when wet (no ash)

# ============================================
# SIMULATION FORMULAS
# ============================================

def calculate_pm25_from_soil(soil_value):
    """
    Convert soil moisture to simulated PM2.5 (ash density in air)
    
    Logic: 
    - Dry soil (ash covered) = High PM2.5 (lots of ash in air)
    - Wet soil (no ash) = Low PM2.5 (clean air)
    
    Formula: PM2.5 = map soil value (0.2-0.95) to PM2.5 range (0-500)
    
    Returns: PM2.5 in µg/m³ (0-500 range)
    """
    if soil_value is None:
        return None
    
    # Clamp soil value to calibrated range
    soil_clamped = max(SOIL_WET, min(SOIL_DRY, soil_value))
    
    # Normalize to 0-1 range (0=wet, 1=dry)
    normalized = (soil_clamped - SOIL_WET) / (SOIL_DRY - SOIL_WET)
    
    # Map to PM2.5 range (0-500 µg/m³)
    # Higher dryness = Higher PM2.5
    pm25 = normalized * 500
    
    return round(pm25, 1)

def get_ash_accumulation_level(soil_value):
    """
    Get qualitative ash accumulation based on soil moisture
    
    Returns: (level, description)
    """
    if soil_value is None:
        return "UNKNOWN", "Sensor error"
    
    if soil_value > 0.80:
        return "HEAVY", "Thick ash layer detected"
    elif soil_value > 0.60:
        return "MODERATE", "Visible ash accumulation"
    elif soil_value > 0.40:
        return "LIGHT", "Minimal ash present"
    else:
        return "NONE", "No significant ash"

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
            'Soil_Moisture_Raw',
            'Soil_Moisture_%',
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
        print(f"⚠️  DHT11 read error: {e}")
        temperature = None
        humidity = None
    
    # Read Soil Moisture Sensor (analog value 0.0 to 1.0)
    try:
        soil_raw = soil_sensor.value  # 0.0 (wet) to 1.0 (dry)
        soil_percent = (1.0 - soil_raw) * 100  # Convert to moisture % (100% = wet)
    except Exception as e:
        print(f"⚠️  Soil sensor read error: {e}")
        soil_raw = None
        soil_percent = None
    
    # Read Sound Sensor
    sound_detected = sound_sensor.is_pressed  # True if sound detected
    
    # Calculate derived values
    pm25 = calculate_pm25_from_soil(soil_raw)
    ash_level, ash_desc = get_ash_accumulation_level(soil_raw)
    tremor = calculate_tremor(sound_detected, previous_tremor)
    
    # Get status classifications
    air_status = get_air_quality_status(pm25)
    tremor_status = get_tremor_status(tremor)
    
    # Prepare data row
    data_row = {
        'Timestamp': timestamp,
        'Temperature_C': f"{temperature:.1f}" if temperature else "N/A",
        'Humidity_%': f"{humidity:.1f}" if humidity else "N/A",
        'Soil_Moisture_Raw': f"{soil_raw:.3f}" if soil_raw else "N/A",
        'Soil_Moisture_%': f"{soil_percent:.1f}" if soil_percent else "N/A",
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
    print(f"🕐 {timestamp}")
    print(f"{'='*70}")
    print(f"🌡️  Temperature:      {temperature}°C" if temperature else "🌡️  Temperature:      N/A")
    print(f"💧 Humidity:         {humidity}%" if humidity else "💧 Humidity:         N/A")
    print(f"🌱 Soil Moisture:    {soil_percent:.1f}% (Raw: {soil_raw:.3f})" if soil_raw else "🌱 Soil Moisture:    N/A")
    print(f"🔊 Sound Detected:   {'YES ⚠️ ' if sound_detected else 'NO'}")
    print(f"{'─'*70}")
    print(f"🌋 Ash Level:        {ash_level} - {ash_desc}")
    print(f"🌫️  PM2.5 (simulated): {pm25:.0f} µg/m³ [{air_status}]" if pm25 else "🌫️  PM2.5:            N/A")
    print(f"📳 Tremor:           {tremor:.3f} m/s² [{tremor_status}]")
    print(f"{'='*70}")
    
    return tremor  # Return for next iteration

# ============================================
# MAIN LOOP
# ============================================

def main():
    """Main logging loop"""
    print("\n" + "="*70)
    print("🌋 ASHFALL MONITORING - DATA LOGGING SYSTEM")
    print("   Lab 6: Sensor Data Logger with Soil Moisture")
    print("="*70)
    print(f"📊 Logging to: {CSV_FILE}")
    print(f"⏱️  Interval: {LOG_INTERVAL} seconds")
    print(f"🌡️  Sensor 1: DHT11 (Temperature & Humidity)")
    print(f"🌱 Sensor 2: Soil Moisture (Ashfall Simulation)")
    print(f"🔊 Sensor 3: Sound Sensor (Tremor Simulation)")
    print("="*70)
    print("\n💡 SENSOR LOGIC:")
    print("   • Dry soil (high value) = Heavy ash = High PM2.5")
    print("   • Wet soil (low value)  = No ash    = Low PM2.5")
    print("="*70)
    print("\n🧪 CALIBRATION INFO:")
    print(f"   • Dry (in air):  {SOIL_DRY:.2f} → Heavy ash")
    print(f"   • Wet (in water): {SOIL_WET:.2f} → No ash")
    print("="*70)
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
        print("="*70)

if __name__ == "__main__":
    main()
