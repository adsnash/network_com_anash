# FLASK - intermediary service to upload/download files

import os
from werkzeug.utils import secure_filename
from flask import Flask, request, redirect, url_for, send_from_directory
from werkzeug.datastructures import FileStorage


# port to serve flask at (this service)
FLASK_PORT = int(os.environ.get('FLASK_PORT'))

# directory to save/serve files from
SAVE_DIR = os.environ.get('FLASK_SAVE_DIR', '/app/flask')

# allowed extensions list
ALLOWED_EXTENSIONS = {'stl', 'csv', 'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.secret_key = "super_duper_secret_key"
app.config['UPLOAD_FOLDER'] = SAVE_DIR
app.config['DOWNLOAD_FOLDER'] = SAVE_DIR
app.add_url_rule("/upload/<file_name>", endpoint="up_file", build_only=True)
app.add_url_rule("/download/<file_name>", endpoint="download_file", build_only=True)


# helper to determine if file has an allowed extension 
def _allowed_ext(file_name):
    return file_name.split('.')[-1].lower() in ALLOWED_EXTENSIONS


# basic route to ensure its working
@app.route("/")
def hello_world():
    print('Flask says "Hello, World!"')
    return "<p>Hello, World!</p>"


# @app.route('/upload', methods=['GET', 'POST'])
@app.route('/upload', methods=['POST'])
def upload_file():
    body = request.form
    upload_file = request.files['upload_file']
    print(f'Flask received upload request for {upload_file.filename}')

    # nameless files will fail
    if upload_file.filename == '':
        print('No file selected, returning 400 error')
        return 'No file selected', 400

    if upload_file and _allowed_ext(upload_file.filename):
        # ensure the name is safe
        file_name = secure_filename(upload_file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
        upload_file.save(file_path)
        print(f'File saved at {file_path}')
        return 'OK', 200
    

# download file from volume mapped directory
@app.route('/download/<file_name>', methods=['GET'])
def download_file(file_name):
    print(f'Flask download request for {file_name}')
    return send_from_directory(app.config["UPLOAD_FOLDER"], file_name)


if __name__ == "__main__":
    print('Starting up flask')
    app.run(host='0.0.0.0', port=FLASK_PORT)

