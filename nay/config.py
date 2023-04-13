import os

CACHEDIR = f"{os.path.expanduser('~')}/.cache/pyaura"

if os.path.exists(CACHEDIR):
    if not os.path.isdir:
        os.mkdir(CACHEDIR)
