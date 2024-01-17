# MIT license; Copyright (c) 2024 Thijn Hoekstra
"""matplotlib.pyplot Module

The `matplotlib.pyplot` module provides a MATLAB-like plotting framework within
MicroPython on the ALPACA. It allows you to create static and live
visualizations in a convenient manner.

Usage:
    To use `matplotlib.pyplot`, import it using:

    >>> import matplotlib.pyplot as plt


    This import convention allows you to access the functions within the module using the alias `plt`.

Examples:
    Create a simple plot using points with x and y values.

    >>> import matplotlib.pyplot as plt
    >>>
    >>> x = [1, 2, 3, 4, 5]
    >>> y = [2, 4, 6, 8, 10]
    >>> plt.plot(x, y) # Create a plot
    >>>
    >>> # Customize the plot
    >>> plt.xlabel('X-axis')
    >>> plt.ylabel('Y-axis')
    >>> plt.title('Simple Plot')


    Key Functions::
        - :py:func:`matplotlib.pyplot.plot`: Create a line or scatter plot.
        - :py:func:`matplotlib.pyplot.xlabel`: Set the label for the x-axis.
        - :py:func:`matplotlib.pyplot.ylabel`: Set the label for the y-axis.
        - :py:func:`matplotlib.pyplot.title`: Set the title of the plot.
        - :py:func:`matplotlib.pyplot.legend`: Add a legend to the plot.
"""
# Format for plot is __PLOT_PREFIX{dictionary of settings}[[x axis], [y axis]]

# Format for attribute is __ATTRIBUTE_PREFIXattribute(parameters)

__PLOT_PREFIX = '%matplotlibdata --'
__LONG_PLOT_PREFIX = '%matplotlibdatalongSTART --'
__LONG_PLOT_SUFFIX = '%matplotlibdatalongEND'
__ATTRIBUTE_PREFIX = '%matplotlib --'  # Prefix to recognize attribute

from ulab import numpy as np
import binascii


def liveplot(*args, labels=None) -> None:
    """Plot live to Jupyter.

    Live plotting can be done by adding the magic command::

        %plot --mode live

    to the top of the code in Jupyter. Incoming data is automatically stored
    and appended to older data. The x-axis of the plot is automatically labeled
    with the time elapsed from the start of the code to the arrival of the
    data in the serial output.

    Args:
        *args: An arbitrary amount of variables to plot.
        labels (list, optional): An optional list of labels, one for each variable to plot.

    Returns:
        None

    Note:
        Due to differences in caching, the live plot flickers when Jupyter
        is run in the Firefox browser. In this case, it is best to use the
        Edge browser instead.

    Examples:
        Using :py:class:`functiongenerator.FuncGen` a sine wave is created,
        measured using the analog input pins of the ALPACA, and plotted live.
        Note the use of a label::

            >>> %plot --mode live
            >>>
            >>> import time
            >>> from machine import ADC, Pin
            >>> import matplotlib.pyplot as plt
            >>> from functiongenerator import FuncGen, Sine
            >>>
            >>> adc = ADC(Pin(26))
            >>>
            >>> with FuncGen(Sine(Vpp=2, offset=0, freq=1)):
                    for _ in range(250):
                        value = adc.read_u16() * 5.0354e-05 # Convert to volts
                        plt.liveplot(value, labels=('voltage', ))

        Two values can also be plotted simulataneously::

            >>> %plot --mode live
            >>>
            >>> adc_1 = ADC(Pin(26))
            >>> adc_2 = ADC(Pin(27))
            >>>
            >>> with FuncGen(Sine(Vpp=2, offset=0, freq=1)):
                for _ in range(250):
                    value_1 = adc_1.read_u16() * 5.0354e-05
                    value_2 = adc_2.read_u16() * 5.0354e-05
                    plt.liveplot(value_1, value_2)

        Two values can also be plotted simulataneously with labels::

            >>> %plot --mode live
            >>>
            >>> with FuncGen(Sine(Vpp=2, offset=0, freq=1)):
                for _ in range(250):
                    value_1 = adc_1.read_u16() * 5.0354e-05
                    value_2 = adc_2.read_u16() * 5.0354e-05
                    plt.liveplot(value_1, value_2, labels=('Vin', 'Vout'))
    """
    if labels:
        if isinstance(labels, list) and len(args) == len(labels):
            pass
        elif isinstance(labels, str) and len(args) == 1:
            pass
        else:
            raise ValueError("Please input a number of labels equal to the amount of data points to plot.")
    else:
        labels = ['l{}'.format(ii) for ii, _ in enumerate(args)]

    out = ['{} {}'.format(label, arg) for arg, label in zip(args, labels)]
    out = ' '.join(out)
    print(out)


def axhline(y=0, xmin=0, xmax=1, **kwargs) -> None:
    """Adds a horizontal line across the axis.

    Args:
        y (float, optional): y position in data coordinates of the horizontal line. Default is 0.
        xmin (float, optional): Should be between 0 and 1, 0 being the far left of the plot, 1 the far right. Default is 0.
        xmax (float, optional): Should be between 0 and 1, 0 being the far left of the plot, 1 the far right. Default is 1.

    Other Parameters:
        **kwargs: Valid keyword arguments are `.Line2D` properties, excluding 'transform'.

    Returns:
        None

    See Also:
        :py:func:`matplotlib.pyplot.hlines` : Add horizontal lines in data coordinates.

    Examples:
        - Draw a thick red hline at 'y' = 0 that spans the xrange:
            >>> axhline(linewidth=4, color='r')
        - Draw a default hline at 'y' = 1 that spans the xrange:
            >>> axhline(y=1)
        - Draw a default hline at 'y' = .5 that spans the middle half of the xrange:
            >>> axhline(y=.5, xmin=0.25, xmax=0.75)
    """
    kwargs['y'] = y
    kwargs['xmin'] = xmin
    kwargs['xmax'] = xmax
    args = ()

    print(__ATTRIBUTE_PREFIX + 'axhline' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def axvline(x=0, ymin=0, ymax=1, **kwargs) -> None:
    """Adds a vertical line across the Axes.

    Parameters:
        x (float, optional): x position in data coordinates of the vertical line. Default is 0.
        ymin (float, optional): Should be between 0 and 1, 0 being the bottom of the plot, 1 the top. Default is 0.
        ymax (float, optional): Should be between 0 and 1, 0 being the bottom of the plot, 1 the top. Default is 1.

    Other Parameters:
        **kwargs: Valid keyword arguments are `.Line2D` properties, excluding 'transform'.

    Returns:
        None

    See Also:
        :py:func:`matplotlib.pyplot.vlines` : Add vertical lines in data coordinates.

    Examples:
        - Draw a thick red vline at *x* = 0 that spans the yrange:
            >>> axvline(linewidth=4, color='r')
        - Draw a default vline at *x* = 1 that spans the yrange:
            >>> axvline(x=1)
        - Draw a default vline at *x* = .5 that spans the middle half of the yrange:
            >>> axvline(x=.5, ymin=0.25, ymax=0.75)
    """
    kwargs['x'] = x
    kwargs['ymin'] = ymin
    kwargs['ymax'] = ymax
    args = ()

    print(__ATTRIBUTE_PREFIX + 'axvline' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def show():
    raise NotImplementedError('matplotlib.pyplot.show is not implemented yet for ALPACA.')


def pause():
    raise NotImplementedError('matplotlib.pyplot.pause is not implemented yet for ALPACA.')


def figure(*args, **kwargs):
    raise NotImplementedError('matplotlib.pyplot.figure is not implemented yet for ALPACA.')


def close(fig=None):
    # """
    # Close a figure window.
    # """
    raise NotImplementedError('matplotlib.pyplot.close is not implemented yet for ALPACA.')


def clf():
    # """Clear the current figure."""
    raise NotImplementedError('matplotlib.pyplot.clf is not implemented yet for ALPACA.')


def draw():
    raise NotImplementedError('matplotlib.pyplot.draw is not implemented yet for ALPACA.')


def savefig(*args, **kwargs):
    raise NotImplementedError('matplotlib.pyplot.savefig is not implemented yet for ALPACA.')


def cla():
    # """Clear the current axes."""
    raise NotImplementedError('matplotlib.pyplot.cla is not implemented yet for ALPACA.')


def subplot(*args, **kwargs):
    # """Add an Axes to the current figure or retrieve an existing Axes."""
    raise NotImplementedError('matplotlib.pyplot.subplot is not implemented yet for ALPACA.')


# Plotting should happen via pyplot
def subplots(nrows=1, ncols=1, *, sharex=False, sharey=False, squeeze=True,
             subplot_kw=None, gridspec_kw=None, **fig_kw):
    # """
    # Create a figure and a set of subplots.
    # """
    raise NotImplementedError(
        'matplotlib.pyplot.subplots is not implemented yet for ALPACA. Instead, please use matplotib.pyplot.plot')


def xlim(*args, **kwargs) -> None:
    """Set the x limits of the current axes.

    Args:
        left (float, optional): The left limit of the x-axis. Default is None.
        right (float, optional): The right limit of the x-axis. Default is None.

    Returns:
        None

    Examples:
        * Set x-axis limits to [0, 10]:

          >>> xlim(0, 10)

        * Adjust the right limit, leaving the left limit unchanged:

          >>> xlim(right=5)
    """
    print(__ATTRIBUTE_PREFIX + 'xlim' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def ylim(*args, **kwargs) -> None:
    """Set the y-limits of the current axes.

    Setting limits turns autoscaling off for the y-axis.

    Args:
        bottom (float, optional): The bottom limit of the y-axis. Default is None.
        top (float, optional): The top limit of the y-axis. Default is None.

    Returns:
        None

    Examples:
        * Set y-axis limits to [-5, 5]:

          >>> ylim(-5, 5)

        * Adjust the top limit, leaving the bottom limit unchanged:

          >>> ylim(top=2)
    """
    print(__ATTRIBUTE_PREFIX + 'ylim' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def xticks(ticks=None, labels=None, **kwargs) -> None:
    """Set the current tick locations and labels of the x-axis.

    Parameters:
        ticks (array-like, optional): The list of xtick locations. Passing an empty list removes all xticks.
        labels (array-like, optional): The labels to place at the given *ticks* locations. This argument can
            only be passed if *ticks* is passed as well.
        **kwargs: `.Text` properties can be used to control the appearance of the labels.

    Returns:
        None
    """


    kwargs['ticks'] = ticks
    kwargs['labels'] = labels
    args = ()

    print(__ATTRIBUTE_PREFIX + 'xticks' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def yticks(ticks=None, labels=None, **kwargs) -> None:
    """Set the current tick locations and labels of the y-axis.

    Parameters:
        ticks (array-like, optional): The list of ytick locations. Passing an empty list removes all yticks.
        labels (array-like, optional): The labels to place at the given *ticks* locations. This argument can
            only be passed if *ticks* is passed as well.
        **kwargs: `.Text` properties can be used to control the appearance of the labels.

    Returns:
        None

    """
    kwargs['ticks'] = ticks
    kwargs['labels'] = labels
    args = ()

    print(__ATTRIBUTE_PREFIX + 'yticks' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def polar(*args, **kwargs):
    # """Make a polar plot."""
    raise NotImplementedError('matplotlib.pyplot.polar is not implemented yet for ALPACA.')


def errorbar(*args, **kwargs):
    raise NotImplementedError('matplotlib.pyplot.errorbar is not implemented yet for ALPACA.')


def grid(*args, **kwargs) -> None:
    """Display grid lines on the current axes.

    Parameters:
        b (bool, optional): Whether to show the grid lines. Default is True.
        which (str or list of str, optional): The grid lines to apply the changes. Options are:
            - 'major' : Show major grid lines.
            - 'minor' : Show minor grid lines.
            - 'both'  : Show both major and minor grid lines.
            Default is 'major'.
        axis (str or None, optional): The axis on which to turn the grid lines. Options are:
            - 'both' : Apply changes to both x and y axes.
            - 'x'    : Apply changes to the x-axis only.
            - 'y'    : Apply changes to the y-axis only.
            - None   : Equivalent to 'both'.
            Default is 'both'.
        **kwargs: Additional keyword arguments controlling the appearance of the grid lines.
                  See the `matplotlib.pyplot.grid` documentation for available options.

    Returns:
        None
    """
    print(__ATTRIBUTE_PREFIX + 'grid' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def hist(*args, **kwargs):
    raise NotImplementedError('matplotlib.pyplot.hist is not implemented yet for ALPACA.')


def hlines(y, xmin, xmax, colors=None, linestyles='solid', label='', data=None, **kwargs) -> None:
    """Add horizontal lines to the current axes.

    Parameters:
        y (float or list of float): y positions in data coordinates of the horizontal lines.
        xmin (float): Should be between 0 and 1, 0 being the far left of the plot, 1 the far right.
        xmax (float): Should be between 0 and 1, 0 being the far left of the plot, 1 the far right.
        colors (str or list of str, optional): Color or list of colors for the lines. Default is None.
        linestyles (str or list of str, optional): Line style or list of line styles. Default is 'solid'.
        label (str, optional): Label for the lines. Default is an empty string.
        **kwargs: Additional keyword arguments controlling the appearance of the lines.
                  See the `matplotlib.pyplot.hlines` documentation for available options.

    Returns:
        None
    """
    kwargs['colors'] = colors
    kwargs['linestyles'] = linestyles
    kwargs['label'] = label
    kwargs['data'] = data

    args = (y, xmin, xmax)

    print(__ATTRIBUTE_PREFIX + 'hlines' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def legend(*args, **kwargs) -> None:
    """Place a legend on the current axes.

    Parameters:
        *args: Variable-length argument list of legend entries. Each entry can be a string or a `~matplotlib.lines.Line2D`.
        loc (str or tuple, optional): The location of the legend. Options are:
            - 'best'   : Automatically choose the optimal location.
            - 'upper right', 'upper left', 'lower left', 'lower right' : Place at the corresponding corner.
            - 'right'  : Place at the right of the plot.
            - 'center left', 'center right' : Place at the center of the left or right side.
            - 'lower center', 'upper center' : Place at the center of the bottom or top side.
            - 'center' : Place at the center of the plot.
            - (float, float) : Place at the specified coordinates.
            Default is 'best'.
        shadow (bool, optional): Whether to draw a shadow behind the legend. Default is False.
        fontsize (int or str, optional): The font size of the legend. If not specified, defaults to the global font size.
        frameon (bool, optional): Whether to draw a frame around the legend. Default is True.
        fancybox (bool, optional): Whether to use a rounded box for the legend. Default is True.
        framealpha (float, optional): The alpha transparency of the legend frame. Default is 1.0 (fully opaque).
        edgecolor (str, optional): The color of the legend frame border. If not specified, uses the Axes' edge color.
        bbox_to_anchor (tuple, optional): The bbox that the legend will be anchored. Only takes effect if `loc` is a string.
            Default is None.
        **kwargs: Additional keyword arguments controlling the appearance of the legend.
                  See the `matplotlib.pyplot.legend` documentation for available options.

    Returns:
        None
    """
    print(__ATTRIBUTE_PREFIX + 'legend' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def loglog(*args, **kwargs):
    raise NotImplementedError(
        'matplotlib.pyplot.loglog is not implemented yet for ALPACA. Please use xscale and yscale.')


def pie(*args, **kwargs):
    raise NotImplementedError('matplotlib.pyplot.pie is not implemented yet for ALPACA.')


def plot(*args, scalex=True, scaley=True, data=None, **kwargs) -> None:
    """Plot y versus x as lines and/or markers.

    Call signatures:
        - plot(y)                  # plot y using x as index array 0..N-1
        - plot(y, 'o')             # plot y using x as index array 0..N-1 and marker 'o'
        - plot(x, y)               # plot x and y using default line style and color
        - plot(x, y, 'bo')         # plot x and y using blue circle markers
        - plot(x, y, 'b-')         # plot x and y using blue solid line
        - plot(y, 'r+', x, 'g-')   # plot y using red plus markers and x using green solid line

    Parameters:
        *args: Variable-length argument list.
            - x (array-like or None): The x-coordinates of the data points. If None, the index of y is used.
            - y (array-like): The y-coordinates of the data points.
            - fmt (str, optional): A format string that controls the appearance of the lines and markers. Default is an empty string.
        scalex (bool, optional): Whether to scale the x-axis. Default is True.
        scaley (bool, optional): Whether to scale the y-axis. Default is True.
        **kwargs: Additional keyword arguments controlling the appearance of the lines and markers.
                  See the `matplotlib.pyplot.plot` documentation for available options.

    Returns:
        None

    Note:
        The `fmt` string can be used to specify line styles, markers, and colors in a concise way.
    """
    # Format for string is {dictionary of settings}[[x axis], [y axis]]
    # xx_uc_byte = np.array(args[0], dtype=np.float).tobytes()

    good_args = _count_axes_in_args(args)

    if len(args) - good_args > 0:  # add fmt string to kwargs if present:
        kwargs['fmt'] = args[2]
    else:
        kwargs['fmt'] = ''

    kwargs['scalex'] = scalex
    kwargs['scaley'] = scaley
    kwargs['data'] = data

    _send_small_plot(kwargs, _get_x_and_y_from_args(args, good_args))

def _count_axes_in_args(args):
    return sum([isinstance(arg, (np.ndarray, list)) for arg in args])


def _get_x_and_y_from_args(args, good_args):
    args = list(args)
    if not isinstance(args[0], (list, np.ndarray, tuple)):
        raise ValueError('x must be an array')

    if good_args == 1:  # Just Y specified
        args[0] = np.array(args[0], dtype=_get_dtype_if_array(args[0]))
        args = args[:1]
        args.append(np.arange(len(args[0]), dtype=_get_dtype_if_array(args[0])))
        args.reverse()

    else:  # X and Y specified
        if not isinstance(args[1], (list, np.ndarray, tuple)):
            raise ValueError('y must be an array')
        if len(args[0]) != len(args[1]):
            raise ValueError('x and y must be the same size')

        args[0] = np.array(args[0], dtype=_get_dtype_if_array(args[0]))
        args[1] = np.array(args[1], dtype=_get_dtype_if_array(args[1]))
        args = args[0:2]

    return args


def _get_dtype_if_array(array):
    if isinstance(array, np.ndarray):
        yy_type = array.dtype
    else:
        yy_type = np.float
    return yy_type


def _send_small_plot(kwargs, args):
    try:
        yy_shape = args[1].shape

        string = '{}{}[[{}], [{}]]{}'.format(__PLOT_PREFIX, kwargs, *_get_plot_data_as_hex(args), yy_shape)
        print(string)
    except MemoryError as e:
        raise MemoryError("It seems that the plot you requested is too big for the ALPACA. Try plotting a subset of "
                          "the points. You might want to do this by slicing a numpy array every N points.") from e


def _get_plot_data_as_hex(args):
    args[0] = args[0].tobytes()
    args[1] = args[1].tobytes()

    args[0] = str(binascii.hexlify(args[0]), 'utf-8')

    args[1] = str(binascii.hexlify(args[1]), 'utf-8')

    return args


def scatter(*args, **kwargs):
    raise NotImplementedError('matplotlib.pyplot.scatter is not implemented yet for ALPACA.')


def violinplot(*args, **kwargs):
    raise NotImplementedError('matplotlib.pyplot.violinplot is not implemented yet for ALPACA.')


def vlines(
        x, ymin, ymax, colors=None, linestyles='solid', label='', *, data=None, **kwargs) -> None:
    """Add vertical lines to the current axes.

    Parameters:
        x (float or list of float): x positions in data coordinates of the vertical lines.
        ymin (float): Should be between 0 and 1, 0 being the bottom of the plot, 1 the top.
        ymax (float): Should be between 0 and 1, 0 being the bottom of the plot, 1 the top.
        colors (str or list of str, optional): Color or list of colors for the lines. Default is None.
        linestyles (str or list of str, optional): Line style or list of line styles. Default is 'solid'.
        label (str, optional): Label for the lines. Default is an empty string.
        **kwargs: Additional keyword arguments controlling the appearance of the lines.
                  See the `matplotlib.pyplot.vlines` documentation for available options.

    Returns:
        None
    """
    args = (x, ymin, ymax)
    kwargs['colors'] = colors
    kwargs['linestyles'] = linestyles
    kwargs['label'] = label
    kwargs['data'] = data

    print(__ATTRIBUTE_PREFIX + 'vlines' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def title(label, fontdict=None, loc=None, pad=None, *, y=None, **kwargs) -> None:
    """Set the title of the current axes.

    Parameters:
        label (str): The title text.
        fontdict (dict, optional): A dictionary containing font properties for the title. Default is None.
        loc (str, optional): The location of the title. Options are:
            - 'center' : Centered title.
            - 'left'   : Left-aligned title.
            - 'right'  : Right-aligned title.
            Default is None, which implies center.
        pad (float, optional): The offset of the title from the top of the axes. Default is None.
        y (float, optional): The y position of the title. Default is None.
        **kwargs: Additional keyword arguments controlling the appearance of the title.
                  See the `matplotlib.pyplot.title` documentation for available options.

    Returns:
        None
    """

    args = (label)

    kwargs['fontdict'] = fontdict
    kwargs['loc'] = loc
    kwargs['pad'] = pad
    kwargs['y'] = y

    print(__ATTRIBUTE_PREFIX + 'title' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def xlabel(xlabel, fontdict=None, labelpad=None, *, loc=None, **kwargs) -> None:
    """Set the label for the x-axis.

    Parameters:
        xlabel (str): The label text for the x-axis.
        fontdict (dict, optional): A dictionary containing font properties for the label. Default is None.
        labelpad (float, optional): The offset of the label from the x-axis. Default is None.
        loc (str, optional): The location of the label. Options are:
            - 'center' : Centered label.
            - 'left'   : Left-aligned label.
            - 'right'  : Right-aligned label.
            Default is None, which implies center.
        **kwargs: Additional keyword arguments controlling the appearance of the x-axis label.
                  See the `matplotlib.pyplot.xlabel` documentation for available options.

    Returns:
        None

    """
    args = (xlabel)

    kwargs['fontdict'] = fontdict
    kwargs['labelpad'] = labelpad
    kwargs['loc'] = loc

    print(__ATTRIBUTE_PREFIX + 'xlabel' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def ylabel(ylabel, fontdict=None, labelpad=None, *, loc=None, **kwargs) -> None:
    """Set the label for the y-axis.

    Parameters:
        ylabel (str): The label text for the y-axis.
        fontdict (dict, optional): A dictionary containing font properties for the label. Default is None.
        labelpad (float, optional): The offset of the label from the y-axis. Default is None.
        loc (str, optional): The location of the label. Options are:
            - 'center' : Centered label.
            - 'left'   : Left-aligned label.
            - 'right'  : Right-aligned label.
            Default is None, which implies center.
        **kwargs: Additional keyword arguments controlling the appearance of the y-axis label.
                  See the `matplotlib.pyplot.ylabel` documentation for available options.

    Returns:
        None

    """
    args = (ylabel)

    kwargs['fontdict'] = fontdict
    kwargs['labelpad'] = labelpad
    kwargs['loc'] = loc

    print(__ATTRIBUTE_PREFIX + 'ylabel' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def xscale(value, **kwargs) -> None:
    """Set the scale of the x-axis.

    Parameters:
        value (str): The scale type for the x-axis. Available options:
            - 'linear' : Linear scale.
            - 'log'    : Logarithmic scale.
            - 'symlog' : Symmetrical log scale.
            - 'logit'  : Logit scale.
        **kwargs: Additional keyword arguments controlling the scale of the x-axis.

    Returns:
        None
    """
    args = value

    print(__ATTRIBUTE_PREFIX + 'xscale' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')


def yscale(value, **kwargs) -> None:
    """
    Set the scale of the y-axis.

    Parameters:
        value (str): The scale type for the y-axis. Available options:
            - 'linear' : Linear scale.
            - 'log'    : Logarithmic scale.
            - 'symlog' : Symmetrical log scale.
            - 'logit'  : Logit scale.
        **kwargs: Additional keyword arguments controlling the scale of the y-axis.

    Returns:
        None

    """
    args = value

    print(__ATTRIBUTE_PREFIX + 'xscale' + '(' + str(args).replace('(', '').replace(')', '') + ', ' + str(kwargs) + ')')
