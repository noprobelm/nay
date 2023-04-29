import configparser

import pyalpm
from pyalpm import Handle
from .package import SyncPackage

parser = configparser.ConfigParser(allow_no_value=True)
parser.read("/etc/pacman.conf")

handle = Handle("/", "/var/lib/pacman")
INSTALLED = [SyncPackage.from_pyalpm(pkg) for pkg in handle.get_localdb().pkgcache]

DATABASES = {
    db: handle.register_syncdb(db, pyalpm.SIG_DATABASE_OPTIONAL)
    for db in parser.sections()[1:]
}
