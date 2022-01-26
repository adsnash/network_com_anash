# README

## The Challenge

Create 2 independent processes A & B cabable of sending a file through 2 different methods. Process A must be able to send a CAD file, `cad_mesh.stl` to process B. Process B must then return the file to process A, where it will be saved as `output.stl`. The two files must match. For bonus points, have process B extract the CAD file's vertices, round them to 4 sig figs, and save them in a `CSV` file, called `output.csv`. 

Read the full assignent here: https://github.com/Machina-Labs/network_com_hw

## The Solution

For semantic's sake, process A = `router` and process B = `dealer`. 

I knew right away I'd be using Docker. I prefer Alpine images for their reduced size. Since the services are all so similar, I used a single dockerfile to create all three services (and copied the files for all three into each container). I also volume-mapped a directory (with the name of the service) into each service, as well as a `send` directory into the `router` service.

I used ZeroMQ (ZMQ) as the primary message-passing system - all communication referenced can be assumed to use ZMQ unless explictly stated otherwise. I also used a `flask` intermediary service to provide a second method of file transfer. 

The `router` service watches the `send` directory for new files. Whenever it gets one, it tells the `dealer` service a new file had arrived (as well as its name), and the `dealer` opens a new file and tells `router` its ready. The `router` then sends the file in chunks to the `dealer`. Once the full file has been received, the `dealer` saves it to the `dealer` directory and uploads it to the `flask` service via requests. The `flask` service saves the file in the `flask` directory. It then checks the files extension; if the file is a CAD file with an `STL` extension, it also extracts the CAD file's vertices with `meshio`, rounds them to 4 sig figs, and saves them in an `output.csv` file, which it also uploads to flask via requests. After a file has been uploaded by the `dealer`, it tells the `router` (and provides the file's name), and the router downloads the file from `flask` with requests and saves it in the `router` directory. At this point, the file has made a round trip from the `router` and back.

## Testing

### Requirements

The only requirements to test are Docker, docker-compose, and a bit of terminal knowledge. 

To ensure the volume-mapped directories will exist, you should create them:

```bash
mkdir send && \
mkdir router && \
mkdir dealer && \
mkdir flask 
```

### Docker Setup

An introduction to Docker is beyond the scope of this README. However I will provide the basic commands provided to run things. 

I prefer to run things in detached mode. Logs must be explictly queried with `docker logs <service>` and the terminal that brings everything up can be closed without consequence. If you prefer to watch the logs in real time, simply remove the `-d` flag. 

To bring up the services (in detached mode), from within this directory, run:

```bash
docker-compose build && \
docker-compose up -d
```

NOTE: this first time you build it will take some time, but after that you won't have to build it again (unless you change something).

You can check that the services are up by running:

```bash
docker ps -a
```

The output should look something like this:

```
CONTAINER ID   IMAGE                  COMMAND                  CREATED         STATUS         PORTS                    NAMES
86677b15527f   machina_router         "python3 -u router.py"   5 seconds ago   Up 4 seconds   0.0.0.0:6000->6000/tcp   router
827cca20e422   machina_dealer         "python3 -u dealer.py"   5 seconds ago   Up 4 seconds   0.0.0.0:7000->7000/tcp   dealer
cf0f946cba42   machina_flask          "python3 -u flask_se…"   5 seconds ago   Up 4 seconds   0.0.0.0:5000->5000/tcp   flask
```

The services are named `router`, `dealer`, and `flask` - you can get the logs of any of them, at any time, by running these commands:

```bash
# get logs for router service
docker logs router

# get logs for dealer service
docker logs dealer

# get logs for flask service
docker logs flask
```

When you are done, you can bring everything down with:

```bash
docker-compose down
```

### Testing the Services

To test the services, simply move/copy the `cad_mesh.stl` (or any other file) into the `send` directory to trigger the pipeline, like so: 

```bash
cp cad_mesh.stl send/
``` 

You can check the logs of each service and ensure the output file in the `router` directory are the same with: 

```bash
diff cad_mesh.stl router/output.stl
```

You will also find the `output.csv` file there. If you want to send it again, be sure to clear out all of the volume-mapped folders first so you can ensure it all ran!

## Potential Improvments

- The `flask` service is not secured - it will allow uploads/downloads from anyone who can reach it. Since it runs locally in Docker, that is not really a concern, but if it were deployed and available on the internet, it very much would be

- None of the services are threaded - this would drastically improve file transfer time, especially for larg files

- Use one dockerfile per service to cut down on size

- The flask service does not have any frontend code and could do with a UI

- A step could be added to both the `dealer` and `router` to ensure they can reach `flask` before proceeding

- Adding timing would highlight the slow parts

## Sources

#### ZMQ Sources
https://zguide.zeromq.org/docs/chapter1/
https://zguide.zeromq.org/docs/chapter7/#Transferring-Files
https://github.com/booksbyus/zguide/blob/master/examples/Python/zhelpers.py
https://stackoverflow.com/questions/47438718/zeromq-req-recv-hangs-with-messages-larger-than-1kb-if-run-inside-docker

#### Writing Files
https://www.daniweb.com/programming/software-development/code/418239/write-an-output-file-by-fixed-length-chunks
https://www.blopig.com/blog/2016/08/processing-large-files-using-python/
https://thepythonguru.com/python-how-to-read-and-write-files/

#### Flask Sources
https://flask.palletsprojects.com/en/2.0.x/patterns/fileuploads/
https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests

#### Meshio Docs
https://github.com/nschloe/meshio
