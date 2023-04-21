import os

CACHEDIR = f"{os.path.expanduser('~')}/.cache/nay"

if not os.path.exists(CACHEDIR):
    os.mkdir(CACHEDIR)
