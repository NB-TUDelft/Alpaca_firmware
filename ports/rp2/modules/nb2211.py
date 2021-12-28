""" Module for using the Raspberry Pi Pico in the course NB2211 Electronic Instrumentation
    By: Thijmen de Wolf & Thijn Hoekstra
"""

version = "0.6" # Module version so students can retrieve their version for debugging

# This module will be imported on both machines running CPython and MicroPython. If IS_PICO is true, 
# then the module has been imported on a device running MicroPython, i.e. the Raspberry Pi Pico
from math import pi
try:
    from machine import SPI, Pin # when not running in MicroPython this will throw an error
    import utime
    from array import array
    import _thread
    IS_PICO = True
except: 
    IS_PICO = False  
    #raise ImportError("Make sure that this module is imported into MicroPython, not CPython")

# Constant declarations for code ran on MicroPython. This is not supported by CPython and thus needs to be run only
# when the import happens on the PICO
if IS_PICO:
    max_voltage_tolerated = const(3300) # Max voltage the DAC is allowed to produce. Set to 3300 mV in to protect against the DAC frying the Pico
    max_voltage_overdrive = const(4096) # Max voltage the DAC can  produce. Will be used in overdrive mode

    pin_number_MOSI = const(11)
    pin_number_SCK = const(10)
    pin_number_CS = const(13)
    pin_number_LDAC = const(12)

    max_int_value = const(4096) # Integer value, that when sent to the DAC over SPI will produce the largest voltage. 4096 for the MCP4822
    max_voltage_gain_2 = const(4095) # Max voltage the DAC can produce measured in millivolts. 4095 for the MCP4822 when the gain has been set to 2.
    max_voltage_gain_1 = const(2047) # Max voltage the DAC can produce measured in millivolts. 4095 for the MCP4822 when the gain has been set to 2.
    delay_native = const(100) # 114 us write delay, whatever pause we want between writes in our program has to be larger than this

    setting_A2 = const(16)  # MCP4822 setting byte for DAC A, Gain 2
    setting_A1 = const(48)  # MCP4822 setting byte for DAC A, Gain 1
    setting_B2 = const(144) # MCP4822 setting byte for DAC B, Gain 2
    setting_B1 = const(176) # MCP4822 setting byte for DAC B, Gain 1

    fudge_factor = const(3) # "Safety factor" for calculating how many sample points for DAC wave generation. More is rougher.

def get_version():
    """Retrieve the version of the `nb2211` module.
    """
    print("You are currently running version " + version + " of nb2211.py")

class Pico:
    """Functions for the Raspberry Pi Pico connected to the Alpaca board using the Cria.
    """
    
    # REMOVED FOR MORE CONCISE DOCUMENTATION
    #Attributes
    #----------
    #isStopping : bool
    #    When true, signals that the function generator should halt.
    #baton : Lock
    #    Lock object used to keep the secondary function generator thread in sync with the rest of the program (and vice versa).
    #LED : Pin
    #    Pin object used to light up the built-in LED on the Raspberry Pi Pico. Signals that the function generator is on.

    #Methods
    #-------
    ##start_function_generator(frequency, shape, low, high)
    #    Start the function generator.
    #stop_function_generator()
    #    Stop the function generator.
    #def store_data(filename, parameters = None, samples = None)
    #    Store data to a file formatted such that it is easy to read with the `nb2211` module.    

    def __init__(self): 
        """Construct an instance of the Pico class.
        """
        self.isStopping = False

    def clear_disk(self):
        import os
        will_clear = False
        while True:
            response = input("Remove all files on disk? Please respond with Yes (Y) or No (N):\n Y/[N] ")
            
            if response in ("Y","y"):
                will_clear = True
                break
            elif response in ("","n","N"): # Default to No when enter is pressed
                print("Escaped. Did not remove files")
                break
            else:
                print("Please enter a valid input: Y/[N]")

        if will_clear:
            print("Remove files...")
            for file in os.ilistdir():
                os.remove(file[0])
                print("Removed ", file[0])
                
        print("Done.")

    def __graceful_exit(self):
        #"""Method to shut down the function generator gracefully. This prevents "core 1 in use" errors.
        #"""
        self.LED.value(False) # Status LED off
        self.baton.release() 

    def __get_setting(self, DAC_A, GAIN_1_SATISFACTORY): # Convert desired settings to an integer that corresponds to a correct settings byte
        #"""Converts a boolean input on the desired setting for the MCP4822 DAC into a byte that the device can understand.
        #"""
        if DAC_A and GAIN_1_SATISFACTORY: return setting_A1
        elif DAC_A and not GAIN_1_SATISFACTORY: return setting_A2
        elif not DAC_A and GAIN_1_SATISFACTORY: return setting_B1
        else: return setting_B2

    def __bake_spi_instructions(self, voltage, DAC_A = True): 
        # Based on voltage_to_byte, but also inserts the settings for the MCP4822 DAC into the array of bytes.
        # Expected input: (List of) voltage(s) as float or integer and string specifiying which DAC to use (True = DAC A)
        if type(voltage) is list: 
            GAIN_1_SATISFACTORY = True
            for ii in range(len(voltage)):
                voltage[ii] = int(voltage[ii]*1000) # Make integers from voltages in millivolts (for speed increase)
                
                if voltage[ii] > max_voltage_gain_1: # Check if Gain 1 will suffice
                    GAIN_1_SATISFACTORY = False

            size = len(voltage) * 2  # Size of array of bytes. Each voltage is represented by two bytes
            byte_array = bytearray(size) # Create array of bytes
            setting = self.__get_setting(DAC_A, GAIN_1_SATISFACTORY)
            #print(setting)
            for ii in range(0,size,2): # Start, stop, step. Produces indices 0, 2, 4 ....
                integer = (voltage[ii//2] * max_int_value) // (max_voltage_gain_1 if GAIN_1_SATISFACTORY else max_voltage_gain_2)
                byte_pair = integer.to_bytes(2, 'big') # Create pair of bytes to represent voltage and insert into array
                byte_array[ii+1] = byte_pair[1] # Last byte contains no setting information and thus can be written directly
                byte_array[ii] = byte_pair[0] | setting # Write settings for the DAC onto first byte
                
            return byte_array

        else: # Single value
            voltage = int(voltage * 1000)
            GAIN_1_SATISFACTORY = voltage < max_voltage_gain_1
            byte_array = bytearray(2)
            integer = (voltage * max_int_value) // (max_voltage_gain_1 if GAIN_1_SATISFACTORY else max_voltage_gain_2)
            byte_pair = integer.to_bytes(2, 'big')
            byte_array[1] = byte_pair[1]
            byte_array[0] = byte_pair[0] | self.__get_setting(DAC_A, GAIN_1_SATISFACTORY)

            return byte_array

    def __clip_voltages(self, *voltages, overdrive: bool = False): # paramaters in volts
        voltages = list(voltages)
        max_voltage_setting = max_voltage_overdrive if overdrive else max_voltage_tolerated
        for ii in range(len(voltages)):
            if voltages[ii] > max_voltage_setting / 1000: #convert treshold in millivolts to volts
                voltages[ii] = max_voltage_setting / 1000

            elif voltages[ii] < 0:
                voltages[ii] = 0

        if len(voltages) == 1: # Special return for single voltage
            return voltages[0]
        else:
            return voltages

    def __setup_spi(self): 
        # returns SPI objects. Used to so objects can be kept locally rather than globally.
        # Rationale: Local objects can be operated upon more quickly in MicroPython
        spi = SPI(1,
                  baudrate=1_000_000, #20_000_000,
                  polarity=1,
                  phase=1,
                  bits = 8,
                  firstbit = SPI.MSB,
                  sck=Pin(pin_number_SCK),
                  mosi=Pin(pin_number_MOSI),
                  miso=None)
        CS = Pin(pin_number_CS, Pin.OUT)
        LDAC = Pin(pin_number_LDAC, Pin.OUT)
        
        return spi, CS, LDAC

    def __function_generator_thread(self, shape, args_list):
          # Setup
        self.LED = Pin(25, Pin.OUT) 
        self.LED.value(True)
        self.baton.acquire() 
        self.isStopping = False

        spi, CS, LDAC = self.__setup_spi()
        if len(args_list) == 4 and not (shape in ["DC", "Flat", "Analog"]):
            frequency, low, high, overdrive = args_list
        elif len(args_list) == 2 and shape in ["DC", "Flat", "Analog"]:
            # Setup
            CS.value(True)
            LDAC.value(False)
            
            DC, overdrive = args_list
            DC = self.__clip_voltages(DC, overdrive = overdrive)
            buffer = self.__bake_spi_instructions(DC)
         
            CS.value(False)
            spi.write(buffer)
            CS.value(True)

            print('W-DC') # Done writing
            self.__graceful_exit()
            return
        else:
            print("Error when starting function generator. When requesting a DC voltage, please enter only one value." + 
            "When requesting any other function, please enter three values")
            self.__graceful_exit()
            return

        # Continuation of AC write
        low, high = self.__clip_voltages(low, high, overdrive = overdrive) # clip

        # Find suitable sine wave, same analysis is also used for triangle wave
        # 114 us write delay, whatever pause we want between writes in our program has to be larger than this
        resolution = int(1e6 / frequency / (fudge_factor*delay_native)) # order of magnitude analysis to find nice wave shape
        
        if resolution > 300:
            resolution = 300

        if resolution < 10: # limit where we sacrifce sine "niceness" for speed
            resolution = 10

        if resolution % 2:
            resolution += 1 #only keep even number for convenience for triangle wave

        if shape in ["Sine", "sine", "S", "s"]:
            from math import sin

            values = [None] * resolution
            for ii in range(resolution):
              points = ii/(resolution)*2*pi  #sin has a period of 2pi
              values[ii] = (sin(points) + 1 ) * 0.5 * abs(high - low) + low
          
            byte_array = self.__bake_spi_instructions(values)

        elif shape in ["Triangle", "triangle", "T", "t"]:
            values = [None] * resolution

            length = resolution // 2 
            #create the upwards part of the slope
            values[:length+1] = [low + x*(high-low)/length for x in range(length+1)]
            #create the downwards part of the slope
            values[length+1:] = [high - (x+1)*(high-low)/length for x in range(length-1)]
            byte_array = self.__bake_spi_instructions(values)

        elif shape in ["Square", "square", "Block", "block", "B", "b"]:
            #use square wave shape,  for which a resolution of 2 is always sufficient
            resolution = 2 
            values = [high, low]
            byte_array = self.__bake_spi_instructions(values)

        else:
            print('Error when finding correct waveform in memory. Did you request a valid wave? Examples are: Sine, Triangle', 'Square')
            self.__graceful_exit()
            return

        # WRITE ------------------------
        delay_us = int(1e6 / frequency / resolution) # delay in loop (in microseconds) necessary to generate wave
        delay_us = delay_us - 114
        if delay_us < 0:
            delay_us = 0

        #print("Resolution = " + str(resolution) +" points. DAC update delay (us) = "+ str(delay_us))

        target = (2* resolution - 2)
        checking_interval = int(frequency) if int(frequency) > 0 else 1
                
        mv = memoryview(byte_array)

        CS.value(True)
        LDAC.value(False)

        buffer = bytearray([0,0])
        ii = 0 # Counts points written
        jj = 0 # Counts periods written
        while True:
            # PREPARE ---------------------------    
            CS.value(False)
            buffer[0] = mv[ii]
            buffer[1] = mv[ii+1]

            # WRITE POINT -----------------------------
            spi.write(buffer)
            CS.value(True) # Datasheet: Chip select to end before LDAC pulse

            utime.sleep_us(delay_us)

            if ii == target: # For looping the wave shape
                ii = 0
                jj += 1
            else:
                ii += 2

            if jj == checking_interval: # For checking whether or not to stop every couple periods
                if self.isStopping:
                    break
                else:
                    jj = 0

        print('W-AC') # Done writing
        self.__graceful_exit()
        return 

    def start_function_generator(self, shape, *args, overdrive: bool = False):
        """Start the function generator on the Alpaca

        Generate an electronic signal using the DAC output A.

        Parameters
        ----------
        shape : {"sine", "triangle", "square", "DC"}
            Specifies what type of signal to generate. `"sine"` will yield a sine wave, `"triangle"` will yield
            a symmetric triangle wave, `"square"` will wield a square wave, and `"DC"` will yield a constant voltage.
        *args : iterable
            Additional arguments. When `shape` is set to `"DC"`, enter only the value in volts.
            When `shape` is set to an AC signal, three parameters are needed. These are, `frequency`, `low` and `high`.
            `frequency` sets the target frequency of the signal (in Hertz). `low` sets the lowest voltage of the periodic signal.
            `high` sets the peak voltage of the periodic signal.
 
        See Also
        --------
        Pico.stop_function_generator
        
        Notes
        -----
        The MCP4822 DAC on board the Alpaca has a voltage range of 0 to 4.095 volts. Note that this means that valid entries
        for signals are non-negative and below 4.095 volts for the complete period. To protect the Raspberry Pi Pico from an overvolt, this range is software-
        limited between 0 and 3.3 volts.
        Examples
        --------
        >>> start_function_generator("DC", 2) # Constant voltage of 2 volts from DAC A
        >>> start_function_generator("sine", 50, 0, 4) # Sine wave with VPP of 4 volts and DC offset of +2 volts at a frequency of 50 Hz
        """
        self.baton = _thread.allocate_lock()
        args = tuple(list(args) + [overdrive])
        try:
            _thread.start_new_thread(self.__function_generator_thread, (shape, args))
        except OSError:
            raise OSError("Could not start function generator because the function generator is already turned on.\n\n"+
            "Did you turn off the function generator in the code?\n\nResolve this error by fully rebooting the ALPACA.")
    
    def stop_function_generator(self):
        """Stop the function generator on the Alpaca.

        Will halt the function generator on the Alpaca and only returns when this happens succesfully.
        
        See Also
        --------
        Pico.start_function_generator
        """
        self.isStopping = True 

        self.baton.acquire() # Check if the other thread has stopped
        self.baton.release()

        spi, CS, LDAC = self.__setup_spi()

        CS.value(True)
        LDAC.value(False)
        
        CS.value(False)
        spi.write(b'\t\x00') # Shutdown DAC B
        CS.value(True)

        CS.value(False)
        spi.write(b'\x01\x00') # Shudown DAC A
        CS.value(True)

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
            self.pico.start_function_generator(self.shape, *self.args, overdrive = self.overdrive)
            utime.sleep_ms(100)

        def __exit__(self, exc_type, exc_value, exc_traceback):
            self.pico.stop_function_generator()


    def store_data(self, filename, parameters = None, samples = None):
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
        >>> pico.store_data("data.txt", samples = [1,2,3]) # Store only three samples
        >>> pico.store_data("data.txt", 24.0, [600, 601, 602]) # Store three samples taken at a frequency of 24.0 Hertz.
        >>> pico.store_data("temperatures.txt", [3600, 12], samples = temperature_list) # Store list 'temperature_list' along with parameters, e.g. 3600 samples taken over the course of 12 days.
        >>> pico.store_data("data.txt", parameters = 10, samples = 3) # Store single parameter and single sample.
        >>> # Storing data and saving data using `numpy`.
        >>> # Saving data
        >>> from nb2211 import Pico
        >>> pico = Pico()
        >>> frequencies = [10, 11, 12]
        >>> data_2D = [[1, 2, 3, 4, 5, 6],
        >>>            [7, 8, 9, 10, 11, 12]]
        >>> pico.store_data("data.txt", parameters=frequencies, samples=data_2D) # With parameters
        >>> #
        >>> # Retrieving data
        >>> import numpy as np
        >>> parameters_stored = True
        >>> data_2D = np.loadtxt("data.txt", skiprows = parameters_stored)
        >>> frequencies = np.loadtxt("data.txt", max_rows = parameters_stored)

        """
        file = open(filename, "w")

        if parameters is not None:
            # Write parameters
            if self.__is_scalar(parameters):
                file.write(str(parameters) + "\n")

            elif self.__is_2D_array(parameters):
                raise TypeError("Error exporting parameters. Can only export 1D arrays")

            elif type(parameters) is list:
                for item in parameters:
                    file.write(str(item) + " ")
                file.write("\n")

            else:
                file.close()
                raise TypeError("Please input parameters as either a scalar value or a list.")

        # ~~~~~~~~~~~~~~~~~~~ Write samples
        if self.__is_scalar(samples):
            file.write(str(samples) + "\n")

        elif self.__is_2D_array(samples):
            for row in samples:
                for column in row:
                    file.write(str(column) + " ")
                file.write("\n")

        elif type(samples) is list:
            for item in samples:
                file.write(str(item) + " ")
            file.write("\n")

        else:
            file.close()
            raise TypeError("Please input parameters as either a scalar value or a (nested) list.")

        file.flush()
        file.close()
