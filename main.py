from flask import Flask, request, render_template, jsonify
import os
from datetime import datetime, timedelta
import threading

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

files_info = {}

def delete_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    if filename in files_info:
        del files_info[filename]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    filename = file.filename
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    
    expiration_time = datetime.now() + timedelta(hours=1)
    files_info[filename] = {
        'expiration_time': expiration_time,
        'size': os.path.getsize(file_path)
    }
    
    threading.Timer(3600, delete_file, args=[filename]).start()
    
    return jsonify({'message': 'File uploaded successfully'}), 200

@app.route('/files')
def get_files():
    current_time = datetime.now()
    files_list = []
    for filename, info in files_info.items():
        remaining_time = (info['expiration_time'] - current_time).total_seconds()
        if remaining_time > 0:
            files_list.append({
                'name': filename,
                'size': info['size'],
                'remaining_time': int(remaining_time)
            })
    return jsonify(files_list)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
