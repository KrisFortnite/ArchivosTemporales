from flask import Flask, request, render_template, send_from_directory, jsonify
import os
import time
from threading import Timer

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
CHUNK_FOLDER = 'chunks'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CHUNK_FOLDER'] = CHUNK_FOLDER

# Crear carpetas de subidas y fragmentos si no existen
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(CHUNK_FOLDER):
    os.makedirs(CHUNK_FOLDER)

# Mantener un diccionario con los archivos y sus tiempos de subida
uploaded_files = {}

@app.route('/')
def index():
    return render_template('index.html', files=uploaded_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    filename = request.form['filename']
    chunk_number = int(request.form['chunkNumber'])
    total_chunks = int(request.form['totalChunks'])
    
    chunk_filepath = os.path.join(app.config['CHUNK_FOLDER'], f"{filename}.part{chunk_number}")
    file.save(chunk_filepath)

    if all(os.path.exists(os.path.join(app.config['CHUNK_FOLDER'], f"{filename}.part{i}")) for i in range(total_chunks)):
        with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), 'wb') as output_file:
            for i in range(total_chunks):
                chunk_filepath = os.path.join(app.config['CHUNK_FOLDER'], f"{filename}.part{i}")
                with open(chunk_filepath, 'rb') as chunk_file:
                    output_file.write(chunk_file.read())
                os.remove(chunk_filepath)
        
        uploaded_files[filename] = time.time()
        Timer(3600, delete_file, [filename]).start()
    
    return jsonify({"filename": filename}), 200

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
