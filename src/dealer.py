# PROCESS B: dealer - receives files, parses stl files, uploads to flask

import os
import csv
import sys
import zmq
import time
import meshio
import requests


# size of chunks for writing, default to 256 MB
CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', 256 * 1024))
# max pipeline chunks in transit, default to 10
PIPELINE = int(os.environ.get('PIPELINE', 10))

# volume-mapped directory where files will be served from
SAVE_DIR = os.environ.get('DEALER_DIR')

# endpoint where flask can be reached
# locally with docker, that is flask container name
FLASK_ENDPOINT = os.environ.get('FLASK_ENDPOINT')
# port flask service is availabe at
FLASK_PORT = int(os.environ.get('FLASK_PORT'))
# base url to reach flask
FLASK_BASE_URL = f'http://{FLASK_ENDPOINT}:{FLASK_PORT}'

# port ZMQ router is available at
ZMQ_PORT=os.environ.get('ZMQ_ROUTER_PORT')
# endpoint where ZMQ router is available at
ZMQ_ENDPOINT=os.environ.get('ZMQ_ROUTER_ENDPOINT')
# setup ZMQ socket
ctx = zmq.Context()
dealer = ctx.socket(zmq.DEALER)
dealer.connect(f'tcp://{ZMQ_ENDPOINT}:{ZMQ_PORT}')


# get files with ZMQ
def zmq_get_file(file_name):
    credit = PIPELINE  # up to PIPELINE chunks in transit
    total = 0          # total bytes received
    chunks = 0         # chunks received
    offset = 0         # offset for next chunk

    out_file = open(os.path.join(SAVE_DIR, file_name), 'wb')

    while True:
        while credit:
            # ask for next chunk
            dealer.send_multipart([
                b'fetch',
                str.encode(str(offset)),
                str.encode(str(CHUNK_SIZE))
            ])

            offset += CHUNK_SIZE
            credit -= 1

        try:
            chunk = dealer.recv()
            out_file.write(chunk)
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                return
            else:
                raise

        chunks += 1
        credit += 1
        size = len(chunk)
        total += size

        if size < CHUNK_SIZE:
            out_file.close()
            print(f'File {file_name} written to disk - {chunks} chunks and {total} bytes')
            return


# parse STL file, extract vertices, and save as CSV with 4 sig figs
def parse_stl(file_name, save_name='output.csv'):
    in_cad = meshio.read(os.path.join(SAVE_DIR, file_name))

    # write file to disk
    with open(os.path.join(SAVE_DIR, save_name), 'w', newline='') as out_csv:
        writer = csv.writer(out_csv)
        for point in in_cad.points:
            # round to 4 sigfigs for each point
            writer.writerow([point[0].round(4), point[1].round(4), point[2].round(4)])

    print(f'STL file {file_name} converted to CSV and saved as {save_name}')
    return save_name


# upload file to flask
def upload_flask(file_name):
    print(f'Uploading {file_name} to flask')
    with open(os.path.join(SAVE_DIR, file_name), 'rb') as f:
        file = {'upload_file': f}
        response = requests.post(f'{FLASK_BASE_URL}/upload', files=file)
        response.raise_for_status()
        print('File uploaded successfully')
    return


def main():
    print('Starting up dealer')
    connected = False  # whether connection has been made 
    attempts = 10      # attempts to connect 
    command = None     # most recent command 

    # send initial connect for router to track identity
    dealer.send(b"connect")

    while True:
        try:
            msg = dealer.recv_multipart()
            # print(f'msg: {msg}')
            command = msg[0]
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                print('Exiting')
                sys.exit()
            else:
                raise

        if command:
            if command == b'established':
                command = None
                print('Connection established with router')
                connected = True

            elif command == b'new_file':
                command = None
                print(f'New file message received with ZMQ, will save to disk')
                new_file = msg[1].decode()
                # get file via zmq
                zmq_get_file(new_file)
                # upload file to flask
                upload_flask(new_file)
                # notify that file is ready for download
                dealer.send_multipart([b"download", str.encode(new_file)])

                # if file was STL, convert to CSV
                if new_file.split('.')[-1].lower() == 'stl':
                    print('STL file received, converting to CSV')
                    # convert stl to csv 
                    # TODO: use file name with CSV ext unless name matches that of hw
                    csv_name = parse_stl(new_file, ) 
                    # upload file to flask
                    upload_flask(csv_name)
                    # notify that file is ready for download
                    dealer.send_multipart([b"download", str.encode(csv_name)])

        # try to connect again if connection has not been established
        if not connected:
            print('Attempting to connect again')
            dealer.send(b"connect")
            attempts -= 1
            # disconnect if too many failed tries
            if attempts == 0:
                print('Failed to connect, shutting down')
                sys.exit()


if __name__ == '__main__':
    main()
