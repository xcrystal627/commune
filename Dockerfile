

FROM ubuntu:22.10
SHELL ["/bin/bash", "-c"]
# syntax=docker/dockerfile:1
WORKDIR /commune
RUN rm -f /etc/apt/sources.list.d/*.list
ARG DEBIAN_FRONTEND=noninteractive
# INSTALL APT PACKAGES
RUN apt update && apt upgrade -y
RUN apt install -y curl sudo nano git htop netcat wget unzip python3-dev python3-pip tmux apt-utils cmake build-essential protobuf-compiler


#  INSTALL PYTHON PACKAGES
COPY ./commune /commune/commune
COPY ./requirements.txt /commune/requirements.txt
COPY ./setup.py /commune/setup.py
COPY ./README.md /commune/README.md
COPY ./bin /commune/bin

RUN pip3 install -e .

# INTSALL NPM PACKAGES
RUN ./scripts/install_npm_env.sh

# # BUILD SUBDSPACE (BLOCKCHAIN)
# COPY ./subspace /commune/subspace
# # Necessary libraries for Rust execution
# RUN apt-get update && apt-get install -y clang 
# ENV PATH="/root/.cargo/bin:${PATH}"
# RUN cd /commune/subspace && ./scripts/install_rust_env.sh
# RUN cd /commune/subspace && cargo build --release --locked

