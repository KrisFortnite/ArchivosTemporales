from flask import Flask, request, render_template, send_from_directory, jsonify
import os
import uuid
import time
from threading import Thread, Lock
from queue import Queue
import psutil

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CHUNK_SIZE = 1024 * 1024  # 1 MB

# Límites de recursos (70% del total)
MAX_RAM_USAGE = 0.7 * 528 * 1024 * 1024  # 70% de 528 MB en bytes
MAX_CPU_USAGE = 0.7 * 0.1  # 70% de 0.1 CPU
# Cálculo exacto: 70% de 0.1 es 0.07
MAX_CPU_USAGE = 0.07

uploaded_files = []
pending_files = []
upload_queue = Queue(maxsize=5)  # Limitar la cola a 5 elementos
upload_lock = Lock()

def get_system_usage():
    ram_usage = psutil.virtual_memory().used
    cpu_usage = psutil.cpu_percent(interval=1) / 100.0
    return ram_usage, cpu_usage

def delete_expired_files():
    while True:
        current_time = time.time()
        with upload_lock:
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
            ram_usage, cpu_usage = get_system_usage()
            if ram_usage < MAX_RAM_USAGE and cpu_usage < MAX_CPU_USAGE:
                file_info = upload_queue.get()
                filename = file_info['filename']
                
                with upload_lock:
                    uploaded_files.append({'filename': filename, 'expiration': time.time() + 3600})
                pending_files.remove(os.path.splitext(filename)[0])
            else:
                time.sleep(5)  # Esperar si los recursos están sobrecargados
        time.sleep(1)

delete_thread = Thread(target=delete_expired_files)
delete_thread.daemon = True
delete_thread.start()

upload_thread = Thread(target=process_uploads)
upload_thread.daemon = True
upload_thread.start()

@app.route('/')
def index():
    current_time = time.time()
    with upload_lock:
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
        ram_usage, cpu_usage = get_system_usage()
        if ram_usage >= MAX_RAM_USAGE or cpu_usage >= MAX_CPU_USAGE:
            return jsonify({'error': 'System resources are currently overloaded. Please try again later.'}), 503
        
        filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pending_files.append(os.path.splitext(filename)[0])
        
        try:
            with open(file_path, 'wb') as f:
                chunk = file.read(CHUNK_SIZE)
                while chunk:
                    f.write(chunk)
                    chunk = file.read(CHUNK_SIZE)
            
            upload_queue.put({'filename': filename}, block=False)
            return jsonify({'success': True}), 200
        except Queue.Full:
            os.remove(file_path)
            pending_files.remove(os.path.splitext(filename)[0])
            return jsonify({'error': 'Upload queue is full. Please try again later.'}), 503

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True, processes=1)
