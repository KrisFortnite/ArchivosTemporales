from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify
import os
import uuid
import time
from threading import Thread, Lock
import zipfile
import io
import psutil
import requests

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CHUNK_SIZE = 1024 * 1024  # 1 MB

uploaded_files = []
pending_files = []
upload_lock = Lock()

SERVER_RAM_LIMIT = 0.8 * 512 * 1024 * 1024  # 80% of 512 MB in bytes
SERVER_CPU_LIMIT = 0.08  # 80% of 0.1 CPU

CLIENT_RAM_LIMIT = 1.5 * 1024 * 1024 * 1024  # 1.5 GB in bytes
CLIENT_CPU_LIMIT = 0.8  # 20% of CPU

def get_system_resources():
    return {
        'ram_usage': psutil.virtual_memory().used,
        'cpu_usage': psutil.cpu_percent(interval=1) / 100
    }

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
        time.sleep(300)  # Check every 5 minutes to reduce CPU usage

def compress_file(file_path, output_filename):
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_path, os.path.basename(file_path))
    return output_filename

def process_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    resources = get_system_resources()
    if resources['ram_usage'] < SERVER_RAM_LIMIT and resources['cpu_usage'] < SERVER_CPU_LIMIT:
        # Process on server
        compressed_filename = f"{os.path.splitext(filename)[0]}.zip"
        compressed_path = os.path.join(app.config['UPLOAD_FOLDER'], compressed_filename)
        compress_file(file_path, compressed_path)
        os.remove(file_path)
    else:
        # Request client to process
        compressed_filename = f"{os.path.splitext(filename)[0]}.zip"
        compressed_path = os.path.join(app.config['UPLOAD_FOLDER'], compressed_filename)
        client_compress_request(file_path, compressed_path)
    
    with upload_lock:
        uploaded_files.append({'filename': compressed_filename, 'expiration': time.time() + 3600})
    pending_files.remove(os.path.splitext(filename)[0])

def client_compress_request(file_path, compressed_path):
    # This is a placeholder function. In a real-world scenario, you would implement
    # a way to send a request to the client to compress the file and send it back.
    # For demonstration purposes, we'll just compress it on the server.
    compress_file(file_path, compressed_path)
    os.remove(file_path)

delete_thread = Thread(target=delete_expired_files)
delete_thread.daemon = True
delete_thread.start()

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
        filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        pending_files.append(os.path.splitext(filename)[0])
        
        try:
            with open(file_path, 'wb') as f:
                chunk = file.read(CHUNK_SIZE)
                while chunk:
                    resources = get_system_resources()
                    if resources['ram_usage'] >= SERVER_RAM_LIMIT or resources['cpu_usage'] >= SERVER_CPU_LIMIT:
                        time.sleep(1)  # Slow down upload if server resources are constrained
                    f.write(chunk)
                    chunk = file.read(CHUNK_SIZE)
            
            # Process the file in a separate thread to avoid blocking
            Thread(target=process_file, args=(filename,), daemon=True).start()
            return jsonify({'success': True}), 200
        except Exception as e:
            pending_files.remove(os.path.splitext(filename)[0])
            return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
