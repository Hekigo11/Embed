import cv2
# from signal import pause
from time import sleep
import threading
import time

try: 
    from gpiozero import LED
    from gpiozero import Buzzer
    buzzer = Buzzer(17)
    led1 = LED(23)
    led2 = LED(24)
    led3 = LED(25)
    leds = [led1, led2, led3]
except ImportError:
    print("gpiozero not available, nasa pc muna")

    class TestBuzzer:
        def on(self): print("Buzzer ON")
        def off(self): print("Buzzer OFF")

    class TestLED:
        def __init__(self, name):
            self.name = name
        def on(self): print(f"{self.name} ON")
        def off(self): print(f"{self.name} OFF")

    # Create 3 fake LEDs to mimic real hardware
    led1 = TestLED("LED1")
    led2 = TestLED("LED2")
    led3 = TestLED("LED3")
    leds = [led1, led2, led3]

    buzzer = TestBuzzer()

def beep_times(count, buzzer):
    def run():
        for _ in range(count):
            buzzer.on()
            time.sleep(1)
            buzzer.off()
            time.sleep(1)
    threading.Thread(target=run, daemon=True).start()


cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(cascade_path)
if face_cascade.empty():
    raise RuntimeError(f"Failed to load cascade at {cascade_path}")
    
cap  = cv2.VideoCapture(0)
if not cap.isOpened():
    raise RuntimeError("Cannot open webcam")

last_beep_time = 0
beep_interval = 1

# VOID LOOP ==================================================================
while True:
    ret, frame = cap.read()
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30,30))
    face_count = len(faces)
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    if face_count > 0:
        print(f"{face_count} face(s) detected")

        
        for led in leds:
            led.off()

       
        for i in range(min(face_count, len(leds))):
            leds[i].on()

        for j in range(face_count):
            buzzer.on()
            time.sleep(0.2)
            buzzer.off()
            time.sleep(0.2)
            time.sleep(1)
        # beep_times(face_count, buzzer)
        # current_time = time.time()
        # if current_time - last_beep_time >= beep_interval:
        #     beep_times(face_count, buzzer)
        #     last_beep_time = current_time

        # sleep(1)

        
    cv2.imshow('Webcam', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()