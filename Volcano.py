#!/usr/bin/env python3
"""
Lab 9: Infrastructure + sensor reads + Firebase logging + actuator control

- DHT22 (board.D4)
- PMS7003 (UART)
- MPU-92xx (I2C, addr 0x68)
- MQ135 via ADS1115 (A0)
- Outputs: RGB LED (PWM 3 pins), Beacon (relay/LED), Siren (relay)
- All sensor imports are wrapped in try/except so this runs on PC for demo.

Usage:
    python3 lab9.py

Before running on Raspberry Pi:
- Enable I2C and Serial (raspi-config)
- Install libraries: adafruit-blinka, adafruit-circuitpython-ads1x15, adafruit-circuitpython-dht,
  smbus2, pyserial, firebase-admin, RPi.GPIO (or gpiozero), mysql-connector-python (optional)
"""

import time, json, sys
from datetime import datetime

# -----------------------------
# Firebase setup (replace values)
# -----------------------------
FIREBASE_JSON_PATH = "volcano-monitoring-system-firebase-adminsdk-fbsvc-a22cd5de50.json"
FIREBASE_DB_URL = "https://volcano-monitoring-system-default-rtdb.asia-southeast1.firebasedatabase.app/"


try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
except Exception as e:
    print("firebase_admin not available:", e)
    FIREBASE_AVAILABLE = False

# DHT22
try:
    import board
    import adafruit_dht
    DHT_AVAILABLE = True
except Exception:
    DHT_AVAILABLE = False

# PMS7003 (serial)
try:
    import serial
    PMS_AVAILABLE = True
except Exception:
    PMS_AVAILABLE = False

# MPU (I2C)
try:
    import smbus2
    MPU_AVAILABLE = True
except Exception:
    MPU_AVAILABLE = False

# ADS1115 for MQ135
try:
    if board is None:
        import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    ADS_AVAILABLE = True
except Exception:
    ADS_AVAILABLE = False

# GPIO control
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except Exception:
    GPIO_AVAILABLE = False

# -----------------------------
# Pin mapping (change if needed)
# -----------------------------
# Sensors
DHT_PIN = 4            # GPIO4 (board.D4)
PMS_PORT = "/dev/ttyS0"  # or "/dev/serial0" depending on Pi config
MPU_ADDR = 0x68

# Outputs (BCM numbering)
RGB_R = 18   # PWM pin for Red
RGB_G = 23   # PWM pin for Green
RGB_B = 24   # PWM pin for Blue
BEACON_PIN = 22  # relay control (ON = beacon on)
SIREN_PIN = 25   # relay control for siren

# ADS1115 channel
ADS_CHANNEL = 0  # A0

# -----------------------------
# Initialize Firebase (safe)
# -----------------------------
if FIREBASE_AVAILABLE:
    try:
        cred = credentials.Certificate(FIREBASE_JSON_PATH)
        firebase_admin.initialize_app(cred, {
            'databaseURL': FIREBASE_DB_URL
        })
        fb_ref = db.reference("VolcanoMonitoring/Readings")
        print("Firebase initialized.")
    except Exception as e:
        print("Firebase init error:", e)
        FIREBASE_AVAILABLE = False

# -----------------------------
# Initialize hardware devices (safe)
# -----------------------------
dht = None
if DHT_AVAILABLE:
    try:
        dht = adafruit_dht.DHT22(board.D4)
    except Exception as e:
        print("DHT22 init error:", e)
        dht = None
        DHT_AVAILABLE = False

pms = None
if PMS_AVAILABLE:
    try:
        pms = serial.Serial(PMS_PORT, baudrate=9600, timeout=1)
    except Exception as e:
        print("PMS7003 serial init error:", e)
        pms = None
        PMS_AVAILABLE = False

mpu_bus = None
if MPU_AVAILABLE:
    try:
        mpu_bus = smbus2.SMBus(1)
        # wake up MPU (MPU-6050 compatible)
        try:
            mpu_bus.write_byte_data(MPU_ADDR, 0x6B, 0)
        except Exception:
            pass
    except Exception as e:
        print("MPU init error:", e)
        mpu_bus = None
        MPU_AVAILABLE = False

ads = None
mq_chan = None
if ADS_AVAILABLE:
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=0x48)
        # mq_chan = AnalogIn(ads, getattr(ADS, f'P{ADS_CHANNEL}'))
        mq_chan = AnalogIn(ads, 0)  
    except Exception as e:
        print("ADS1115 init error:", e)
        ads = None
        mq_chan = None
        ADS_AVAILABLE = False

# GPIO init for outputs
if GPIO_AVAILABLE:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    # outputs
    for pin in (RGB_R, RGB_G, RGB_B, BEACON_PIN, SIREN_PIN):
        try:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        except Exception as e:
            print(f"GPIO setup error pin {pin}:", e)
    # PWM for RGB
    try:
        pwm_r = GPIO.PWM(RGB_R, 500)
        pwm_g = GPIO.PWM(RGB_G, 500)
        pwm_b = GPIO.PWM(RGB_B, 500)
        pwm_r.start(0)
        pwm_g.start(0)
        pwm_b.start(0)
    except Exception as e:
        print("PWM init error:", e)
        pwm_r = pwm_g = pwm_b = None
else:
    pwm_r = pwm_g = pwm_b = None

# -----------------------------
# Sensor read helpers
# -----------------------------
import random

def read_dht22():
    if not DHT_AVAILABLE or dht is None:
        return None, None
    try:
        temp = dht.temperature
        hum = dht.humidity
        return temp, hum
    except Exception:
        return None, None

def read_pms7003():
    """Return (pm1, pm25, pm10) or None"""
    if not PMS_AVAILABLE or pms is None:
        return None
    try:
        raw = pms.read(32)
        if len(raw) >= 32 and raw[0] == 0x42 and raw[1] == 0x4d:
            pm1 = raw[10]*256 + raw[11]
            pm25 = raw[12]*256 + raw[13]
            pm10 = raw[14]*256 + raw[15]
            return pm1, pm25, pm10
    except Exception:
        pass
    return None

def read_mpu_accel_mag():
    if not MPU_AVAILABLE or mpu_bus is None:
        return None
    try:
        def r16(reg):
            hi = mpu_bus.read_byte_data(MPU_ADDR, reg)
            lo = mpu_bus.read_byte_data(MPU_ADDR, reg+1)
            val = (hi << 8) | lo
            if val & 0x8000:
                val -= 65536
            return val
        ax = r16(0x3B) / 16384.0
        ay = r16(0x3D) / 16384.0
        az = r16(0x3F) / 16384.0
        mag = (ax*ax + ay*ay + az*az) ** 0.5
        return round(mag, 3)
    except Exception:
        return None

def read_mq135_voltage():
    if not ADS_AVAILABLE or mq_chan is None:
        return None
    try:
        return round(mq_chan.voltage, 3)
    except Exception:
        return None

# -----------------------------
# Actuator helpers
# -----------------------------
def rgb_set_color(r, g, b):
    """r,g,b in [0..100] duty cycle (0=off, 100=max)"""
    if not GPIO_AVAILABLE or pwm_r is None:
        return
    try:
        pwm_r.ChangeDutyCycle(max(0, min(100, r)))
        pwm_g.ChangeDutyCycle(max(0, min(100, g)))
        pwm_b.ChangeDutyCycle(max(0, min(100, b)))
    except Exception:
        pass

def beacon_on(state=True):
    if not GPIO_AVAILABLE:
        return
    try:
        GPIO.output(BEACON_PIN, GPIO.HIGH if state else GPIO.LOW)
    except Exception:
        pass

def siren_on(state=True):
    if not GPIO_AVAILABLE:
        return
    try:
        GPIO.output(SIREN_PIN, GPIO.HIGH if state else GPIO.LOW)
    except Exception:
        pass

# -----------------------------
# Simple alerting logic
# -----------------------------
# def evaluate_alert(pm25, accel_mag, mqv):
    # """
    # Return level (0..3) and reason string.
    # Simple thresholds — tune for field.
    # """
    # level = 0
    # reasons = []
    # if pm25 is not None:
    #     if pm25 > 350:
    #         level = max(level, 3); reasons.append("PM Hazardous")
    #     elif pm25 > 200:
    #         level = max(level, 2); reasons.append("PM Very Unhealthy")
    #     elif pm25 > 100:
    #         level = max(level, 1); reasons.append("PM Unhealthy")
    # if accel_mag is not None:
    #     if accel_mag > 1.0:
    #         level = max(level, 3); reasons.append("Strong Tremor")
    #     elif accel_mag > 0.5:
    #         level = max(level, 2); reasons.append("Moderate Tremor")
    #     elif accel_mag > 0.15:
    #         level = max(level, 1); reasons.append("Light Tremor")
    # if mqv is not None and mqv > 2.5:
    #     level = max(level, 2); reasons.append("Gas Rise")
    # return level, "; ".join(reasons) if reasons else "Normal"
def evaluate_alert(pm25, accel_mag, mqv, temp=None):
    """
    Standardized PHIVOLCS-inspired alert levels.
    Sensors:
      - accel_mag: tremor strength
      - mqv: gas concentration (analog voltage)
      - pm25: ash emission simulation
      - temp: crater temperature simulation
    Returns:
      alert_level (0–5), reason string
    """

    level = 0
    reasons = []

    # --- Level 1: Low Intermittent Unrest ---
    if accel_mag and accel_mag >= 0.05:
        level = max(level, 1)
        reasons.append("Light tremor")
    if mqv and mqv >= 1.0:
        level = max(level, 1)
        reasons.append("Slight gas rise")
    if temp and temp >= 45:
        level = max(level, 1)
        reasons.append("Slight temperature increase")

    # --- Level 2: Moderate Unrest ---
    if accel_mag and accel_mag >= 0.15:
        level = max(level, 2)
        reasons.append("Elevated tremor")
    if mqv and mqv >= 1.8:
        level = max(level, 2)
        reasons.append("Moderate gas increase")
    if temp and temp >= 60:
        level = max(level, 2)
        reasons.append("High temperature")

    # --- Level 3: High Unrest ---
    if accel_mag and accel_mag >= 0.5:
        level = max(level, 3)
        reasons.append("Strong tremor")
    if pm25 and pm25 >= 150:
        level = max(level, 3)
        reasons.append("High ash emission")
    if mqv and mqv >= 2.5:
        level = max(level, 3)
        reasons.append("High gas level")

    # --- Level 4: Hazardous Eruption Imminent ---
    if accel_mag and accel_mag >= 1.0:
        level = max(level, 4)
        reasons.append("Very strong tremor")
    if pm25 and pm25 >= 350:
        level = max(level, 4)
        reasons.append("Hazardous ash emission")

    # --- Level 5: Hazardous Eruption Ongoing ---
    if accel_mag and accel_mag >= 1.5:
        level = max(level, 5)
        reasons.append("Extreme tremor (eruption)")
    if pm25 and pm25 >= 500:
        level = max(level, 5)
        reasons.append("Extreme ash (eruption)")

    # No readings? Background
    if not reasons:
        reasons.append("Background levels")

    return level, "; ".join(reasons)

# -----------------------------
# Firebase write function (best effort)
# -----------------------------
def firebase_log(entry: dict):
    if not FIREBASE_AVAILABLE:
        return False
    try:
        fb_ref.push(entry)
        return True
    except Exception as e:
        print("Firebase push error:", e)
        return False

# -----------------------------
# Main loop
# -----------------------------
def main_loop(interval=2.0):
    print("Starting Lab9 main loop. Press Ctrl-C to stop.")
    try:
        while True:
            ts = datetime.now().isoformat()
            # Read sensors
            temp, hum = read_dht22()
            pms = read_pms7003()
            if pms:
                pm1, pm25, pm10 = pms
            else:
                pm1 = pm25 = pm10 = None
            accel = read_mpu_accel_mag()
            mqv = read_mq135_voltage()
            # Determine alert
            level, reason = evaluate_alert(pm25, accel, mqv)
            # Actuate outputs based on level
            if level == 0:
                rgb_set_color(20,80,20)   # green-ish
                beacon_on(False)
                siren_on(False)
            elif level == 1:
                rgb_set_color(80,80,20)   # yellow
                beacon_on(True)
                siren_on(False)
            elif level == 2:
                rgb_set_color(90,40,0)    # orange
                beacon_on(True)
                siren_on(True)
            else:
                rgb_set_color(100,0,0)    # red
                beacon_on(True)
                siren_on(True)
            # Prepare payload
            payload = {
                "timestamp": ts,
                "dht": {"temp_c": temp, "hum_pct": hum},
                "pm": {"pm1": pm1, "pm2_5": pm25, "pm10": pm10},
                "accel_mag_g": accel,
                "mq_voltage": mqv,
                "alert_level": level,
                "reason": reason
            }
            # Print to console
            print(json.dumps(payload, indent=2, default=str))
            # Firebase push
            fb_ok = firebase_log(payload)
            if fb_ok:
                print("Pushed to Firebase")
            else:
                if FIREBASE_AVAILABLE:
                    print("Firebase available but push failed")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopping main loop")
    finally:
        # Cleanup
        if GPIO_AVAILABLE:
            try:
                pwm_r.stop(); pwm_g.stop(); pwm_b.stop()
            except Exception:
                pass
            GPIO.cleanup()
        # If DHT object exists, best-effort cleanup
        try:
            if dht is not None:
                dht.exit()
        except Exception:
            pass

# -----------------------------
# Quick-run
# -----------------------------
if __name__ == "__main__":
    main_loop(2.0)
