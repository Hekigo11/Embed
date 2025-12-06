import firebase_admin
from firebase_admin import credentials, db
import time

try:
    cred = credentials.Certificate("volcano-monitoring-system-firebase-adminsdk-fbsvc-75eba7d26a.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://volcano-monitoring-system-default-rtdb.asia-southeast1.firebasedatabase.app/'
    })

    ref = db.reference("VolcanoMonitoring/Test")
    ref.set({
        "status": "Lab 9 Infra OK",
        "timestamp": time.time()
    })

    print("Firebase connection successful")

except Exception as e:
    print("Firebase error:", e)
