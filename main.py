from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify
import os
import uuid
import time
from threading import Thread, Lock
import zipfile
import io
import psutil
import requests
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CHUNK_SIZE = 1024 * 1024  # 1 MB

uploaded_files = []
pending_files = []
upload_lock = Lock()
connected_clients = {}

SERVER_RAM_LIMIT = 0.8 * 512 * 1024 * 1024  # 80% of 512 MB in bytes
SERVER_CPU_LIMIT = 0.08  # 80% of 0.1 CPU

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
                    f.write(chunk)
                    chunk = file.read(CHUNK_SIZE)
            
            # Request client to process the file
            socketio.emit('process_file', {'filename': filename}, broadcast=True)
            return jsonify({'success': True}), 200
        except Exception as e:
            pending_files.remove(os.path.splitext(filename)[0])
            return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('connect')
def handle_connect():
    client_id = request.sid
    connected_clients[client_id] = {'processing': False}
    print(f"Client {client_id} connected")

@socketio.on('disconnect')
def handle_disconnect():
    client_id = request.sid
    if client_id in connected_clients:
        del connected_clients[client_id]
    print(f"Client {client_id} disconnected")

@socketio.on('client_ready')
def handle_client_ready(data):
    client_id = request.sid
    connected_clients[client_id]['ram'] = data['ram']
    connected_clients[client_id]['cpu'] = data['cpu']
    assign_task()

def assign_task():
    for client_id, client_info in connected_clients.items():
        if not client_info['processing'] and pending_files:
            filename = pending_files.pop(0)
            client_info['processing'] = True
            socketio.emit('process_file', {'filename': filename}, room=client_id)
            break

@socketio.on('file_processed')
def handle_file_processed(data):
    client_id = request.sid
    filename = data['filename']
    compressed_data = data['compressed_data']
    
    compressed_filename = f"{os.path.splitext(filename)[0]}.zip"
    compressed_path = os.path.join(app.config['UPLOAD_FOLDER'], compressed_filename)
    
    with open(compressed_path, 'wb') as f:
        f.write(compressed_data)
    
    with upload_lock:
        uploaded_files.append({'filename': compressed_filename, 'expiration': time.time() + 3600})
    
    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    connected_clients[client_id]['processing'] = False
    assign_task()

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)
