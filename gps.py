import serial
import threading
import pynmea2
import time

gps_data = {
    'lat': None,
    'lon': None,
    'time': None
}

def gps_reader_loop(port: str = '/dev/ttyACM0', baud: int = 9600):
    """
    Sürekli GPS cihazından NMEA cümlelerini okur ve
gps_data dict'ini günceller.
    port: Seri cihaz yolu (ör. '/dev/ttyACM0')
    baud: İletişim hız değeri (bps)
    """
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1)
        while True:
            line = ser.readline().decode('ascii', errors='ignore').strip()
            if line.startswith(('$GPGGA', '$GPRMC')):
                try:
                    msg = pynmea2.parse(line)
                    gps_data['lat'] = f"{msg.latitude} {msg.lat_dir}"
                    gps_data['lon'] = f"{msg.longitude} {msg.lon_dir}"
                    gps_data['time'] = msg.timestamp.isoformat()
                except pynmea2.ParseError:
                    pass
            time.sleep(0.2)
    except Exception as e:
        print(f"[GPS] Okuma hatası: {e}")
        time.sleep(5)
        gps_reader_loop(port, baud)

def start_gps_thread():
    """
    GPS okuma thread'ini başlatır (daemon olarak).
    """
    thread = threading.Thread(target=gps_reader_loop, daemon=True)
    thread.start()
