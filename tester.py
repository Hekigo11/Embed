import serial
import time
from smbus2 import SMBus
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn
import board
import busio
import adafruit_dht

# ============================================================
# PMS7003 SETUP (UART)
# ============================================================

pms = serial.Serial(
    port="/dev/serial0",
    baudrate=9600,
    timeout=1
)

def read_pms7003():
    """Read PM1, PM2.5, PM10"""
    data = pms.read(32)

    if len(data) < 32:
        return None

    if data[0] == 0x42 and data[1] == 0x4D:
        pm1  = (data[10] << 8) | data[11]
        pm25 = (data[12] << 8) | data[13]
        pm10 = (data[14] << 8) | data[15]
        return pm1, pm25, pm10

    return None


# ============================================================
# MPU-92xx SETUP (I2C)
# ============================================================

bus = SMBus(1)
MPU_ADDR = 0x68

# Wake up MPU
bus.write_byte_data(MPU_ADDR, 0x6B, 0)

def read_mpu():
    """Read accelerometer and gyro from MPU9265/9250"""
    def read_word(reg):
        high = bus.read_byte_data(MPU_ADDR, reg)
        low = bus.read_byte_data(MPU_ADDR, reg + 1)
        val = (high << 8) + low
        if val > 32767:
            val -= 65536
        return val

    ax = read_word(0x3B) / 16384.0
    ay = read_word(0x3D) / 16384.0
    az = read_word(0x3F) / 16384.0

    gx = read_word(0x43) / 131.0
    gy = read_word(0x45) / 131.0
    gz = read_word(0x47) / 131.0

    return ax, ay, az, gx, gy, gz


# ============================================================
# MQ135 (via ADS1115 ADC)
# ============================================================

# i2c = busio.I2C(board.SCL, board.SDA)
# adc = ADS1115(i2c)
# mq135 = AnalogIn(adc, ADS1115.P0)

# def read_mq135():
#     """Return raw voltage of MQ-135"""
#     voltage = mq135.voltage
#     return round(voltage, 3)


# ============================================================
# DHT11 SENSOR (GPIO)
# ============================================================

dht = adafruit_dht.DHT11(board.D4)     # DHT11 on GPIO 4

def read_dht11():
    try:
        temperature = dht.temperature
        humidity = dht.humidity
        return temperature, humidity
    except:
        return None, None



# ============================================================
# MAIN LOOP
# ============================================================

print("Starting PMS7003 + MPU92xx + MQ135 + DHT11 basic reading test...")
print("Press CTRL+C to stop.\n")

while True:
    # PMS7003
    pms_data = read_pms7003()
    if pms_data:
        pm1, pm25, pm10 = pms_data
    else:
        pm1 = pm25 = pm10 = "N/A"

    # MPU
    ax, ay, az, gx, gy, gz = read_mpu()

    # MQ135
    # mq = read_mq135()

    # DHT11
    temp, hum = read_dht11()

    # DISPLAY
    print("====================================================")
    print(f"PMS7003 → PM1={pm1}, PM2.5={pm25}, PM10={pm10}")
    print(f"MPU9265 → Accel: X={ax:.2f} Y={ay:.2f} Z={az:.2f}")
    print(f"          Gyro : X={gx:.2f} Y={gy:.2f} Z={gz:.2f}")
    # print(f"MQ135    → Gas (raw voltage): {mq} V")
    print(f"DHT11    → Temp: {temp if temp else 'N/A'} °C | Humidity: {hum if hum else 'N/A'} %")
    print("====================================================\n")

    time.sleep(1)
