# MIT license; Copyright (c) 2024 Thijn Hoekstra

"""Function generator and means to define waveforms.

This module contains classes that provide function generator functionality to
the ALPACA. In the Studio Classroom, the `Agilent 33220a`_ Function / Waveform
Generator is used to this end. This module intends to mimic a subset of the
functionality of that device using the ALPACA. The desired output is created by
modulating (stepping) the output of the `MCP 4822`_ Digital-to-Analog Coverter
(DAC).

To create a waveform, one must first define it. This can be done using a
number of classes implemented in this module, e.g. `Sine`, `Triangle`, and
`Square`, for sine, square, and triangular (sawtooth) waves respectively.

Such a waveform, once created, needs to be created using the DAC. To do so,
this module implements a function generator `FuncGen`. `FuncGen` is intended to
be used in a `with`-statement, i.e. as a so-called `context manager`_.

Example:

    A typical usage example, in which a sine wave is defined and created using the
    function generator is shown below. The output of the function generator
    defaults to the A channel of the DAC. At the same time, the output of the
    function generator is measured using the analog input pins of the ALPACA::

        >>> import time
        >>> import machine
        >>> from functiongenerator import FuncGen, Sine
        >>>
        >>> a0 = machine.ADC(26)
        >>>
        >>> sine = Sine(Vmin=0, Vmax=1, freq=1)
        >>> with FuncGen(sine): # Turn on the function generator and create a sine.
            for i in range(250): # Take 250 samples
                print("a0: ", a0.read_u16() * 5.0354e-05) # Print result in volts
                time.sleep(0.01) # Delay such that sampling occurs at 100 Hz

    This can be made more consise by creating and directly passing the waveform:

    >>> with FuncGen(Sine(Vmin=1, Vmax=1, freq=1)):
    >>>     pass # Measurement, etc.

.. _`Agilent 33220a`:
    https://www.keysight.com/us/en/product/33220A/function--arbitrary-waveform-generator-20-mhz.html
.. _`MCP 4822`: https://www.microchip.com/en-us/product/mcp4822
.. _`context manager`: https://peps.python.org/pep-0343/
"""


from ulab import numpy as np
import _thread
import utime
from machine import SPI, Pin

try:
    const(1)
except NameError:
    # This is being run by autodoc. Create some dummy objects
    def const(n):
        # """Dummy const"""
        return n

    def micropython(f):
        # """Dummy micropython decorator"""
        pass

    micropython.native = lambda f: f




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
    """A generic waveform.

    A generic waveform consisting of discrete voltages. Intended to make it
    convenient to use the function generator or to create sequences of voltages,
    like sine wave, square waves, or sawtooth waves. Can be initialized
    based on a set of parameters that fully define the wave.

    For defining the amplitude of the waveform this can for example be a
    peak-to-peak voltage (`Vpp`) along
    with an offset voltage (`offset`), a peak-to-mean voltage (`Vp`)
    along with an offset voltage, or a minimum voltage (`Vmin`) along
    with a maximum voltage (`Vmax`).

    The time characteristic of the waveform can be defined either as a
    frequency (`freq`) or as a period (`period`).

    Attributes:
        v_min (int): An integer expressing the minimum voltage of the waveform
            in milli-volts.
        v_max (int): An integer expressing the maximum voltage of the waveform
            in milli-volts.
        freq (float): A float indicating the frequency of the wave.
        unsafe (bool): A boolean indicating whether the waveform is allowed to
            exceed a maximum voltage of 3.3 volts (the maximum voltage of the
            analog inputs on the `Raspberry Pi Pico`_ on the ALPACA). Defaults to
            False.
        hold (bool): A boolean indicating whether the current voltage of the waveform
            should be held when used for the function generator. Defaults to
            False, causing the DAC to shut off.

    Args:
        Vpp (float): The peak-to-peak voltage of waveform in volts.
        Vp (float): The peak-to-mean voltage of waveform in volts.
        Vmin (float): The minimum voltage of the waveform in volts.
        Vmax (float): The maximum voltage of the waveform in volts.
        offset (float): The offset voltage of the mean of the waveform in
            volts.
        freq (float): The frequency of the waveform in Hertz.
        period (float): The period of the waveform in seconds.
        unsafe (bool): A boolean indicating whether the waveform is allowed
            to exceed a maximum voltage of 3.3 volts (the maximum voltage
            of the analog inputs on the `Raspberry Pi Pico`_ on the ALPACA).
            Defaults to False.
        hold (bool): A boolean indicating whether the current voltage of the
            waveform should be held when used for the function generator.
            Defaults to False, causing the DAC to shut off after the
            function generator stops.

    Raises:
        ValueError: If no pair of parameters that fully defines the waveform
            was given.

    Note:
        By default, the voltage range of the waveform is limited to 0-3.3 V,
        the range that is safe for input to the analog input pins of the
        `Raspberry Pi Pico`_ in the ALPACA. Voltages of a waveform that fall
        outside this range are clipped, i.e. set to either 0 or 3.3 V. This
        behavior can be turned off using the `unsafe` parameter, increasing
        the range of the waveform to that of the `MCP 4822`_ DAC, i.e. to
        0-4.096 V. Note that in both cases, this clipping will occur
        silently.

    Note:
        A good example for when to set the `hold` paramater is
        when using the DAC Assistant on the ALPACA. If the DAC is connected
        to the DAC Assistant and turned off (0 V) after use, the voltage at
        the output of the assistant will shoot to a large negative voltage.
        This might be undesirable for a certain circuit connected to this
        output. By setting `hold` to True, the DAC will hold the voltage
        to whatever voltage the function generator happened to end on.
        Depending on the voltage range of the waveform, this can guarantee
        a desirable output at the DAC Assistant output.


    Examples:
        A generic waveform with a mean voltage of 1.5 volts, an amplitude
        of 1.5 volts, and a frequency of 10 Hz and can be created in many
        ways. Using a mean voltage, an amplitude, and a frequency:

        >>> wf = Waveform(Vp=1.5, offset=1.5, freq=10)

        Using a mean voltage and a peak-to-peak voltage:

        >>> wf = Waveform(Vpp=3, offset=1.5, freq=10)

        Using a minimum and maximum voltage:

        >>> wf = Waveform(Vmin=0, Vmax=3, freq=10)

        Using a period rather than a frequency:
        >>> wf = Waveform(Vmin=0, Vmax=3, freq=0.1)

    .. _`MCP 4822`: https://www.microchip.com/en-us/product/mcp4822
    .. _`Raspberry Pi Pico`: https://www.raspberrypi.com/products/raspberry-pi-pico/
    """

    def __init__(self, Vpp=None, Vp=None, Vmin=None, Vmax=None, offset=0,
                 freq=None, period=None, unsafe=False, hold=False):

        Vmin, Vmax, freq = self._clean_input(Vpp, Vp, Vmin, Vmax, offset,
                                             freq, period, unsafe)
        self.v_min = Vmin
        self.v_max = Vmax
        self.freq = freq

        self._array_period = _MAX_NUM  # Used to calculate waveforms

        self.unsafe = unsafe
        self.hold = hold

        self._N_step = None  # Number of discrete voltages in the waveform.
        self._gain_2 = False  # Whether 2X gain is needed to create the waveform.
        self._equation = None # TODO: make this implementation nicer

    def _eq(self, tt: np.ndarray) -> np.ndarray:
        raise NotImplementedError('Error the generic waveform is not intended '
                                  'for direct use. Please use a subclass.')

    def _set_N_step(self, n: int) -> None:
        self._N_step = n

    def __str__(self):
        return ('{} with Vmin={} mV, Vmax={} mV, and Frequency={}'
                .format(type(self).__name__, self.v_min, self.v_max, self.freq))

    def _get_wcr_array(self) -> np.ndarray:
        return self._create_wcr_array()

    @staticmethod
    def _clean_input(V_PP: float, V_P: float,
                     V_min: float, V_max: float,
                     offset: float,
                     freq: float, period: float, unsafe: bool) -> tuple:

        has_vpp_input: bool = (V_PP is not None) or (V_P is not None)
        has_minmax_input: bool = (V_min is not None) and (V_max is not None)

        if not (has_vpp_input or has_minmax_input):  # No inputs
            raise ValueError('Expected an keyword argument for waveform size.\n'
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
    def _clip_voltages(self, v_array):
        if self.unsafe:
            v_max = _MAX_VOLTAGE_OVERDRIVE
        else:
            v_max = _MAX_VOLTAGE_TOLERATED

        v_min = _MIN_VOLTAGE

        v_array[v_array > v_max] = v_max
        v_array[v_array < v_min] = v_min

        return v_array

    @micropython.native
    def _voltage_to_integer(self, voltages):
        max_voltage = _DAC_MAX_VOLTAGE_GAIN_2 if self._gain_2 else _DAC_MAX_VOLTAGE_GAIN_1

        # print('Gain 2 {}'.format('ON' if self.gain_2 else 'OFF'))

        integers = np.array(voltages
                            * _DAC_MAX_INT
                            * _VOLTAGE_CALIB_FACTOR
                            / max_voltage,
                            dtype=np.uint16)

        return integers

    def get_voltages(self, n: int) -> np.ndarray:
        """Express the waveform as an array of voltages.

        Create an array of N voltages from a waveform. One period of the
        waveform is sampled to N discrete points equally spaced in time.

        Args:
            n (int): The number of voltages to which to convert the waveform.

        Returns:
            np.ndarray: The waveform converted to an array of N voltages.

        Note:
            The voltages obtained using this method will not undergo the
            clipping process described in the initilization method of
            :py:meth:`functiongenerator.Waveform`.

        Note:
            This function is not defined for the generic
            :py:meth:`functiongenerator.Waveform` class, but only works for its
            sub-classes, e.g. :py:meth:`functiongenerator.Sine` and
            :py:meth:`functiongenerator.Triangle`.

        Examples:
            Converting a generic waveform into an array using 100 discrete
            points.

            >>> wf = Waveform(Vp=1.5, offset=1.5, freq=10)
            >>> a = wf.get_voltages(100)
            >>> print(len(a))
            100
        """

        t = np.linspace(0, _MAX_NUM - 1, int(n), dtype=np.uint16)
        return self._eq(t) / 1000  # Use waveform equation, get volts

    @micropython.native
    def _create_wcr_array(self):
        if self._N_step is None:  # Need to calculate N_step
            N_step = _get_n_step(self.freq)

            if N_step > _N_STEP_MAX:
                N_step = _N_STEP_MAX

            elif N_step <= _N_STEP_MIN:
                raise ValueError('Requested frequency is too high, '
                                 'try a frequency below {} Hz'.format(
                    str(1000000 // _T_DAC_DELAY_US // _N_STEP_MIN)))

            self._set_N_step(N_step)

        tt = np.linspace(0, _MAX_NUM - 1, self._N_step, dtype=np.uint16)
        voltages = self._eq(tt)  # Use waveform equation
        voltages = self._clip_voltages(voltages)

        if self.v_max >= _DAC_MAX_VOLTAGE_GAIN_1:
            self._gain_2 = True
        else:
            self._gain_2 = False

        integers = self._voltage_to_integer(voltages)

        return integers.byteswap().tobytes()


class Sine(Waveform):
    """A sine wave.

    A `sine wave`_ consisting of discrete voltages.
    Can be initilized using a set of parameters that fully define
    the wave. For more details, consult the documentation of the super
    class :py:class:`functiongenerator.Waveform`.

    Attributes:
        v_min (int): See :py:attr:`functiongenerator.Waveform.v_min`.
        v_max (int): See :py:attr:`functiongenerator.Waveform.v_max`.
        freq (float): See :py:attr:`functiongenerator.Waveform.freq`.
        unsafe (bool): See :py:attr:`functiongenerator.Waveform.unsafe`.
        hold (bool): See :py:attr:`functiongenerator.Waveform.hold`.


    Args:
        Vpp (float): See :py:class:`functiongenerator.Waveform`.
        Vp (float): See :py:class:`functiongenerator.Waveform`.
        Vmin (float): See :py:class:`functiongenerator.Waveform`.
        Vmax (float): See :py:class:`functiongenerator.Waveform`.
        offset (float): See :py:class:`functiongenerator.Waveform`.
        freq (float): See :py:class:`functiongenerator.Waveform`.
        period (float): See :py:class:`functiongenerator.Waveform`.
        unsafe (bool): See :py:class:`functiongenerator.Waveform`.
        hold (bool): See :py:class:`functiongenerator.Waveform`.

    Raises:
        ValueError: If no pair of parameters that fully defines the sine wave
            was given.

    Examples:
        A sine wave with a mean voltage of 1.5 volts, an amplitude
        of 1.5 volts, and a frequency of 10 Hz and can be created in many
        ways. Using a mean voltage, an amplitude, and a frequency:

        >>> wf = Sine(Vp=1.5, offset=1.5, freq=10)

        For more information on various ways of defining a waveform, see:
        :py:class:`functiongenerator.Waveform`.

    .. _`Raspberry Pi Pico`: https://www.raspberrypi.com/products/raspberry-pi-pico/
    .. _`sine wave`: https://en.wikipedia.org/wiki/Sine_wave
    """

    def __init__(self, **kwargs):


        super().__init__(**kwargs)
        self._N_step = None  # Floating N
        self._equation = [self._eq]

    def _eq(self, tt):
        return np.array(0.5 * abs(self.v_max - self.v_min)
                        * np.sin(2 * np.pi * (tt / self._array_period))
                        + 0.5 * abs(self.v_max + self.v_min))


class Triangle(Waveform):
    """A triangle wave.

    A `triangle wave`_ consisting of discrete voltages. Can be initialized using
    a set of parameters that fully define the wave.
    For more details, consult the documentation of the super
    class :py:class:`functiongenerator.Waveform`. Can be used to create
    a symmetric triangle wave, a `sawtooth wave`_ (in both orientations), and
    other asymetric triangle waves.

    Attributes:
        v_min (int): See :py:attr:`functiongenerator.Waveform.v_min`.
        v_max (int): See :py:attr:`functiongenerator.Waveform.v_max`.
        freq (float): See :py:attr:`functiongenerator.Waveform.freq`.
        symmetry (float): A floating point number between 0 and 100. The skew
            of the triangle is determined by the percentile value of symmetry.
            If set to 50, the triangle is symmetric, i.e. the rise time is
            exactly equal to the fall time. When set to 100, a rising
            sawtooth wave is created. Conversely, when set to 0, a falling
            sawtooth wave is created. Intermediate values result in triangle
            waves with a difference between the rise and fall times.
        unsafe (bool): See :py:attr:`functiongenerator.Waveform.unsafe`.
        hold (bool): See :py:attr:`functiongenerator.Waveform.hold`.

    Args:
        Vpp (float): See :py:class:`functiongenerator.Waveform`.
        Vp (float): See :py:class:`functiongenerator.Waveform`.
        Vmin (float): See :py:class:`functiongenerator.Waveform`.
        Vmax (float): See :py:class:`functiongenerator.Waveform`.
        offset (float): See :py:class:`functiongenerator.Waveform`.
        symmetry (float): A floating point number between 0 and 100. The skew
            of the triangle is determined by the percentile value of symmetry.
            If set to 50, the triangle is symmetric, i.e. the rise time is
            exactly equal to the fall time. When set to 100, a rising
            sawtooth wave is created. Conversely, when set to 0, a falling
            sawtooth wave is created. Intermediate values result in triangle
            waves with a difference between the rise and fall times. Defaults
            to 50.
        freq (float): See :py:class:`functiongenerator.Waveform`.
        period (float): See :py:class:`functiongenerator.Waveform`.
        unsafe (bool): See :py:class:`functiongenerator.Waveform`.
        hold (bool): See :py:class:`functiongenerator.Waveform`.

    Raises:
        ValueError: If no pair of parameters that fully defines the triangle wave
            was given.

    Examples:
        A symmetric triangle wave with a mean voltage of 1.5 volts, an amplitude
        of 1.5 volts, and a frequency of 10 Hz and can be created in many
        ways. Using a mean voltage, an amplitude, and a frequency:

        >>> wf = Triangle(Vp=1.5, offset=1.5, freq=10)

        A rising sawtooth wave can be created as follows:

        >>> wf = Triangle(Vp=1.5, offset=1.5, symmetry=100, freq=10)

        Likewise, a falling sawtooth wave can be created using:

        >>> wf = Triangle(Vp=1.5, offset=1.5, symmetry=0, freq=10)

        Other values for symmetry between 0 and 100 are also possible:

        >>> wf = Triangle(Vp=1.5, offset=1.5, symmetry=33.3, freq=10)

        For more information on various ways of defining a waveform, see:
        :py:class:`functiongenerator.Waveform`.


    .. _`Raspberry Pi Pico`: https://www.raspberrypi.com/products/raspberry-pi-pico/
    .. _`triangle wave`: https://en.wikipedia.org/wiki/Triangle_wave
    .. _`sawtooth wave`: https://en.wikipedia.org/wiki/Sawtooth_wave
    """

    def __init__(self, symmetry=50, **kwargs):
        super().__init__(**kwargs)

        if symmetry > 100 or symmetry < 0:
            raise ValueError('Please input a symmetry between 0 and 100%')

        self.symmetry = symmetry
        self._N_step = None  # Floating N
        self._equation = [self._eq]

    def _eq(self, tt):

        frac = self.symmetry / 100
        v_pp = abs(self.v_max - self.v_min)

        if self.symmetry == 0:
            up = 0

            down_coef = v_pp / self._array_period + self.v_min
            down = down_coef * tt
            down = down[::-1]

        elif self.symmetry == 100:
            up = v_pp * (tt / self._array_period) + self.v_min

            down = 0

        else:
            switch_idx = int(len(tt) * frac)

            up = v_pp * (tt / self._array_period) / frac + self.v_min
            up[switch_idx:] = 0

            down_coef = v_pp / self._array_period / (1 - frac)
            down = down_coef * tt + self.v_min
            down = down[::-1]
            down[:switch_idx] = 0

        return up + down


class DC(Waveform):
    """A constant voltage.

    A waveform consisting of a constant voltage, i.e. a DC voltage

    Attributes:
        v (int): DC voltage in milli-volts.
        unsafe (bool): See :py:attr:`functiongenerator.Waveform.unsafe`.
        hold (bool): See :py:attr:`functiongenerator.Waveform.hold`.

    Args:
        V (float): Constant voltage in volts.
        unsafe (bool): See :py:class:`functiongenerator.Waveform`.
        hold (bool): See :py:class:`functiongenerator.Waveform`.

    Examples:
        A waveform of a DC current at 1 volt:

        >>> wf = DC(V=1)

    """

    def __init__(self, V=None, hold=False, unsafe=False):

        if not isinstance(V, (float, int)):
            raise ValueError(
                'Please input the DC voltage as a single number (float or int).')

        if V is None:
            raise ValueError('Please input a DC voltage.')

        super().__init__(Vmin=V, Vmax=V, freq=1, unsafe=unsafe, hold=hold)

        self.v = V * 1000  # Convert to mV
        self._N_step = 2  # Floating N
        self._equation = [self._eq]

    def _eq(self, tt):
        return np.array([self.v] * 2)


class Square(Waveform):
    """A square wave.

    A `square wave`_ consisting of discrete voltages. Can be initialized using
    a set of parameters that fully define the wave.
    For more details, consult the documentation of the super
    class :py:class:`functiongenerator.Waveform`. Can be used to create
    a square wave with a specified `duty cycle`_.

    Attributes:
       v_min (int): See :py:attr:`functiongenerator.Waveform.v_min`.
       v_max (int): See :py:attr:`functiongenerator.Waveform.v_max`.
       freq (float): See :py:attr:`functiongenerator.Waveform.freq`.
       duty_cycle (float): A floating point number between 0 and 100
        specifying the fraction of time which the wave is at the maximum
        voltage.
       unsafe (bool): See :py:attr:`functiongenerator.Waveform.unsafe`.
       hold (bool): See :py:attr:`functiongenerator.Waveform.hold`.

    Args:
       Vpp (float): See :py:class:`functiongenerator.Waveform`.
       Vp (float): See :py:class:`functiongenerator.Waveform`.
       Vmin (float): See :py:class:`functiongenerator.Waveform`.
       Vmax (float): See :py:class:`functiongenerator.Waveform`.
       offset (float): See :py:class:`functiongenerator.Waveform`.
       duty_cycle (float): A floating point number between 0 and 100
        specifying the fraction of time which the wave is at the maximum
        voltage. Defaults to 50.
       freq (float): See :py:class:`functiongenerator.Waveform`.
       period (float): See :py:class:`functiongenerator.Waveform`.
       unsafe (bool): See :py:class:`functiongenerator.Waveform`.
       hold (bool): See :py:class:`functiongenerator.Waveform`.

    Raises:
       ValueError: If no pair of parameters that fully defines the square wave
           was given.

    Note:
        If the amplitude of the waveform is irrelevant to the application,
        also consider using `PWM`_ on a digital pin instead,
        as this a much faster and more
        efficient implementation. PWM is however limited to the square wave
        between 0 and 3.3 V (the output values of the digital pins).




    Todo:
        * This is a really lazy implementation
        (i.e. with the ratio of updates to the DAC)

    Examples:
       A square wave with a mean voltage of 1.5 volts, an amplitude
       of 1.5 volts, and a frequency of 10 Hz and can be created in many
       ways. Using a mean voltage, an amplitude, and a frequency:

       >>> wf = Square(Vp=1.5, offset=1.5, freq=10)

       The duty cycle of the square wave can be set from 0 to 100:

       >>> wf = Square(Vp=1.5, offset=1.5, duty_cycle=33.3, freq=10)

       For more information on various ways of defining a waveform, see:
       :py:class:`functiongenerator.Waveform`.


    .. _`Raspberry Pi Pico`: https://www.raspberrypi.com/products/raspberry-pi-pico/
    .. _`square wave`: https://en.wikipedia.org/wiki/Square_wave
    .. _`duty cycle`: https://en.wikipedia.org/wiki/Duty_cycle
    .. _`PWM`: https://docs.micropython.org/en/latest/rp2/quickref.html#pwm-pulse-width-modulation
    """

    def __init__(self, duty_cycle: float = 50, **kwargs):
        self.duty_cycle = float(duty_cycle)

        if self.duty_cycle > 100 or self.duty_cycle < 0:
            raise ValueError('Please input a duty cycle between 0 and 100%')

        super().__init__(**kwargs)

        if self.duty_cycle == 100 or self.duty_cycle == 0:
            self._fraction = None
            self._N_step = 2  # Fixed N
        else:

            self._fraction = _as_fraction(self.duty_cycle / 100)
            self._fraction = (
                self._fraction[1] - self._fraction[0], self._fraction[0])
            self._N_step = sum(self._fraction)

        self._equation = [self._eq]

    def _eq(self, tt):
        if self.duty_cycle == 100:
            return np.array([self.v_max] * 2)
        elif self.duty_cycle == 0:
            return np.array([self.v_min] * 2)
        else:

            return np.array(
                [self.v_min] * self._fraction[0] + [self.v_max] * self._fraction[
                    1])


class Arbitrary(Waveform):
    """An abritrarily shaped wave.

    An aribitrarily shaped wave consisting of discrete voltages. Initilized
    using a sequence of voltages to be created at the output of the DAC.

    Attributes:
       voltages (np.ndarray): An sequence of voltages that make up the waveform.
       freq (float): See :py:attr:`functiongenerator.Waveform.freq`.
       unsafe (bool): See :py:attr:`functiongenerator.Waveform.unsafe`.
       hold (bool): See :py:attr:`functiongenerator.Waveform.hold`.

    Args:
       voltages (np.ndarray): An sequence of voltages that make up the waveform.
       freq (float): See :py:class:`functiongenerator.Waveform`.
       period (float): See :py:class:`functiongenerator.Waveform`.
       unsafe (bool): See :py:class:`functiongenerator.Waveform`.
       hold (bool): See :py:class:`functiongenerator.Waveform`.

    Note:
        Using the function generator,
        the waveform will be created in the background, i.e. in parallel with
        whatever code is run inside the `while`. Similar functionality can also
        be created using
        :py:meth:`dac.DAC.write`. in a `for` loop. When using
        the DAC directly this way, this operation happens in series with the
        other code.
        This method might be more suitable if some measurement has to be
        synchronized with the output of the DAC. To conviently get an array to
        put into :py:meth:`dac.DAC.write`, consider turning a `Waveform` into
        an array using :py:meth:`functiongenerator.Waveform.get_voltages`.


    Examples:
        A waveform consisting of three voltages stepping up, i.e. from 0
        to 4 volts (and then back to 0 volts) in steps of 1 volt with a
        frequency of 100 milli-Hertz.

        >>> steps = [0, 1, 2, 3, 4]
        >>> wf = Arbitrary(steps, freq=0.1)

        For the arbitrary waveform, it might often make more sense to define
        the period of the whole wave.

        >>> wf = Arbitrary(steps, period=10)

        This can also be expressed as the delay between two steps:
        >>> step_delay = 2
        >>> wf = Arbitrary(steps, period=len(steps) * step_delay)

    .. _`arbitrary waveform generator`: https://en.wikipedia.org/wiki/Arbitrary_waveform_generator
    """

    def __init__(self, voltages: np.ndarray,
                 freq: float = None, period: float = None,
                 unsafe=False, hold=False):
        super().__init__(Vmax=1, Vmin=0, freq=freq,
                         period=period, unsafe=unsafe, hold=hold)
        self.voltages = voltages
        self._N_step = len(voltages)
        self._equation = [self._eq]

    # Really hacky but let's go with it
    def _eq(self, tt):
        return np.array(self.voltages) * 1000  # V to mV


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
def _function_generator_thread(wcr_array: bytearray, freq_mHz: int,
                               N_steps: int) -> None:
    global _baton
    global _stop_flag

    # Setup
    LED = Pin(25, Pin.OUT)
    LED.value(True)
    _baton.acquire()

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
    i = 0  # Counts points written
    j = 0  # Counts periods written
    while True:
        # PREPARE ---------------------------
        CS.value(False)
        buffer[0] = mv[i]
        buffer[1] = mv[i + 1]

        # WRITE POINT -----------------------------
        spi.write(buffer)
        CS.value(True)  # Datasheet: Chip select to end before LDAC pulse

        utime.sleep_us(delay_us)

        if i == target:  # For looping the wave shape
            i = 0
            j += 1
        else:
            i += 2

        if j == checking_interval:  # For checking whether or not to stop every couple periods
            if _stop_flag:
                break
            else:
                j = 0

    # print('W-AC')  # Done writing
    LED.value(False)  # Status LED off
    _baton.release()

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
    """A class for a function generator.

    A class that creates a function generator and starts it. Take a waveform as
    an input and starts a process that takes control of the `MCP 4822`_
    Digital-to-Analog Coverter (DAC) on the ALPACA. The DAC is continuously
    updated to approximate the requested waveform. Note that this happens in a
    thread that is entirely seperate from the main thread, meaning that code
    in the main thread can be exectued simultaneously. This is advantageous for
    most measuring setups, where you want to simultaneously create some signal
    using the function generator, which you then pass through a circuit of some
    sort, and measure using the analog pins on the ALPACA (the latter being
    the part run in the main thread). This parallel operation can be handled
    using `with`-statement, i.e. as a so-called `context manager`_.

    Attributes:
       waveform (Waveform): The waveform to be created by the function
        generator.
       dac_A (bool): A boolean specifying if the DAC A channel is used
        (rather than DAC B).

    Args:
        waveform (Waveform): The waveform to be created by the function
            generator.
        channel (str): A string specifying which channel to use. For 'a' or
            'A', channel A on the DAC is used. For 'b' or 'B', channel B is
            used. Defaults to 'A'.

    Note:
        Depending on the waveform, the maximum frequency of the function
        genetator is approximately 800 Hz. For very low frequencies, i.e.
        <100 milli-Hertz the function
        generator might also behave erratically.

    Note:
        :py:meth:`dac.DAC.write` is not indended to be used inside the function
        generator `with` context. Unexpected behavior may occur.

    Todo:
        * Fix low-freq function generator behavior.

    Example:

        A typical usage example, in which a sine wave is defined and created using the
        function generator is shown below. The output of the function generator
        defaults to the A channel of the DAC::

            >>> from functiongenerator import FuncGen, Sine
            >>> sine = Sine(Vmin=0, Vmax=1, freq=1)
            >>> with FuncGen(sine): # Turn on the function generator and create a sine.
                    pass # Do something, e.g. measure while the function generator is on.

        This can be made more consise by creating and directly passing the waveform::

            >>> with FuncGen(Sine(Vmin=1, Vmax=1, freq=1)):
                pass

        The function generator defaults to the A-channel of the DAC. The
        B-channel can also be used instead. Note that it is not yet possible to
        use both channels simultaneously::

            >>> with FuncGen(Sine(Vmin=1, Vmax=1, freq=1), channel='B'):
                    pass

    .. _`MCP 4822`: https://www.microchip.com/en-us/product/mcp4822
    .. _`context manager`: https://peps.python.org/pep-0343/
        """

    def __init__(self, waveform: Waveform, channel: str = 'A'):
        global _baton
        global _stop_flag

        _baton = _thread.allocate_lock()
        _stop_flag = False

        self.waveform = waveform

        self._wcr_array = self.waveform._get_wcr_array()

        self.dac_A = not channel in ['B', 'b']

        self._wcr_array = _add_instr_to_wcr_array(self._wcr_array,
                                                  self.dac_A,
                                                  self.waveform._gain_2)

    def __enter__(self):
        try:
            _thread.start_new_thread(_function_generator_thread, (
                self._wcr_array,
                int(self.waveform.freq * 1000),
                self.waveform._N_step))
            # Convert frequency in Hz to mHz

        except OSError:
            raise OSError(
                'Could not start function generator because the function generator is already turned on.\n\n' +
                'Did you turn off the function generator in the code?\n\nResolve this error by fully rebooting the ALPACA.')

        utime.sleep_ms(10)

        return self

    def update(self, waveform: Waveform):
        """

        Args:
            waveform:

        Examples:

            Change to entirely new waveform::

                >>> import time
                >>> import machine
                >>> from functiongenerator import FuncGen, Sine
                >>>
                >>> a0 = machine.ADC(26)
                >>>
                >>> with FuncGen(Sine(Vpp=2, offset=1, freq=1)) as fg:
                        for i in range(250):
                            if not i == 50:
                                fg.update(Triangle(Vpp=2, offset=1, freq=1))

                            print(a0.read_u16()*5.0354e-05)
                            time.sleep(0.01)

            Frequency sweep::
                >>> with FuncGen(Sine(Vpp=2, offset=1, freq=1)) as fg:
                    freq = 1
                    for i in range(250):
                        if not i % 50:
                            freq += 1
                            fg.update(Sine(Vpp=2, offset=1, freq=freq))

                        print(a0.read_u16()*5.0354e-05)
                        time.sleep(0.01)

        """
        # Stop thread
        global _baton
        global _stop_flag

        _stop_flag = True

        _baton.acquire()  # Check if the other thread has stopped
        _baton.release()

        # Update waveform
        self.waveform = waveform

        self._wcr_array = _add_instr_to_wcr_array(
            self.waveform._get_wcr_array(),
            self.dac_A,
            self.waveform._gain_2)

        # Go again
        _stop_flag = False
        self.__enter__()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Stop the function generator on the Alpaca.

        Will halt the function generator on the Alpaca and only returns when this happens succesfully.

        See Also
        --------
        Pico.start_function_generator
        """
        global _baton
        global _stop_flag

        _stop_flag = True

        _baton.acquire()  # Check if the other thread has stopped
        _baton.release()

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

    def _graceful_exit(self):
        # """Method to shut down the function generator gracefully. This prevents 'core 1 in use' errors.
        # """
        self.LED.value(False)  # Status LED off
        self.baton.release()


if __name__ == '__main__':
    pass
