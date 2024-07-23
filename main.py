from flask import Flask, request, render_template, send_from_directory, jsonify
import os
import time
from threading import Timer

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear carpeta de subidas si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Mantener un diccionario con los archivos y sus tiempos de subida
uploaded_files = {}

@app.route('/')
def index():
    return render_template('index.html', files=uploaded_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    uploaded_files[file.filename] = time.time()
    # Configurar un temporizador para eliminar el archivo después de una hora
    Timer(3600, delete_file, [file.filename]).start()
    return jsonify({"filename": file.filename}), 200

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def delete_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        del uploaded_files[filename]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
