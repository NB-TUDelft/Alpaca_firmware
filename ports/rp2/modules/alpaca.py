# MIT license; Copyright (c) 2024 Thijn Hoekstra
"""Module with functions for maintaining the ALPACA.
"""
version = '0.8'  # Module version so students can retrieve their version for debugging

import os
import utime


def get_version():
    """Retrieve the current version of the ALPACA Firmware.

    Useful for debugging.
    """
    print('You are currently running version ' + version + ' of alpaca.py')


def clear_disk(self):
    """Removes all files on the ALPACA.

    Wipes all files on the drive of the ALPACA. Note that the firmware
    (MicroPython) is kept. Useful for resetting the ALPACA if it is bloated
    by files saved on disk.

    Warning:
        This procedure cannot be undone!
    """

    utime.sleep(5)

    print('Remove files...')
    for file in os.listdir():
        os.remove(file[0])
        print('Removed ', file[0])

    print('Done.')
