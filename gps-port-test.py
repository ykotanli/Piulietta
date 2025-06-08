import serial
from datetime import datetime

ser = serial.Serial('/dev/ttyACM0', baudrate=9600, timeout=1)
with open('nmea_raw.log', 'a') as f:
    while True:
        line = ser.readline()
        if not line:
            continue
        entry = f"{datetime.utcnow().isoformat()}  {line.decode('ascii', errors='ignore').strip()}\n"
        f.write(entry)
        f.flush()
        print(entry, end='')
