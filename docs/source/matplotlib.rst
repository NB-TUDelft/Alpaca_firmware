.. _Plotting module:

matplotlib package
==================

Introduction
------------
MicroPython, the programming language for the ALPACA, does not natively support
plotting, as it is intended to interface over a text-based serial interface.
For NB2214 however, it is convenient to be able to visualize the signals that
have been acquired. As the ALPACA is used together with Jupyter, the plots
be shown here.

To make this possible, `nb2214-micropython`  has to work together with a
specialized `kernel`_ for Jupyter, called the `ALPACA kernel`_. With both pieces
of software installed, a subset of the widely-used `matplotlib`_ module is
available for use.

Specifically, plotting can (only) be done using the :py:mod:`matplotlib.pyplot`
module. This is the familiar state-based interface to matplotlib, which
provides a MATLAB-like way of plotting. Figures are then automatically shown
in the cell in Jupyter.

Note that this means that a lot of the extended functionality of `matplotlib`
is unavailable, like subplots. A list of available functions and their usage,
which is similar or identical to that of "normal" `matplotlib` can be found
on this page.

This module does, however, implement a function not seen in the `matplotlib`:
:py:func:`matplotlib.pyplot.liveplot`, which means to do live plotting during a
measurement.

.. _`ALPACA kernel`: https://anaconda.org/twh/alpaca_kernel_2
.. _`kernel`: https://docs.jupyter.org/en/latest/projects/kernels.html
.. _`matplotlib`: https://matplotlib.org/


Submodules
----------

matplotlib.pyplot module
------------------------


.. automodule:: matplotlib.pyplot
    :members:
    :show-inheritance:


Module contents
---------------

.. automodule:: matplotlib
    :members:
    :undoc-members:
    :show-inheritance:
