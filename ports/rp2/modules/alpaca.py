# MIT license; Copyright (c) 2024 Thijn Hoekstra

#       ___       __      .______      ___       ______     ___
#      /   \     |  |     |   _  \    /   \     /      |   /   \
#     /  ^  \    |  |     |  |_)  |  /  ^  \   |  ,----'  /  ^  \
#    /  /_\  \   |  |     |   ___/  /  /_\  \  |  |      /  /_\  \
#   /  _____  \  |  `----.|  |     /  _____  \ |  `----./  _____  \
#  /__/     \__\ |_______|| _|    /__/     \__\ \______/__/     \__\
version = '0.8'  # Module version so students can retrieve their version for debugging


def get_version():
    """Retrieve the version of the ALPACA Firmware.
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