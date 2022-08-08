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


def __is_2D_array(self, object):
    result = False
    if type(object) is list:
        if type(object[0]) is list:
            result = True
    return result

def __is_scalar(self, object):
    return type(object) is float or type(object) is int

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
