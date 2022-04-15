from ulab import numpy as np

def is_number(xx, annotation='an input', strict=True):
    Number = (int, float)
    tt = isinstance(xx, Number)
    if (not tt) and strict:
        raise ValueError('Expected {} to be of type {}'.format(annotation, Number))
    else:
        return tt


class Waveform:

    def __init__(self, V_PP=None, V_P=None, V_min=None, V_max=None, offset=0, freq=None):
        V_min, V_max, freq = self.clean_input(V_PP, V_P, V_min, V_max, offset, freq)
        self.v_min = V_min
        self.v_max = V_max
        self.freq = freq
        self.equation = []

    def __str__(self):
        return ('{} with V_min={} mV, V_max={} mV, and Frequency={}'
                .format(type(self).__name__, self.v_min, self.v_max, self.freq))

    @staticmethod
    def clean_input(V_PP, V_P, V_min, V_max, offset, freq):

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
            raise Exception('Expected a keyword "freq" specifying '
                            'the frequency of the waveform')
        else:
            is_number(freq, annotation='Frequency')

        return V_min, V_max, freq

class Sine(Waveform):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.equation = self.eq

    def eq(self, tt):
        return (0.5 * abs(self.v_max - self.v_min)
                * np.sin(2*np.pi*tt)
                + 0.5 * abs(self.v_max + self.v_min)).astype(int)

if __name__ == '__main__':
    pass
