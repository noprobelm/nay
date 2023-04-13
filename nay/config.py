import os

CACHEDIR = f"{os.path.expanduser('~')}/.cache/nay"

if os.path.exists(CACHEDIR):
    if not os.path.isdir:
        os.mkdir(CACHEDIR)
