from functiongenerator import DC, _add_instr_to_wcr_array, _setup_spi


class DAC:

    def __init__(self, channel: str = 'A'):
        self.dac_A = not DAC in ['B', 'b']

    def write(self, voltage):
        waveform = DC(voltage)

        wcr_array = _add_instr_to_wcr_array(waveform.get_wcr_array(),
                                            self.dac_A,
                                            waveform.gain_2)

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



if __name__ == '__main__':
    pass
