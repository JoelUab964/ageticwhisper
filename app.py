import os
import whisper
import serial
import time
import serial.tools.list_ports
import unicodedata
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from pydub import AudioSegment
#creamos la aplicacion con flask
app = Flask(__name__)
#habilitamos websockets para la comunicacion en tiempo real con la interfaz
socketio = SocketIO(app, cors_allowed_origins="*")
# Carga el modelo de Whisper
model = None  # El modelo se cargará dinámicamente
# Configuración de carpeta de subida
#defien la carpeta donde se guardan los audios
UPLOAD_FOLDER = "uploads"
#crea una carpeta si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
# Configuración del puerto serial (ajusta el puerto según tu sistema)
ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
#esperamos dos segundos 
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
@app.route('/list_ports', methods=['GET'])
def list_ports():
    ports = serial.tools.list_ports.comports()
    port_list = [port.device for port in ports]
    return jsonify(port_list)

#creamos una ruta para devolver modelos disponibles 
@app.route('/list_models', methods=['GET'])
def list_models():
    # Lista estática de modelos disponibles
    return jsonify(["tiny", "base", "small", "medium", "large"])

#ruta para configurar el modelo
@app.route('/set_model', methods=['POST'])
def set_model():
    global model
    data = request.get_json()
    selected_model = data.get("model")
    try:
        model = whisper.load_model(selected_model)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# Función para convertir texto en Braille
def convert_to_braille(text):
    normalized = normalize_text(text.lower())
    #creamos una lista vacia para almacenar la conversion a braile
    braille_translation = []
    #convertir el texto recibido a minusculas  y recorremos todos los caracteres del texto
    for char in normalized:
        if char in braille_dict:
            braille_translation.append(braille_dict[char])
    return braille_translation

# Función para enviar los datos a Arduino
#recibimos una lista con la traduccion a braile
def send_to_arduino(braille_data):
    #recorremos cada letra convertida en braile
    for letter in braille_data:
        #convertimos la lista de numeros en string
        command = ",".join(map(str, letter))  # Convertir lista a cadena "1,0,1,0,0,0"
        #enviamos string a arduino
        ser.write((command + "\n").encode())  # Enviar por Serial
        time.sleep(4.5)  # Esperar 1 segundo entre letras

def normalize_text(text):
    # Elimina acentos y caracteres especiales, dejando solo letras básicas
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

@app.route('/')
def index():
    return render_template("index.html")

#recibimos archivos de audio
@app.route('/upload', methods=['POST'])
def upload_audio():
    start_time = time.time() #inicio del temporizador
    #verificamo si hay un archivo en la solicitud
    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
    #obtenemos el archivo y verificamo si tiene un nombre valido
    file = request.files["file"]
    #verificamos si el nombre esta vacio
    if file.filename == "":
        return jsonify({"error": "Nombre de archivo inválido"}), 400
    #guardamos el archivo en la carpeta upload
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    #calcular la duracion del audio
    audio = AudioSegment.from_file(filepath)
    duration_sec = round(len(audio) / 1000, 2)  # duración en segundos

    # Transcribir con Whisper
    result = model.transcribe(filepath)
    transcription = result["text"]

    # Convertir a Braille
    braille_data = convert_to_braille(transcription)

    # Enviar a Arduino
    send_to_arduino(braille_data)
    elapsed_time = time.time() - start_time  # ⏱️ Tiempo total
    return jsonify({
        "message": "Transcripción enviada a Arduino",
        "transcription": transcription,
        "processing_time": round(elapsed_time, 2),
        "audio_duration": duration_sec
    })
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
