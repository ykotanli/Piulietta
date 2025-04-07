from flask import Flask, render_template, Response, jsonify, request
from picamera2 import Picamera2
import cv2
import numpy as np
import time
import threading
import RPi.GPIO as GPIO
import logging

app = Flask(__name__)

# ---------------- KAMERA AYARLARI ---------------- #
picam2 = None
camera_lock = threading.Lock()

def init_camera():
    global picam2
    with camera_lock:
        if picam2 is None:
            try:
                picam2 = Picamera2()
                config = picam2.create_preview_configuration()
                picam2.configure(config)
                picam2.start()
                print("Kamera başarıyla başlatıldı!")
            except Exception as e:
                print(f"Kamera başlatma hatası: {str(e)}")
                picam2 = None
    return picam2

def generate_frames():
    global picam2
    if picam2 is None:
        picam2 = init_camera()
        if picam2 is None:
            time.sleep(2)
            picam2 = init_camera()

    while True:
        try:
            with camera_lock:
                if picam2 is None:
                    picam2 = init_camera()
                    if picam2 is None:
                        time.sleep(2)
                        continue

                frame = picam2.capture_array()
            
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            frame_bgr = cv2.rotate(frame_bgr, cv2.ROTATE_180)
            ret, buffer = cv2.imencode('.jpg', frame_bgr)
            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            time.sleep(0.05)
        except Exception as e:
            print(f"Görüntü alma hatası: {str(e)}")
            time.sleep(1)

# ---------------- MOTOR AYARLARI ---------------- #
logging.basicConfig(level=logging.INFO)

# Pin tanımlamaları
motorENApin = 23
motorIN1pin = 4
motorIN2pin = 17
motorIN3pin = 27
motorIN4pin = 22
motorENBpin = 24
buzzerPin = 25

# GPIO ayarı
GPIO.setmode(GPIO.BCM)
GPIO.setup(motorENApin, GPIO.OUT)
GPIO.setup(motorIN1pin, GPIO.OUT)
GPIO.setup(motorIN2pin, GPIO.OUT)
GPIO.setup(motorIN3pin, GPIO.OUT)
GPIO.setup(motorIN4pin, GPIO.OUT)
GPIO.setup(motorENBpin, GPIO.OUT)
GPIO.setup(buzzerPin, GPIO.OUT)

# PWM ayarı
pwmENA = GPIO.PWM(motorENApin, 500)
pwmENB = GPIO.PWM(motorENBpin, 500)

pwmENA.start(0)
pwmENB.start(0)

def motorSurucu(ena, in1, in2, in3, in4, enb):
    pwmENA.ChangeDutyCycle(ena)
    pwmENB.ChangeDutyCycle(enb)
    
    GPIO.output(motorIN1pin, in1)
    GPIO.output(motorIN2pin, in2)
    GPIO.output(motorIN3pin, in3)
    GPIO.output(motorIN4pin, in4)

def test_motor(command):
    if command == "forward":
        motorSurucu(70, True, False, True, False, 70)
    elif command == "backward":
        motorSurucu(70, False, True, False, True, 70)
    elif command == "left":
        motorSurucu(70, False, True, True, False, 70)
    elif command == "right":
        motorSurucu(70, True, False, False, True, 70)
    elif command == "stop":
        motorSurucu(0, False, False, False, False, 0)
    else:
        return False
    return True

# ---------------- FLASK ROUTE'LER ---------------- #
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/send_command', methods=['POST'])
def send_command():
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        logging.info(f"Alınan komut: {command}")

        if not command:
            raise ValueError("Komut boş olamaz")

        if test_motor(command):
            return jsonify({'status': 'success', 'message': f"Komut çalıştırıldı: {command}"})
        else:
            raise ValueError(f"Geçersiz komut: {command}")

    except Exception as e:
        logging.error(f"Komut gönderme hatası: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ---------------- ANA UYGULAMA ---------------- #
if __name__ == '__main__':
    try:
        init_camera()
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    finally:
        with camera_lock:
            if picam2 is not None:
                picam2.stop()
                print("Kamera kapatıldı.")
        GPIO.cleanup()
