MicroPython for NB2211 *Electronic Instrumentation*
===========

Adapted for the course by: Tijmen de Wolf and Thijn Hoekstra

MicroPython
------------
All this is made possible by the MicroPython project. MicroPython is an open-source project and welcomes contributions. To be
productive, please be sure to follow the
[Contributors' Guidelines](https://github.com/micropython/micropython/wiki/ContributorGuidelines)
and the [Code Conventions](https://github.com/micropython/micropython/blob/master/CODECONVENTIONS.md).
Note that MicroPython is licenced under the MIT license, and all contributions
should follow this license.

About this repository
---------------------

This repository contains the following components:
- [py/](py/) -- the core Python implementation, including compiler, runtime, and
  core library.
- [mpy-cross/](mpy-cross/) -- the MicroPython cross-compiler which is used to turn scripts
  into precompiled bytecode.
- [ports/](ports/) -- platform-specific code for the various ports and architectures that MicroPython runs on.
- [lib/](lib/) -- submodules for external dependencies.
- [tests/](tests/) -- test framework and test scripts.
- [docs/](docs/) -- user documentation in Sphinx reStructuredText format. This is used to generate the [online documentation](http://docs.micropython.org).
- [extmod/](extmod/) -- additional (non-core) modules implemented in C.
- [tools/](tools/) -- various tools, including the pyboard.py module.
- [examples/](examples/) -- a few example Python scripts.

"make" is used to build the components, or "gmake" on BSD-based systems.
You will also need bash, gcc, and Python 3.3+ available as the command `python3`
(if your system only has Python 2.7 then invoke make with the additional option
`PYTHON=python2`). Some ports (rp2 and esp32) additionally use CMake.

Supported platforms & architectures
-----------------------------------

MicroPython runs on a wide range of microcontrollers, as well as on Unix-like
(including Linux, BSD, macOS, WSL) and Windows systems.

Microcontroller targets can be as small as 256kiB flash + 16kiB RAM, although
devices with at least 512kiB flash + 128kiB RAM allow a much more
full-featured experience.

The [Unix](ports/unix) and [Windows](ports/windows) ports allow both
development and testing of MicroPython itself, as well as providing
lightweight alternative to CPython on these platforms (in particular on
embedded Linux systems).

The ["minimal"](ports/minimal) port provides an example of a very basic
MicroPython port and can be compiled as both a standalone Linux binary as
well as for ARM Cortex M4. Start with this if you want to port MicroPython to
another microcontroller. Additionally the ["bare-arm"](ports/bare-arm) port
is an example of the absolute minimum configuration, and is used to keep
track of the code size of the core runtime and VM.

In addition, the following ports are provided in this repository:
 - [cc3200](ports/cc3200) -- Texas Instruments CC3200 (including PyCom WiPy).
 - [esp32](ports/esp32) -- Espressif ESP32 SoC (including ESP32S2, ESP32S3, ESP32C3).
 - [esp8266](ports/esp8266) -- Espressif ESP8266 SoC.
 - [mimxrt](ports/mimxrt) -- NXP m.iMX RT (including Teensy 4.x).
 - [nrf](ports/nrf) -- Nordic Semiconductor nRF51 and nRF52.
 - [pic16bit](ports/pic16bit) -- Microchip PIC 16-bit.
 - [powerpc](ports/powerpc) -- IBM PowerPC (including Microwatt)
 - [qemu-arm](ports/qemu-arm) -- QEMU-based emulated target, for testing)
 - [renesas-ra](ports/renesas-ra) -- Renesas RA family.
 - [rp2](ports/rp2) -- Raspberry Pi RP2040 (including Pico and Pico W).
 - [samd](ports/samd) -- Microchip (formerly Atmel) SAMD21 and SAMD51.
 - [stm32](ports/stm32) -- STMicroelectronics STM32 family (including F0, F4, F7, G0, G4, H7, L0, L4, WB)
 - [webassembly](ports/webassembly) -- Emscripten port targeting browsers and NodeJS.
 - [zephyr](ports/zephyr) -- Zephyr RTOS.

The MicroPython cross-compiler, mpy-cross
-----------------------------------------

Most ports require the [MicroPython cross-compiler](mpy-cross) to be built
first.  This program, called mpy-cross, is used to pre-compile Python scripts
to .mpy files which can then be included (frozen) into the
firmware/executable for a port.  To build mpy-cross use:

    $ cd mpy-cross
    $ make

External dependencies
---------------------

The core MicroPython VM and runtime has no external dependencies, but a given
port might depend on third-party drivers or vendor HALs. This repository
includes [several submodules](lib/) linking to these external dependencies.
Before compiling a given port, use

    $ cd ports/name
    $ make submodules

to ensure that all required submodules are initialised.


Building from source
--------------------

To build the RP2040 MicroPython port, you’ll need to install some extra tools. To build projects you’ll need CMake, a
cross-platform tool used to build the software, and the GNU Embedded Toolchain for Arm, which turns MicroPython’s C
source code into a binary program RP2040’s processors can understand. `build-essential` is a bundle of tools you need
to build code native to your own machine — this is needed for some internal tools in MicroPython and the SDK. You can
install all of these via `apt` from the command line. Anything you already have installed will be ignored by `apt`

Linux:
```shell
sudo apt update
sudo apt install cmake gcc-arm-none-eabi libnewlib-arm-none-eabi build-essential
```

Macos
```shell
brew update
brew install cmake
xcode-select --install
```

Install `gcc-arm-none-eabi`
https://developer.arm.com/downloads/-/gnu-rm

Add to PATH
```shell
sudo nano /etc/paths
```
For example the path could be: /Applications/ARM/bin

The /etc/paths file is a list of paths to search. It should now look something like:
```
/usr/local/bin
/System/Cryptexes/App/usr/bin
/usr/bin
/bin
/usr/sbin
/sbin
/Applications/ARM/bin
```


```bash
git clone https://github.com/twhoekstra/nb2211-micropython.git
cd nb2211-micropython/
```

The MicroPython repository also contains pointers (submodules) to specific 
versions of libraries it needs to run on a
particular board, like the SDK in the case of RP2040. We need to fetch these submodules too

```bash
make -C ports/rp2 submodules
```

Fetch ulab submodule.
```bash
git submodule update --init lib/ulab
```

First we need to bootstrap a special tool for MicroPython builds, that ships with the source code:

```bash
make -C mpy-cross
```

We can now build the port we need for RP2040, that is, the version of MicroPython that has specific support for our
chip.

```bash
cd ports/rp2
make USER_C_MODULES=../../lib/ulab/code/micropython.cmake
```
