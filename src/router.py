# PROCESS A: router - sends files, downloads from flask

import os
import sys
import zmq
import time 
import requests


# size of chunks for writing, default to 256 MB
CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', 256 * 1024))
# max pipeline chunks in transit, default to 10
PIPELINE = int(os.environ.get('PIPELINE', 10))

# volume-mapped directory where files will be saved to
SAVE_DIR = os.environ.get('ROUTER_DIR')
# volume-mapped where files will be sent from
SEND_DIR = os.environ.get('SEND_DIR')

# endpoint where flask can be reached
# locally with docker, that is flask container name
FLASK_ENDPOINT = os.environ.get('FLASK_ENDPOINT')
# port flask service is availabe at
FLASK_PORT = int(os.environ.get('FLASK_PORT'))
# base url to reach flask
FLASK_BASE_URL = f'http://{FLASK_ENDPOINT}:{FLASK_PORT}'

# port ZMQ dealer (this service) is available at
ZMQ_PORT=os.environ.get('ZMQ_ROUTER_PORT')
# setup ZMQ socket
ctx = zmq.Context()
router = ctx.socket(zmq.ROUTER)
# set high water mark
# source: https://github.com/booksbyus/zguide/blob/master/examples/Python/zhelpers.py
try:
    router.sndhwm = router.rcvhwm = PIPELINE
except AttributeError:
    router.hwm = PIPELINE
router.bind(f'tcp://*:{ZMQ_PORT}')


# send files with ZMQ
def zmq_send_file(file_name):
    chunks = 0  # chunks sent
    path = os.path.join(SEND_DIR, file_name)

    if os.path.exists(path):
        file = open(path, 'rb')
        print(f'Sending file {file_name} with ZMQ')
    else:
        print(f'Could not find file {file_name}')
        return

    while True:
        try:
            msg = router.recv_multipart()
            # print(f'msg: {msg}')
            identity, command, offset_str, chunksz_str = msg
        except zmq.ZMQError as e:
            if e.errno == zmq.ETERM:
                print('Exiting')
                return
            else:
                raise

        chunks += 1
        offset = int(offset_str)
        chunksz = int(chunksz_str)

        # read chunk from file
        file.seek(offset, os.SEEK_SET)
        data = file.read(chunksz)

        # send chunk
        # print(f'Sending chunk {chunks}')
        router.send_multipart([identity, data])
        
        # close file when finished
        if not data:
            file.close()
            print('File successfully sent')
            return


# attempt to download a file from FLASK_BASE_URL
def download_file(file_name):
    print(f'Attempting to download {file_name} from Flask via requests')
    response = requests.get(f'{FLASK_BASE_URL}/download/{file_name}')
    response.raise_for_status()

    # per requirements, returned file to be called 'output.stl'
    save_name = 'output.stl'
    # get extension to confirm file is 'stl'
    file_ext = file_name.split('.')[-1].lower()
    # if file is not an stl or default file already exists, use file_name
    if file_ext != 'stl' or os.path.exists(os.path.join(SAVE_DIR, save_name)):
        # NOTE: not handling for whether THIS path exists
        save_name = file_name

    # save file to disk
    print(f'Saving file {file_name} as {save_name}')
    with open(os.path.join(SAVE_DIR, save_name), 'wb') as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE): 
            if chunk: 
                f.write(chunk)
    print(f'File saved successfully')


def main():
    print('Starting up router')
    identity = None  # identity of dealer, set from "connect"
    command = None   # most recent command 

    watch_file_ls = [i for i in os.listdir(SEND_DIR) if not i.startswith('.')]
    print(f'{len(watch_file_ls)} initial file(s) in {SEND_DIR}')

    while True:
        try:
            # NOTE: use NOBLOCK so this doesn't hang while waiting for a file
            msg = router.recv_multipart(flags=zmq.NOBLOCK)
            # print(f'msg: {msg}')
            command = msg[1]
        # handle for again error 
        except zmq.error.Again:
            pass

        except Exception as e:
            print(e)
            print(dir(e))

        if command:
            # handle for initial connection 
            if command == b'connect':
                command = None
                identity = msg[0]
                print(f'Received connection message, setting identity = {identity}')
                # let dealer know connection was succesful
                router.send_multipart([identity, b'established'])

            elif command == b'download': 
                command = None
                file_name = msg[2].decode()
                print(f'Received message that {file_name} is ready for download')
                download_file(file_name)

        cur_file_ls = [i for i in os.listdir(SEND_DIR) if not i.startswith('.')]

        if len(cur_file_ls) > len(watch_file_ls):
            print('New file(s) found')
            new_file_ls = [i for i in cur_file_ls if i not in watch_file_ls]

            # TODO: confirm this works if multiple files arrive
            for new_file in new_file_ls:
                # TODO: handle for no identity i.e. no connection established
                if identity is not None:
                    router.send_multipart([identity, b'new_file', str.encode(new_file)])
                    zmq_send_file(new_file)

        watch_file_ls = cur_file_ls


if __name__ == '__main__':
    main()
