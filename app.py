import os
import whisper
import serial
import time
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Carga el modelo de Whisper
model = whisper.load_model("small")

# Configuración de carpeta de subida
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Configuración del puerto serial (ajusta el puerto según tu sistema)
ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
time.sleep(2)  # Esperar a que Arduino inicie

# Diccionario de letras a Braille (puntos activos 1 = levantado, 0 = bajado)
braille_dict = {
    "a": [1, 0, 0, 0, 0, 0], "b": [1, 1, 0, 0, 0, 0],
    "c": [1, 0, 0, 1, 0, 0], "d": [1, 0, 0, 1, 1, 0],
    "e": [1, 0, 0, 0, 1, 0], "f": [1, 1, 0, 1, 0, 0],
    "g": [1, 1, 0, 1, 1, 0], "h": [1, 1, 0, 0, 1, 0],
    "i": [0, 1, 0, 1, 0, 0], "j": [0, 1, 0, 1, 1, 0],
    "k": [1, 0, 1, 0, 0, 0], "l": [1, 1, 1, 0, 0, 0],
    "m": [1, 0, 1, 1, 0, 0], "n": [1, 0, 1, 1, 1, 0],
    "o": [1, 0, 1, 0, 1, 0], "p": [1, 1, 1, 1, 0, 0],
    "q": [1, 1, 1, 1, 1, 0], "r": [1, 1, 1, 0, 1, 0],
    "s": [0, 1, 1, 1, 0, 0], "t": [0, 1, 1, 1, 1, 0],
    "u": [1, 0, 1, 0, 0, 1], "v": [1, 1, 1, 0, 0, 1],
    "w": [0, 1, 0, 1, 1, 1], "x": [1, 0, 1, 1, 0, 1],
    "y": [1, 0, 1, 1, 1, 1], "z": [1, 0, 1, 0, 1, 1],
    " ": [0, 0, 0, 0, 0, 0]  # Espacio en blanco
}

# Función para convertir texto en Braille
def convert_to_braille(text):
    braille_translation = []
    for char in text.lower():
        if char in braille_dict:
            braille_translation.append(braille_dict[char])
    return braille_translation

# Función para enviar los datos a Arduino
def send_to_arduino(braille_data):
    for letter in braille_data:
        command = ",".join(map(str, letter))  # Convertir lista a cadena "1,0,1,0,0,0"
        ser.write((command + "\n").encode())  # Enviar por Serial
        time.sleep(1)  # Esperar 1 segundo entre letras

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload_audio():
    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nombre de archivo inválido"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Transcribir con Whisper
    result = model.transcribe(filepath)
    transcription = result["text"]

    # Convertir a Braille
    braille_data = convert_to_braille(transcription)

    # Enviar a Arduino
    send_to_arduino(braille_data)

    return jsonify({"message": "Transcripción enviada a Arduino", "transcription": transcription})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
