from functiongenerator import DC, _add_instr_to_wcr_array, _setup_spi


class DAC:

    def __init__(self):
        pass

    def write(self, voltage_a: float = None, voltage_b: float = None):

        if voltage_a is None and voltage_b is None:
            raise ValueError('Must specify either a voltage_a or voltage_b')
        elif voltage_a is not None and voltage_b is None:
            # Just use DAC A
            voltages = [voltage_a]
            selectors = [True]
        elif voltage_b is not None and voltage_a is None:
            # Just use DAC B
            voltages = [voltage_b]
            selectors = [False]
        else:
            # Use both DACs
            voltages = [voltage_a, voltage_b]
            selectors = [True, False]

        spi, CS, LDAC = _setup_spi()
        LDAC.value(True) # Set LDAC to HIGH to keep latch closed

        for voltage, sele in zip(voltages, selectors):
            waveform = DC(voltage)

            wcr_array = _add_instr_to_wcr_array(waveform.get_wcr_array(),
                                                sele,
                                                waveform.gain_2)
            mv = memoryview(wcr_array)

            CS.value(True)


            buffer = bytearray([0, 0])

            # PREPARE ---------------------------
            CS.value(False)
            buffer[0] = mv[0]
            buffer[1] = mv[1]

            # WRITE POINT -----------------------------
            spi.write(buffer)
            CS.value(True)  # Datasheet: Chip select to end before LDAC pulse

        LDAC.value(False) # Release latch to update simultaneously

        return 1



if __name__ == '__main__':
    pass
