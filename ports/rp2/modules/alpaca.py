"""Module for using the Raspberry Pi Pico in the course NB2211 Electronic Instrumentation
    By: Thijmen de Wolf & Thijn Hoekstra
"""

import os

_VERSION = '0.8'  # Module version so students can retrieve their version


def get_version():
    """Retrieve the version of the `nb2211` module.
    """
    print('You are currently running version ' + _VERSION + ' of alpaca.py')


def clear_disk(self):
    print('Remove files...')
    for file in os.listdir():
        os.remove(file[0])
        print('Removed ', file[0])

    print('Done.')
