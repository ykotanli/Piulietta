from flask import Flask, render_template, Response, jsonify, request
from picamera2 import Picamera2
import cv2, time, threading, logging
import RPi.GPIO as GPIO
from gps import start_gps_thread, gps_data

app = Flask(__name__)

picam2 = None
camera_lock = threading.Lock()

def init_camera():
    global picam2
    with camera_lock:
        if picam2 is None:
            try:
                picam2 = Picamera2()
                picam2.configure(picam2.create_preview_configuration())
                picam2.start()
                print("Kamera başlatıldı")
            except Exception as e:
                print(f"Kamera hatası: {e}")
                picam2 = None
    return picam2

def generate_frames():
    global picam2
    if picam2 is None:
        init_camera()
    while True:
        with camera_lock:
            if picam2 is None:
                time.sleep(1)
                continue
            frame = picam2.capture_array()
        jpg = cv2.imencode(
            '.jpg',
            cv2.rotate(
                cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                cv2.ROTATE_180
            )
        )[1].tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
        time.sleep(0.05)

logging.basicConfig(level=logging.INFO)

motorENApin, motorIN1pin, motorIN2pin = 23, 4, 17
motorIN3pin, motorIN4pin, motorENBpin = 27, 22, 24
buzzerPin = 25

TRIG_PIN = 19
ECHO_PIN = 26

GPIO.setmode(GPIO.BCM)
for p in (motorENApin, motorIN1pin, motorIN2pin,
          motorIN3pin, motorIN4pin, motorENBpin,
          buzzerPin, TRIG_PIN):
    GPIO.setup(p, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

pwmENA = GPIO.PWM(motorENApin, 500)
pwmENB = GPIO.PWM(motorENBpin, 500)
pwmENA.start(0)
pwmENB.start(0)

current_command = 'stop'

def motorSurucu(ena, in1, in2, in3, in4, enb):
    pwmENA.ChangeDutyCycle(ena)
    pwmENB.ChangeDutyCycle(enb)
    GPIO.output(motorIN1pin, in1)
    GPIO.output(motorIN2pin, in2)
    GPIO.output(motorIN3pin, in3)
    GPIO.output(motorIN4pin, in4)

def test_motor(cmd):
    global current_command
    ok = True
    if   cmd == "forward":
        motorSurucu(40, True, False, True, False, 40)
    elif cmd == "backward":
        motorSurucu(40, False, True, False, True, 40)
    elif cmd == "left":
        motorSurucu(40, False, True, True, False, 40)
    elif cmd == "right":
        motorSurucu(40, True, False, False, True, 40)
    elif cmd == "stop":
        motorSurucu(0, False, False, False, False, 0)
    else:
        ok = False

    if ok:
        current_command = cmd
    return ok

def measure_distance():
    GPIO.output(TRIG_PIN, False)
    time.sleep(0.05)
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, False)

    start = time.time()
    while GPIO.input(ECHO_PIN) == 0 and time.time() - start < 0.05:
        pass
    t0 = time.time()
    while GPIO.input(ECHO_PIN) == 1 and time.time() - t0 < 0.05:
        pass

    pulse = time.time() - t0
    return round(pulse * 17150, 2)

def obstacle_avoidance():
    while True:
        dist = measure_distance()
        if current_command != 'stop' and dist < 30:
            logging.warning(f"Engel {dist} cm! Kaçış manevrası başlıyor.")
            test_motor("right")
            time.sleep(0.5)
            test_motor("forward")
        time.sleep(0.01)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/send_command', methods=['POST'])
def send_command():
    data = request.get_json()
    cmd  = data.get('command','').strip()
    if not cmd:
        return jsonify(status='error', message='Komut boş'), 400
    if test_motor(cmd):
        return jsonify(status='success', message=f"Komut: {cmd}")
    else:
        return jsonify(status='error', message='Geçersiz komut'), 400

@app.route('/gps_data')
def get_gps_data():
    return jsonify(gps_data)

if __name__ == "__main__":
    try:
        start_gps_thread()
        init_camera()
        threading.Thread(target=obstacle_avoidance, daemon=True).start()
        app.run(host='0.0.0.0', port=5000, threaded=True)
    finally:
        with camera_lock:
            if picam2:
                picam2.stop()
        GPIO.cleanup()
