FROM python:3.9.5-alpine3.13

WORKDIR /app

RUN apk update && \
    apk add --no-cache \
        vim \
        build-base \
        libzmq \
        musl-dev \
        python3 \
        python3-dev \
        zeromq-dev && \
    rm -rf /var/cache/apk/*

COPY requirements.txt /app

RUN pip3 install -r requirements.txt && \
  rm requirements.txt

# NOTE: copying code for all 3 services into each container
COPY src/ /app/
