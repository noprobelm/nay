import os

CACHEDIR = f"{os.path.expanduser('~')}/.cache/nay"

if os.path.exists(CACHEDIR) is False:
    os.mkdir(CACHEDIR)
