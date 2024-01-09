from ulab import numpy as np
import _thread
import utime
from machine import SPI, Pin

# Max voltage the DAC is allowed to produce. Set to 3300 mV in
# to protect against the DAC frying the Pico
_MAX_VOLTAGE_TOLERATED = const(3300)

# Max voltage the DAC can  produce.
# Will be used in overdrive mode
_MAX_VOLTAGE_OVERDRIVE = const(4096)

# Minimum voltage allowed, set to zero for MCP4822
_MIN_VOLTAGE = const(0)

_PIN_NO_MOSI = const(11)
_PIN_NO_SCK = const(10)
_PIN_NO_CS = const(13)
_PIN_NO_LDAC = const(12)

# Integer value, that when sent to the DAC over SPI will
# produce the largest voltage. 4096 for the MCP4822
_DAC_MAX_INT = const(4096)

# Max voltage the DAC can produce measured in millivolts.
# 4095 for the MCP4822 when the gain has been set to 2.
_DAC_MAX_VOLTAGE_GAIN_2 = const(4095)

# Max voltage the DAC can produce measured in millivolts.
# 4095 for the MCP4822 when the gain has been set to 2.
_DAC_MAX_VOLTAGE_GAIN_1 = const(2047)

# 114 us write delay, whatever pause we want between
# writes in our program has to be larger than this
_T_DAC_DELAY_US = const(73)

_SET_BYTE_A1 = const(12288)  # MCP4822 setting byte for DAC A, Gain 1
_SET_BYTE_A2 = const(4096)  # MCP4822 setting byte for DAC A, Gain 2
_SET_BYTE_B1 = const(45056)  # MCP4822 setting byte for DAC B, Gain 1
_SET_BYTE_B2 = const(36864)  # MCP4822 setting byte for DAC B, Gain 2

# 'Safety factor' for calculating how many sample points
# for DAC wave generation. Higher is rougher shapes.
_FUDGE_FACTOR = const(1)

_VOLTAGE_CALIB_FACTOR = 0.8948


# Max voltage array length
_N_STEP_MAX = const(4096)
_N_STEP_MIN = const(16)

# Max number for 16-bit integer
_MAX_NUM = const(65535)


def _is_number(n, annotation='an input', strict=True) -> bool:
    """Checks if an input is a number.

    Args:
        n: An input.
        annotation: The origin of this input. Used for creating error message.
        strict: Whether to throw an error message if the input is not a number.
          Defaults to True.

    Returns:
        True if the input is a number, else False.

    """
    Number = (int, float)
    truth = isinstance(n, Number)
    if (not truth) and strict:
        raise ValueError('Expected {} to be of type {}'
                         .format(annotation, Number))
    else:
        return truth


def _get_n_step(freq: float) -> int:
    """Gets the number of points for a frequency.

    Calculates the max number of subdivisions for a wave of a certain frequency.
    The function generator creates waves by stepping the DAC to different
    values. This function returns the maximum number of steps attainable
    in one period. Note that this is currently limited by the rate with which
    this Python code can send new points to the DAC chip.

    Args:
        freq (float): The frequency of a wave.

    Returns:
        An integer number of points with which the function generator can
          create the wave.

    """
    return int(1E6 / _T_DAC_DELAY_US / freq)


@micropython.native
def _as_fraction(number: float, accuracy: float = 0.0001) -> (int, int):
    """Converts a number to a fraction.

    Taken from:
    https://codereview.stackexchange.com/questions/159758/efficiently-finding-approximate-fraction-with-tolerance-for-fp-rounding)

    Args:
        number: A number to convert into a fraction.
        accuracy: The absolute accuracy with which to do the conversion.
          Defaults to 0.0001.

    Returns:
        A tuple of integers, the former being the enumerator and the latter the
          denominator.

    """

    whole, x = divmod(number, 1)
    if not x:
        return int(whole), 1
    n = 1
    while True:
        d = int(n / x)
        if n / d - x < accuracy:
            return int(whole) * d + n, d
        d += 1
        if x - n / d < accuracy:
            return int(whole) * d + n, d
        n += 1


class Waveform:

    def __init__(self, Vpp=None, Vp=None, Vmin=None, Vmax=None, offset=0,
                 freq=None, period=None, unsafe=False, hold=False):
        Vmin, Vmax, freq = self.__clean_input(Vpp, Vp, Vmin, Vmax, offset, freq, period,
                                              unsafe)
        self.v_min = Vmin
        self.v_max = Vmax
        self.freq = freq

        self.array_period = _MAX_NUM  # Used to calculate waveforms

        self.unsafe = unsafe
        self.hold = hold

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
    def __clean_input(V_PP, V_P, V_min, V_max, offset, freq, period, unsafe):

        has_vpp_input: bool = (V_PP is not None) or (V_P is not None)
        has_minmax_input: bool = (V_min is not None) and (V_max is not None)

        if not (has_vpp_input or has_minmax_input):  # No inputs
            raise Exception('Expected an keyword argument for waveform size.\n'
                            'Use either "V_PP" (Peak-to-Peak Voltage) or '
                            '"V_P" (amplitude).\n'
                            'Alternatively specify "V_min" and "V_max" ('
                            'extremes of the waveform).')
        elif has_vpp_input:
            if V_PP is not None:
                if _is_number(V_PP, annotation='V_PP'):
                    V_P = V_PP / 2
            else:  # V_P input
                if _is_number(V_P, annotation='V_P'):
                    pass

            V_max = offset + V_P
            V_min = offset - V_P

        elif has_minmax_input:
            if (_is_number(V_max, annotation='V_max')
                    and _is_number(V_min, annotation='V_min')):
                pass
        else:
            raise RuntimeError()

        # Input units in V, convert to units in mV
        # Everything should have been converted to V_min and V_max
        V_max = int(V_max * 1_000)
        V_min = int(V_min * 1_000)

        # Sanity check for frequency
        if freq is None and period is None:
            raise ValueError('Expected a keyword "freq" specifying '
                             'the frequency of the waveform or a keyword '
                             '"period" specifying the period.')
        if freq is None:
            freq = 1 / period

        _is_number(freq, annotation='Frequency')

        # Sanity check for voltage bounds
        if not unsafe and (V_max > _MAX_VOLTAGE_TOLERATED):
            pass
            # print(('WARNING:functiongenerator:Requested a peak maximum voltage of {} mV \n'
            #       '\tthat is too high for safe mode. To prevent clipping, turn off  \n'
            #        '\tsafe mode (not recommended) or request a voltage below {} mV'
            #        ).format(V_max, MAX_VOLTAGE_TOLERATED))

        elif unsafe and (V_max > _MAX_VOLTAGE_OVERDRIVE):
            pass
            # print(('WARNING:functiongenerator:Requested a peak maximum voltage of {} mV \n'
            #       '\tthat is too high for the DAC. To prevent clipping, \n'
            #        '\tplease request a voltage below {} mV'
            #        ).format(V_max, MAX_VOLTAGE_OVERDRIVE))

        elif V_min < _MIN_VOLTAGE:
            pass
            # print(('WARNING:functiongenerator:Requested a peak minimum voltage of {} mV \n'
            #       '\tthat is too low for the DAC. To prevent clipping, \n'
            #        '\tplease request a voltage above {} mV'
            #        ).format(V_min, MIN_VOLTAGE))

        return V_min, V_max, freq

    @micropython.native
    def __clip_voltages(self, v_array):
        if self.unsafe:
            v_max = _MAX_VOLTAGE_OVERDRIVE
        else:
            v_max = _MAX_VOLTAGE_TOLERATED

        v_min = _MIN_VOLTAGE

        v_array[v_array > v_max] = v_max
        v_array[v_array < v_min] = v_min

        return v_array

    @micropython.native
    def __voltage_to_integer(self, voltages):
        max_voltage = _DAC_MAX_VOLTAGE_GAIN_2 if self.gain_2 else _DAC_MAX_VOLTAGE_GAIN_1

        # print('Gain 2 {}'.format('ON' if self.gain_2 else 'OFF'))

        integers = np.array(voltages
                            * _DAC_MAX_INT
                            * _VOLTAGE_CALIB_FACTOR
                            / max_voltage,
                            dtype=np.uint16)

        return integers

    def get_voltages(self, n):
        tt = np.linspace(0, _MAX_NUM - 1, n, dtype=np.uint16)
        return self.eq(tt) / 1000 # Use waveform equation, get volts


    @micropython.native
    def __create_wcr_array(self):
        if self.N_step is None:  # Need to calculate N_step
            N_step = _get_n_step(self.freq)

            if N_step > _N_STEP_MAX:
                N_step = _N_STEP_MAX

            elif N_step <= _N_STEP_MIN:
                raise ValueError('Requested frequency is too high, '
                                 'try a frequency below {} Hz'.format(
                    str(1000000 // _T_DAC_DELAY_US // _N_STEP_MIN)))

            self.set_N_step(N_step)

        tt = np.linspace(0, _MAX_NUM - 1, self.N_step, dtype=np.uint16)
        voltages = self.eq(tt)  # Use waveform equation
        voltages = self.__clip_voltages(voltages)

        if self.v_max >= _DAC_MAX_VOLTAGE_GAIN_1:
            self.gain_2 = True
        else:
            self.gain_2 = False

        integers = self.__voltage_to_integer(voltages)

        return integers.byteswap().tobytes()


class Sine(Waveform):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.N_step = None  # Floating N
        self.equation = [self.eq]

    def eq(self, tt):
        return np.array(0.5 * abs(self.v_max - self.v_min)
                        * np.sin(2 * np.pi * (tt / self.array_period))
                        + 0.5 * abs(self.v_max + self.v_min))


class Triangle(Waveform):

    def __init__(self, symmetry=50, **kwargs):
        super().__init__(**kwargs)

        if symmetry > 100 or symmetry < 0:
            raise ValueError('Please input a symmetry between 0 and 100%')

        self.symmetry = symmetry
        self.N_step = None  # Floating N
        self.equation = [self.eq]

    def eq(self, tt):

        frac = self.symmetry / 100
        v_pp = abs(self.v_max - self.v_min)

        if self.symmetry == 0:
            up = 0

            down_coef = v_pp / self.array_period / (1 - frac)
            down = down_coef * tt
            down = down[::-1]

        elif self.symmetry == 100:
            up = v_pp * (tt / self.array_period) / frac + self.v_min

            down = 0

        else:
            switch_idx = int(len(tt) * frac)

            up = v_pp * (tt / self.array_period) / frac + self.v_min
            up[switch_idx:] = 0

            down_coef = v_pp / self.array_period / (1 - frac)
            down = down_coef * tt
            down = down[::-1]
            down[:switch_idx] = 0

        return up + down


class DC(Waveform):

    def __init__(self, V=None, hold=False, **kwargs):

        if not isinstance(V, (float, int)):
            raise ValueError(
                'Please input the DC voltage as a single number (float or int).')

        if V is None:
            raise ValueError('Please input a DC voltage.')

        super().__init__(Vmin=V, Vmax=V, freq=1)

        self.V = V * 1000  # Convert to mV
        self.N_step = 2  # Floating N
        self.equation = [self.eq]
        self.hold = hold

    def eq(self, tt):
        return np.array([self.V] * 2)


class Square(Waveform):

    def __init__(self, duty_cycle: int = 50, **kwargs):
        self.duty_cycle = int(duty_cycle)

        if self.duty_cycle > 100 or self.duty_cycle < 0:
            raise ValueError('Please input a duty cycle between 0 and 100%')

        super().__init__(**kwargs)

        if self.duty_cycle == 100 or self.duty_cycle == 0:
            self.fraction = None
            self.N_step = 2  # Fixed N
        else:

            self.fraction = _as_fraction(self.duty_cycle / 100)
            self.fraction = (
                self.fraction[1] - self.fraction[0], self.fraction[0])
            self.N_step = sum(self.fraction)

        self.equation = [self.eq]

    def eq(self, tt):
        if self.duty_cycle == 100:
            return np.array([self.v_max] * 2)
        elif self.duty_cycle == 0:
            return np.array([self.v_min] * 2)
        else:

            return np.array(
                [self.v_min] * self.fraction[0] + [self.v_max] * self.fraction[
                    1])

class Arbitrary(Waveform):

    def __init__(self, voltages, freq: float = None, period: float = None,
                 unsafe=False, hold=False):

        super().__init__(Vmax=1, Vmin=0, freq=freq,
                         period=period, unsafe=unsafe, hold=hold)
        self.voltages = voltages
        self.N_step = len(voltages)  # Floating N
        self.equation = [self.eq]

    # Really hacky but let's go with it
    def eq(self, tt):
        return np.array(self.voltages) * 1000 # V to mV



#######################################################################

def _setup_spi():
    # returns SPI objects. Used to so objects can be kept locally rather than globally.
    # Rationale: Local objects can be operated upon more quickly in MicroPython
    spi = SPI(1,
              baudrate=1_000_000,  # 20_000_000,
              polarity=1,
              phase=1,
              bits=8,
              firstbit=SPI.MSB,
              sck=Pin(_PIN_NO_SCK),
              mosi=Pin(_PIN_NO_MOSI),
              miso=None)
    CS = Pin(_PIN_NO_CS, Pin.OUT)
    LDAC = Pin(_PIN_NO_LDAC, Pin.OUT)

    return spi, CS, LDAC


@micropython.native
def __function_generator_thread(wcr_array: bytearray, freq_mHz: int,
                                N_steps: int) -> None:
    global baton
    global stop_flag

    # Setup
    LED = Pin(25, Pin.OUT)
    LED.value(True)
    baton.acquire()

    spi, CS, LDAC = _setup_spi()

    # WRITE ------------------------
    delay_us = int(
        1e9 / freq_mHz / N_steps)  # delay in loop (in microseconds) necessary to generate wave
    delay_us = delay_us - _T_DAC_DELAY_US
    if delay_us < 0:
        delay_us = 0

    # print('Resolution = ' + str(resolution) +' points. DAC update delay (us) = '+ str(delay_us))

    target = (2 * N_steps - 2)
    checking_interval = int(freq_mHz / 1000) if int(freq_mHz / 1000) > 0 else 1

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

    # print('W-AC')  # Done writing
    LED.value(False)  # Status LED off
    baton.release()

    return


def _add_instr_to_wcr_array(wcr_array, dac_a=True, gain_2=False):
    ###############################
    if dac_a and not gain_2:
        set_byte = _SET_BYTE_A1
    elif dac_a and gain_2:
        set_byte = _SET_BYTE_A2
    elif not dac_a and not gain_2:
        set_byte = _SET_BYTE_B1
    else:
        set_byte = _SET_BYTE_B2
    ###############################

    set_byte_array = np.array((len(wcr_array) // 2) * [set_byte],
                              dtype=np.uint16).byteswap().tobytes()

    new_wcr_array = bytearray((int.from_bytes(wcr_array, 'big')
                               | int.from_bytes(set_byte_array, 'big')
                               ).to_bytes(len(wcr_array), 'big'))

    return new_wcr_array


class FuncGen:
    def __init__(self, waveform: Waveform, channel: str = 'A',
                 unsafe: bool = False):
        """Construct an instance of the Function Generator class.
        """

        global baton
        global stop_flag

        baton = _thread.allocate_lock()
        stop_flag = False

        self.waveform = waveform
        self.overdrive = unsafe

        self.wcr_array = self.waveform.get_wcr_array()

        self.dac_A = not channel in ['B', 'b']

        self.wcr_array = _add_instr_to_wcr_array(self.wcr_array,
                                                       self.dac_A,
                                                       self.waveform.gain_2)

    def __enter__(self):
        try:
            _thread.start_new_thread(__function_generator_thread, (
                self.wcr_array,
                int(self.waveform.freq * 1000),
                self.waveform.N_step))
            # Convert frequency in Hz to mHz

        except OSError:
            raise OSError(
                'Could not start function generator because the function generator is already turned on.\n\n' +
                'Did you turn off the function generator in the code?\n\nResolve this error by fully rebooting the ALPACA.')

        utime.sleep_ms(10)

        return self

    def update(self, waveform: Waveform):

        # Stop thread
        global baton
        global stop_flag

        stop_flag = True

        baton.acquire()  # Check if the other thread has stopped
        baton.release()

        # Update waveform
        self.waveform = waveform

        self.wcr_array = _add_instr_to_wcr_array(
            self.waveform.get_wcr_array(),
            self.dac_A,
            self.waveform.gain_2)

        # Go again
        stop_flag = False
        self.__enter__()


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

        if not self.waveform.hold:
            spi, CS, LDAC = _setup_spi()

            CS.value(True)
            LDAC.value(False)

            CS.value(False)
            spi.write(b'\t\x00')  # Shutdown DAC B
            CS.value(True)

            CS.value(False)
            spi.write(b'\x01\x00')  # Shudown DAC A
            CS.value(True)

    def __graceful_exit(self):
        # """Method to shut down the function generator gracefully. This prevents 'core 1 in use' errors.
        # """
        self.LED.value(False)  # Status LED off
        self.baton.release()


if __name__ == '__main__':
    pass
