# MIT license; Copyright (c) 2024 Thijn Hoekstra

"""Direct control of the digital-to-analog converted.

This module contains a class for directly controlling the output of the `MCP 4822`_
Digital-to-Analog Coverter (DAC). This is in contrast to the
:py:class:`functiongenerator.FuncGen` class, which modulates the DAC in the
background.

Examples:

    Acessing the A-channel of the DAC and setting it to 1 volt:

    >>> from dac import DAC
    >>>
    >>> dac_a = DAC('A') # Create a DAC object
    >>>
    >>> dac_a.write(1)

    Creating an array of voltages from 0 to 3.3 volts with steps of 250
    milli-volts to set the DAC to and sampling after the
    DAC changes::

        >>> import time
        >>> import machine
        >>> import numpy as np
        >>> from dac import DAC
        >>>
        >>> dac_a = DAC('A')
        >>> voltages = np.arange(0, 3.3, 0.25)
        >>> for voltage in voltages:
                dac_a.write(voltage)

                time.sleep(0.1)

                print(a0.read_u16() * 5.0354e-05) # Convert to volts

        >>> dac_a.off() # Turning off the DAC after use

Note:
    Consider using :py:meth:`functiongenerator.Waveform.get_voltages` to create
    an array of voltages to pass to the DAC.

.. _`MCP 4822`: https://www.microchip.com/en-us/product/mcp4822
"""


from functiongenerator import DC, _add_instr_to_wcr_array, _setup_spi


class DAC:
    """A class representing the digital-to-analog converter.

    Class for controlling the digital-to-analog converter on the ALPACA.

    Attributes:
        dac_A (bool): A boolean specifying if the DAC A channel is used
            (rather than DAC B).
        unsafe (bool): A boolean indicating whether the waveform is allowed
            to exceed a maximum voltage of 3.3 volts (the maximum voltage
            of the analog inputs on the `Raspberry Pi Pico`_ on the ALPACA).
            Defaults to False.

    Args:
        channel (str): A string specifying which channel to use. For 'a' or
            'A', channel A on the DAC is used. For 'b' or 'B', channel B is
            used. Defaults to 'A'.
        unsafe (bool): A boolean indicating whether the waveform is allowed
            to exceed a maximum voltage of 3.3 volts (the maximum voltage
            of the analog inputs on the `Raspberry Pi Pico`_ on the ALPACA).
            Defaults to False.

    Note:
        By default, the voltage range of the DAC is limited to 0-3.3 V,
        the range that is safe for input to the analog input pins of the
        `Raspberry Pi Pico`_ in the ALPACA. Voltages of a waveform that fall
        outside this range are clipped, i.e. set to either 0 or 3.3 V. This
        behavior can be turned off using the `unsafe` parameter, increasing
        the range of the waveform to that of the `MCP 4822`_ DAC, i.e. to
        0-4.096 V. Note that in both cases, this clipping will occur
        silently.

    .. _`Raspberry Pi Pico`: https://www.raspberrypi.com/products/raspberry-pi-pico/
    """

    def __init__(self, channel: str = 'A', unsafe: bool = False):
        self.dac_A = not channel in ['B', 'b']
        self.unsafe = unsafe

    def write(self, voltage: float) -> None:
        """Sets the digital-to-analog converter to a voltage.

        Args:
            voltage (float): Voltage to se the DAC to:

        Returns:
            None

        """
        waveform = DC(voltage, unsafe=self.unsafe)

        wcr_array = _add_instr_to_wcr_array(waveform._get_wcr_array(),
                                            self.dac_A,
                                            waveform._gain_2)

        spi, CS, LDAC = _setup_spi()

        mv = memoryview(wcr_array)

        CS.value(True)
        LDAC.value(False)

        buffer = bytearray([0, 0])

        # PREPARE ---------------------------
        CS.value(False)
        buffer[0] = mv[0]
        buffer[1] = mv[1]

        # WRITE POINT -----------------------------
        spi.write(buffer)
        CS.value(True)  # Datasheet: Chip select to end before LDAC pulse

        return 1

    def off(self):
        """Turns off the digital-to-analog converter.

        It is recommended to run this after use.
        """
        spi, CS, LDAC = _setup_spi()

        CS.value(True)
        LDAC.value(False)

        if self.dac_A:
            CS.value(False)
            spi.write(b'\x01\x00')  # Shudown DAC A
            CS.value(True)
        else:
            CS.value(False)
            spi.write(b'\t\x00')  # Shutdown DAC B
            CS.value(True)

    def __del__(self):
        self.off()


if __name__ == '__main__':
    pass
