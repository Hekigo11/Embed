import tkinter as tk
from tkinter import ttk
import threading
import time
import json
import socket
from datetime import datetime

# ==== TRY IMPORT HARDWARE LIBRARIES ====
try:
    import Adafruit_DHT
    import serial
    import smbus2
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    import board
    DHT_AVAILABLE = True
except:
    DHT_AVAILABLE = False

try:
    i2c = board.I2C()
    ads = ADS.ADS1115(i2c)
    mq_channel = AnalogIn(ads, ADS.P0)
    ADS_AVAILABLE = True
except:
    ADS_AVAILABLE = False

try:
    ser = serial.Serial("/dev/ttyS0", baudrate=9600, timeout=1)
    PMS_AVAILABLE = True
except:
    PMS_AVAILABLE = False

try:
    bus = smbus2.SMBus(1)
    MPU_ADDR = 0x68
    bus.write_byte_data(MPU_ADDR, 0x6B, 0)
    MPU_AVAILABLE = True
except:
    MPU_AVAILABLE = False

# ==== OPTIONAL: MARIADB ====
try:
    import mysql.connector
    db = mysql.connector.connect(
        host="localhost", user="root", password="", database="volcano"
    )
    cursor = db.cursor()
    DB_AVAILABLE = True
except:
    DB_AVAILABLE = False

# ==== READ FUNCTIONS ====
def read_dht():
    if not DHT_AVAILABLE: return "No Sensor"
    h,t = Adafruit_DHT.read_retry(11, 4)
    if h and t: return f"{t:.1f}°C / {h:.1f}%"
    return "Error"

def read_pms():
    if not PMS_AVAILABLE: return "No Sensor"
    data = ser.read(32)
    if len(data) < 32: return "No Data"
    pm25 = data[12]*256 + data[13]
    return f"{pm25} µg/m³"

def read_mpu():
    if not MPU_AVAILABLE: return "No Sensor"
    try:
        ax_h = bus.read_byte_data(MPU_ADDR, 0x3B)
        ax_l = bus.read_byte_data(MPU_ADDR, 0x3C)
        ax = (ax_h << 8) | ax_l
        return f"AX:{ax}"
    except:
        return "Error"

def read_mq():
    if not ADS_AVAILABLE: return "No ADS"
    return f"{mq_channel.voltage:.2f} V"

# ==== NETWORK SENDER ====
def send_to_pc(data):
    try:
        s = socket.socket()
        s.connect(("192.168.1.10", 5000))  # <--- change to your PC IP
        s.send(json.dumps(data).encode())
        s.close()
    except:
        pass

# ==== DB LOGGER ====
def log_to_db(data):
    if not DB_AVAILABLE: return
    try:
        cursor.execute(
            "INSERT INTO sensor_logs (timestamp, dht, pm, mpu, mq) VALUES (%s,%s,%s,%s,%s)",
            (datetime.now(), data["dht"], data["pm"], data["mpu"], data["mq"])
        )
        db.commit()
    except:
        pass

# ==== GUI THREAD ====
def update_loop():
    while True:
        dht = read_dht()
        pm  = read_pms()
        mpu = read_mpu()
        mq  = read_mq()

        dht_var.set(dht)
        pm_var.set(pm)
        mpu_var.set(mpu)
        mq_var.set(mq)

        if send_flag.get():  
            packet = {"dht": dht, "pm": pm, "mpu": mpu, "mq": mq}
            send_to_pc(packet)
            log_to_db(packet)

        time.sleep(1)

# ==== GUI ====
root = tk.Tk()
root.title("Volcano Monitoring System GUI")

dht_var = tk.StringVar(); pm_var = tk.StringVar()
mpu_var = tk.StringVar(); mq_var = tk.StringVar()
send_flag = tk.BooleanVar(value=False)

ttk.Label(root, text="DHT11 Temperature & Humidity").pack()
ttk.Label(root, textvariable=dht_var, font=("Arial", 14)).pack(pady=5)

ttk.Label(root, text="PMS7003 PM2.5").pack()
ttk.Label(root, textvariable=pm_var, font=("Arial", 14)).pack(pady=5)

ttk.Label(root, text="MPU-9265 Seismic").pack()
ttk.Label(root, textvariable=mpu_var, font=("Arial", 14)).pack(pady=5)

ttk.Label(root, text="MQ-135 Gas (ADS1115)").pack()
ttk.Label(root, textvariable=mq_var, font=("Arial", 14)).pack(pady=5)

ttk.Checkbutton(root, text="Send Live Data (LAN + DB)", variable=send_flag).pack(pady=10)

threading.Thread(target=update_loop, daemon=True).start()
root.mainloop()
