from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify
import os
import uuid
import time
from threading import Thread, Lock
from queue import Queue

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Esta lista contendrá los archivos subidos con sus tiempos de expiración
uploaded_files = []
pending_files = []
upload_queue = Queue()
upload_lock = Lock()

def delete_expired_files():
    while True:
        current_time = time.time()
        for file in uploaded_files[:]:
            if current_time > file['expiration']:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], file['filename']))
                except:
                    pass
                uploaded_files.remove(file)
        time.sleep(60)

def process_uploads():
    while True:
        if not upload_queue.empty():
            file_info = upload_queue.get()
            filename = file_info['filename']
            file_content = file_info['content']
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with upload_lock:
                with open(file_path, 'wb') as f:
                    f.write(file_content)
            uploaded_files.append({'filename': filename, 'expiration': time.time() + 3600})
            pending_files.remove(filename)
        time.sleep(1)

# Hilos para la eliminación de archivos caducados y procesamiento de subidas
delete_thread = Thread(target=delete_expired_files)
delete_thread.start()

upload_thread = Thread(target=process_uploads)
upload_thread.start()

@app.route('/')
def index():
    # Filtramos los archivos para asegurarnos de no mostrar los que ya han expirado
    current_time = time.time()
    visible_files = [file for file in uploaded_files if current_time < file['expiration']]
    return render_template('index.html', files=visible_files, pending_files=pending_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file:
        filename = f"{uuid.uuid4()}_{file.filename}"
        pending_files.append(filename)
        file_content = file.read()
        upload_queue.put({'filename': filename, 'content': file_content})
        return jsonify({'success': True}), 200

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
