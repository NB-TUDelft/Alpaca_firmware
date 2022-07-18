from ulab import numpy as np
import _thread
import utime
from machine import SPI, Pin

# Max voltage the DAC is allowed to produce. Set to 3300 mV in
# to protect against the DAC frying the Pico
MAX_VOLTAGE_TOLERATED = const(3300)

# Max voltage the DAC can  produce.
# Will be used in overdrive mode
MAX_VOLTAGE_OVERDRIVE = const(4096)

# Minimum voltage allowed, set to zero for MCP4822
MIN_VOLTAGE = const(0)

PIN_NO_MOSI = const(11)
PIN_NO_SCK = const(10)
PIN_NO_CS = const(13)
PIN_NO_LDAC = const(12)

# Integer value, that when sent to the DAC over SPI will
# produce the largest voltage. 4096 for the MCP4822
DAC_MAX_INT = const(4096)

# Max voltage the DAC can produce measured in millivolts.
# 4095 for the MCP4822 when the gain has been set to 2.
DAC_MAX_VOLTAGE_GAIN_2 = const(4095)

# Max voltage the DAC can produce measured in millivolts.
# 4095 for the MCP4822 when the gain has been set to 2.
DAC_MAX_VOLTAGE_GAIN_1 = const(2047)

# 114 us write delay, whatever pause we want between
# writes in our program has to be larger than this
T_DAC_DELAY_US = const(100)

SET_BYTE_A1 = const(12288)  # MCP4822 setting byte for DAC A, Gain 1
SET_BYTE_A2 = const(4096)  # MCP4822 setting byte for DAC A, Gain 2
SET_BYTE_B1 = const(45056)  # MCP4822 setting byte for DAC B, Gain 1
SET_BYTE_B2 = const(36864)  # MCP4822 setting byte for DAC B, Gain 2

# 'Safety factor' for calculating how many sample points
# for DAC wave generation. Higher is rougher shapes.
FUDGE_FACTOR = const(1)

# Max voltage array length
N_STEP_MAX = const(300)
N_STEP_MIN = const(16)
FREQ_MAX = const(625)  # Hz

# Max number for 16-bit integer
MAX_NUM = const(65535)


def is_number(xx, annotation='an input', strict=True):
    Number = (int, float)
    truth = isinstance(xx, Number)
    if (not truth) and strict:
        raise ValueError('Expected {} to be of type {}'.format(annotation, Number))
    else:
        return truth


def get_N_step(ff):
    return int(1 / T_DAC_DELAY_US / ff)


def is_max(N_step):
    return N_step > N_STEP_MAX


def is_min(N_step):
    return N_step <= N_STEP_MIN


class Waveform:

    def __init__(self, Vpp=None, Vp=None, Vmin=None, Vmax=None, offset=0, freq=None, unsafe=False):
        Vmin, Vmax, freq = self.__clean_input(Vpp, Vp, Vmin, Vmax, offset, freq, unsafe)
        self.v_min = Vmin
        self.v_max = Vmax
        self.freq = freq

        self.array_period = MAX_NUM  # Used to calculate waveforms

        self.unsafe = unsafe

        self.N_step = None
        self.gain_2 = False

    def eq(self, tt):
        pass

    def set_N_step(self, N_step):
        self.N_step = N_step

    def __str__(self):
        return ('{} with Vmin={} mV, Vmax={} mV, and Frequency={}'
                .format(type(self).__name__, self.v_min, self.v_max, self.freq))

    def get_wcr_array(self):
        return self.__create_wcr_array()

    @staticmethod
    def __clean_input(V_PP, V_P, V_min, V_max, offset, freq, unsafe):

        has_vpp_input: bool = (V_PP is not None) or (V_P is not None)
        has_minmax_input: bool = (V_min is not None) and (V_max is not None)

        if not (has_vpp_input or has_minmax_input):  # No inputs
            raise Exception('Expected an keyword argument for waveform size.\n'
                            'Use either "V_PP" (Peak-to-Peak Voltage) or "V_P" (amplitude).\n'
                            'Alternatively specify "V_min" and "V_max" (extremes of the waveform).')
        elif has_vpp_input:
            if V_PP is not None:
                if is_number(V_PP, annotation='V_PP'):
                    V_P = V_PP / 2
            else:  # V_P input
                if is_number(V_P, annotation='V_P'):
                    pass

            V_max = offset + V_P
            V_min = offset - V_P

        elif has_minmax_input:
            if (is_number(V_max, annotation='V_max')
                    and is_number(V_min, annotation='V_min')):
                pass
        else:
            raise RuntimeError()

        # Input units in V, convert to units in mV
        # Everything should have been converted to V_min and V_max
        V_max = int(V_max * 1_000)
        V_min = int(V_min * 1_000)

        # Sanity check for frequency
        if freq is None:
            raise ValueError('Expected a keyword "freq" specifying '
                             'the frequency of the waveform')
        else:
            is_number(freq, annotation='Frequency')

        # Sanity check for voltage bounds
        if not unsafe and (V_max > MAX_VOLTAGE_TOLERATED):
            print(('WARNING:functiongenerator:Requested a peak maximum voltage of {} mV \n'
                   '\tthat is too high for safe mode. To prevent clipping, turn off  \n'
                   '\tsafe mode (not recommended) or request a voltage below {} mV'
                   ).format(V_max, MAX_VOLTAGE_TOLERATED))

        elif unsafe and (V_max > MAX_VOLTAGE_OVERDRIVE):
            print(('WARNING:functiongenerator:Requested a peak maximum voltage of {} mV \n'
                   '\tthat is too high for the DAC. To prevent clipping, \n'
                   '\tplease request a voltage below {} mV'
                   ).format(V_max, MAX_VOLTAGE_OVERDRIVE))

        elif V_min < MIN_VOLTAGE:
            print(('WARNING:functiongenerator:Requested a peak minimum voltage of {} mV \n'
                   '\tthat is too low for the DAC. To prevent clipping, \n'
                   '\tplease request a voltage above {} mV'
                   ).format(V_min, MIN_VOLTAGE))

        return V_min, V_max, freq

    def __clip_voltages(self, v_array):
        if self.unsafe:
            v_max = MAX_VOLTAGE_OVERDRIVE
        else:
            v_max = MAX_VOLTAGE_TOLERATED

        v_min = MIN_VOLTAGE

        v_array[v_array > v_max] = v_max
        v_array[v_array < v_min] = v_min

        return v_array

    def __voltage_to_integer(self, voltages):
        max_voltage = DAC_MAX_VOLTAGE_GAIN_2 if self.gain_2 else DAC_MAX_VOLTAGE_GAIN_1
        integers = np.array(voltages * DAC_MAX_INT / max_voltage, dtype=np.uint16)
        return integers

    def __create_wcr_array(self):
        if self.N_step is None:  # Need to calculate N_step
            N_step = get_N_step(self.freq)

            if is_max(N_step):
                raise ValueError('Requested frequency is too high, try a frequency below ' + str(FREQ_MAX) + ' Hz')
            elif is_min(N_step):
                N_step = N_STEP_MIN

        self.set_N_step(N_step)
        tt = np.linspace(0, MAX_NUM - 1, N_step, dtype=np.uint16)
        voltages = self.eq(tt)  # Use waveform equation
        voltages = self.__clip_voltages(voltages)

        if self.v_max >= DAC_MAX_VOLTAGE_GAIN_1:
            self.gain_2 = True
        else:
            self.gain_2 = False

        integers = self.__voltage_to_integer(voltages)

        return integers.tobytes()


class Sine(Waveform):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.N_step = None  # Floating N
        self.equation = [self.eq]

    def eq(self, tt):
        return np.array(0.5 * abs(self.v_max - self.v_min)
                        * np.sin(2 * np.pi * (tt / self.array_period))
                        + 0.5 * abs(self.v_max + self.v_min))


#######################################################################

def __setup_spi():
    # returns SPI objects. Used to so objects can be kept locally rather than globally.
    # Rationale: Local objects can be operated upon more quickly in MicroPython
    spi = SPI(1,
              baudrate=1_000_000,  # 20_000_000,
              polarity=1,
              phase=1,
              bits=8,
              firstbit=SPI.MSB,
              sck=Pin(PIN_NO_SCK),
              mosi=Pin(PIN_NO_MOSI),
              miso=None)
    CS = Pin(PIN_NO_CS, Pin.OUT)
    LDAC = Pin(PIN_NO_LDAC, Pin.OUT)

    return spi, CS, LDAC


def __function_generator_thread(wcr_array, freq, N_steps):
    global baton
    global stop_flag

    # Setup
    LED = Pin(25, Pin.OUT)
    LED.value(True)
    baton.acquire()

    spi, CS, LDAC = __setup_spi()

    # WRITE ------------------------
    delay_us = int(1e6 / freq / N_steps)  # delay in loop (in microseconds) necessary to generate wave
    delay_us = delay_us - 114
    if delay_us < 0:
        delay_us = 0

    # print('Resolution = ' + str(resolution) +' points. DAC update delay (us) = '+ str(delay_us))

    target = (2 * N_steps - 2)
    checking_interval = int(freq) if int(freq) > 0 else 1

    mv = memoryview(wcr_array)

    CS.value(True)
    LDAC.value(False)

    buffer = bytearray([0, 0])
    ii = 0  # Counts points written
    jj = 0  # Counts periods written
    while True:
        # PREPARE ---------------------------
        CS.value(False)
        buffer[0] = mv[ii]
        buffer[1] = mv[ii + 1]

        # WRITE POINT -----------------------------
        spi.write(buffer)
        CS.value(True)  # Datasheet: Chip select to end before LDAC pulse

        utime.sleep_us(delay_us)

        if ii == target:  # For looping the wave shape
            ii = 0
            jj += 1
        else:
            ii += 2

        if jj == checking_interval:  # For checking whether or not to stop every couple periods
            if stop_flag:
                break
            else:
                jj = 0

    print('W-AC')  # Done writing
    LED.value(False)  # Status LED off
    baton.release()

    return


class FuncGen:
    def __init__(self, waveform: Waveform, DAC: str = 'A', unsafe: bool = False):
        """Construct an instance of the Function Generator class.
        """

        global baton
        global stop_flag

        baton = _thread.allocate_lock()
        stop_flag = False

        self.waveform = waveform
        self.overdrive = unsafe

        self.wcr_array = self.waveform.get_wcr_array()

        print(self.wcr_array)

        for ii in range(len(self.wcr_array) // 2):
            bb = self.wcr_array[ii * 2: ii * 2 + 2]
            integer = int.from_bytes(bb, 'big')
            print('{} \t --> {:016b} --> {}'.format(bb, integer, integer))

        print('Printed {} pairs of bytes, should equal {}'.format(ii + 1, waveform.N_step))

        dac_A = not DAC in ['B', 'b']

        self.wcr_array = self.__add_instr_to_wcr_array(self.wcr_array,
                                                       dac_A,
                                                       self.waveform.gain_2)

        print(self.wcr_array)

    def __enter__(self):
        try:
            _thread.start_new_thread(__function_generator_thread, (
                self.wcr_array,
                self.waveform.freq,
                self.waveform.N_step))

        except OSError:
            raise OSError(
                'Could not start function generator because the function generator is already turned on.\n\n' +
                'Did you turn off the function generator in the code?\n\nResolve this error by fully rebooting the ALPACA.')

        utime.sleep_ms(100)

        return None

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Stop the function generator on the Alpaca.

        Will halt the function generator on the Alpaca and only returns when this happens succesfully.

        See Also
        --------
        Pico.start_function_generator
        """
        global baton
        global stop_flag

        stop_flag = True

        baton.acquire()  # Check if the other thread has stopped
        baton.release()

        spi, CS, LDAC = __setup_spi()

        CS.value(True)
        LDAC.value(False)

        CS.value(False)
        spi.write(b'\t\x00')  # Shutdown DAC B
        CS.value(True)

        CS.value(False)
        spi.write(b'\x01\x00')  # Shudown DAC A
        CS.value(True)

    def __add_instr_to_wcr_array(self, wcr_array, dac_a=True, gain_2=False):
        ###############################
        if dac_a and not gain_2:
            set_byte = SET_BYTE_A1
        elif dac_a and gain_2:
            set_byte = SET_BYTE_A2
        elif not dac_a and not gain_2:
            set_byte = SET_BYTE_B1
        else:
            set_byte = SET_BYTE_B2
        ###############################

        set_byte_array = np.array((len(wcr_array) // 2) * [set_byte], dtype=np.uint16).tobytes()

        new_wcr_array = bytearray((int.from_bytes(wcr_array, 'big')
                                   | int.from_bytes(set_byte_array, 'big')
                                   ).to_bytes(len(wcr_array), 'big'))

        return new_wcr_array

    def __graceful_exit(self):
        # """Method to shut down the function generator gracefully. This prevents 'core 1 in use' errors.
        # """
        self.LED.value(False)  # Status LED off
        self.baton.release()


if __name__ == '__main__':
    pass


