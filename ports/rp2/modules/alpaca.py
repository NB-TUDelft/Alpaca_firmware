"""Module for using the Raspberry Pi Pico in the course NB2211 Electronic Instrumentation
    By: Thijmen de Wolf & Thijn Hoekstra
"""
#       ___       __      .______      ___       ______     ___
#      /   \     |  |     |   _  \    /   \     /      |   /   \
#     /  ^  \    |  |     |  |_)  |  /  ^  \   |  ,----'  /  ^  \
#    /  /_\  \   |  |     |   ___/  /  /_\  \  |  |      /  /_\  \
#   /  _____  \  |  `----.|  |     /  _____  \ |  `----./  _____  \
#  /__/     \__\ |_______|| _|    /__/     \__\ \______/__/     \__\
version = '0.7'  # Module version so students can retrieve their version for debugging


Number = (int, float)

SINE_WAVE_STRINGS = ['Sine', 'sine', 'S', 's']
TRIANGLE_WAVE_STRINGS = ['Triangle', 'triangle', 'T', 't']
SQUARE_WAVE_STRINGS = ['Square', 'square', 'Block', 'block', 'B', 'b']

DC_STRINGS = ['DC', 'dc', 'Flat', 'Analog']
AC_STRINGS = SINE_WAVE_STRINGS + TRIANGLE_WAVE_STRINGS + SQUARE_WAVE_STRINGS


from math import pi

from ulab import numpy as np
from machine import SPI, Pin  # when not running in MicroPython this will throw an error
import utime
from array import array
import _thread





def get_version():
    """Retrieve the version of the `nb2211` module.
    """
    print('You are currently running version ' + version + ' of alpaca.py')

def clear_disk(self):
    import os
    will_clear = False

    utime.sleep(5)

    print('Remove files...')
    for file in os.ilistdir():
        os.remove(file[0])
        print('Removed ', file[0])

    print('Done.')

class FunctionGenerator:
    def __init__(self):
        """Construct an instance of the Function Generator class.
        """
        self.isStopping = False

    def __graceful_exit(self):
        # """Method to shut down the function generator gracefully. This prevents 'core 1 in use' errors.
        # """
        self.LED.value(False)  # Status LED off
        self.baton.release()




class Pico:
    """Functions for the Raspberry Pi Pico connected to the Alpaca board using the Cria.
    """

    def __init__(self):
        """Construct an instance of the Pico class.
        """
        self.isStopping = False


    def __clip_voltages(self, wcr, overdrive: bool = False):  # paramaters in volts
        voltages = list(voltages)
        max_voltage_setting = max_voltage_overdrive if overdrive else max_voltage_tolerated
        for ii in range(len(voltages)):
            if voltages[ii] > max_voltage_setting / 1000:  # convert treshold in millivolts to volts
                voltages[ii] = max_voltage_setting / 1000

            elif voltages[ii] < 0:
                voltages[ii] = 0

        if len(voltages) == 1:  # Special return for single voltage
            return voltages[0]
        else:
            return voltages
        
        def __bake_spi_instructions(self, voltage, DAC_A=True):
        # Based on voltage_to_byte, but also inserts the settings for the MCP4822 DAC into the array of bytes.
        # Expected input: (List of) voltage(s) as float or integer and string specifiying which DAC to use (True = DAC A)
        if type(voltage) is list:
            GAIN_1_SATISFACTORY = True
            for ii in range(len(voltage)):
                voltage[ii] = int(voltage[ii] * 1000)  # Make integers from voltages in millivolts (for speed increase)

                if voltage[ii] > max_voltage_gain_1:  # Check if Gain 1 will suffice
                    GAIN_1_SATISFACTORY = False

            size = len(voltage) * 2  # Size of array of bytes. Each voltage is represented by two bytes
            byte_array = bytearray(size)  # Create array of bytes
            setting = self.__get_setting(DAC_A, GAIN_1_SATISFACTORY)
            # print(setting)
            for ii in range(0, size, 2):  # Start, stop, step. Produces indices 0, 2, 4 ....
                integer = (voltage[ii // 2] * max_int_value) // (
                    max_voltage_gain_1 if GAIN_1_SATISFACTORY else max_voltage_gain_2)
                byte_pair = integer.to_bytes(2,
                                             'big')  # Create pair of bytes to represent voltage and insert into array
                byte_array[ii + 1] = byte_pair[
                    1]  # Last byte contains no setting information and thus can be written directly
                byte_array[ii] = byte_pair[0] | setting  # Write settings for the DAC onto first byte

            return byte_array

    

    def __is_2D_array(self, object):
        result = False
        if type(object) is list:
            if type(object[0]) is list:
                result = True
        return result

    def __is_scalar(self, object):
        return type(object) is float or type(object) is int

    class Function_Generator:

        def __init__(self, shape, *args, overdrive: bool = False):
            self.pico = Pico()
            self.shape = shape
            self.args = args
            self.overdrive = overdrive

        def __enter__(self):
            self.pico.start_function_generator(self.shape, *self.args, overdrive=self.overdrive)
            utime.sleep_ms(100)

        def __exit__(self, exc_type, exc_value, exc_traceback):
            self.pico.stop_function_generator()

    def store_data(self, filename, parameters=None, samples=None):
        """Stores samples taken during a measurement as a text file on the memory of the Raspberry Pi Pico.

        The data is stored in such a way that it is relatively easy to read later on. It is possible to store
        just the samples, but it is also possible to add information about the measurement (or parameters) to
        the text file.

        Parameters
        ----------
        filename : str
            Filename of text file in which to store data. Should include the file extension, e.g. `data.txt`.
        parameters : int or float or list, optional
            Information about the measurement, e.g. a single measurement parameter such as frequency stored as a float
            or multiple parameters stored as a list.
        samples : list
            A list of the samples taken during the measurment. Note that this can also be a nested list, e.g. a 2D array.


        Notes
        -----
        Stores the file as `filename` to the root directory of the Raspberry Pi Pico. Importing the data is best done using the `numpy` package. For example:


        Examples
        --------
        >>> pico = nb2211.Pico()
        >>> pico.store_data('data.txt', samples = [1,2,3]) # Store only three samples
        >>> pico.store_data('data.txt', 24.0, [600, 601, 602]) # Store three samples taken at a frequency of 24.0 Hertz.
        >>> pico.store_data('temperatures.txt', [3600, 12], samples = temperature_list) # Store list 'temperature_list' along with parameters, e.g. 3600 samples taken over the course of 12 days.
        >>> pico.store_data('data.txt', parameters = 10, samples = 3) # Store single parameter and single sample.
        >>> # Storing data and saving data using `numpy`.
        >>> # Saving data
        >>> from nb2211 import Pico
        >>> pico = Pico()
        >>> frequencies = [10, 11, 12]
        >>> data_2D = [[1, 2, 3, 4, 5, 6],
        >>>            [7, 8, 9, 10, 11, 12]]
        >>> pico.store_data('data.txt', parameters=frequencies, samples=data_2D) # With parameters
        >>> #
        >>> # Retrieving data
        >>> import numpy as np
        >>> parameters_stored = True
        >>> data_2D = np.loadtxt('data.txt', skiprows = parameters_stored)
        >>> frequencies = np.loadtxt('data.txt', max_rows = parameters_stored)

        """
        file = open(filename, 'w')

        if parameters is not None:
            # Write parameters
            if self.__is_scalar(parameters):
                file.write(str(parameters) + '\n')

            elif self.__is_2D_array(parameters):
                raise TypeError('Error exporting parameters. Can only export 1D arrays')

            elif type(parameters) is list:
                for item in parameters:
                    file.write(str(item) + ' ')
                file.write('\n')

            else:
                file.close()
                raise TypeError('Please input parameters as either a scalar value or a list.')

        if isinstance(samples, (list, tuple, np.ndarray)):
            for ii, item in enumerate(samples):
                if isinstance(item, (list, tuple, np.ndarray)):
                    samples[ii] = list(np.array(item).flatten())

            samples = list(samples)

        # ~~~~~~~~~~~~~~~~~~~ Write samples
        if self.__is_scalar(samples):
            file.write(str(samples) + '\n')

        elif self.__is_2D_array(samples):
            for row in samples:
                for column in row:
                    file.write(str(column) + ' ')
                file.write('\n')

        elif type(samples) is list:
            for item in samples:
                file.write(str(item) + ' ')
            file.write('\n')

        else:
            file.close()
            raise TypeError('Please input parameters as either a scalar value or a (nested) list.')

        file.flush()
        file.close()
