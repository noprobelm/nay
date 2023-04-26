import configparser
import pyalpm
from pyalpm import Handle


parser = configparser.ConfigParser(allow_no_value=True)
parser.read("/etc/pacman.conf")

handle = Handle("/", "/var/lib/pacman")
SYNC_PACKAGES = []
INSTALLED = [pkg.name for pkg in handle.get_localdb().pkgcache]

DATABASES = {
    db: handle.register_syncdb(db, pyalpm.SIG_DATABASE_OPTIONAL)
    for db in parser.sections()[1:]
}

for db in DATABASES:
    SYNC_PACKAGES.extend([pkg.name for pkg in DATABASES[db].pkgcache])
