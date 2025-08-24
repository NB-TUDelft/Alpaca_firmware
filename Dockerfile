FROM python:bookworm

ARG DEBIAN_FRONTEND=noninteractive

# Install toolchain and build tools needed to build MicroPython for RP2040 (Raspberry Pi Pico)
RUN apt update -qy \
    && apt install -qfy \
    bash \
    build-essential \
    ca-certificates \
    cmake \
    gcc-arm-none-eabi \
    git \
    libnewlib-arm-none-eabi \
    ninja-build \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# Print versions for debugging during docker build
RUN cmake --version && arm-none-eabi-gcc --version && make --version