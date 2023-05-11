import configparser
import pyalpm
from pyalpm import Handle
from .package import SyncPackage, AURPackage


class Database:
    def __init__(self, root: str, dbpath: str):
        handle = Handle(root, dbpath)
        self.db = handle.get_localdb()


class Local(Database):
    def __init__(self, root: str, dbpath: str):
        handle = Handle(root, dbpath)
        self.db = handle.get_localdb()

    def get_packages(
        self,
        *names: str,
    ) -> list[SyncPackage]:
        """
        Get packages based on passed string or strings. Invalid results are ignored/dropped from return result.

        :param pkg_names: A string or series of strings for which SyncPackage or AURPackage objects will be fetched
        :type pkg_names: str
        :param verbose: Flag to induce verbosity. Defaults to False
        :type verbose: bool


        :returns: Package list based on input
        :rtype: list[Package]
        """
        names = set(names)
        packages = []
        for name in names:
            pkg = self.db.get_pkg(name)
            if pkg:
                packages.append(SyncPackage.from_pyalpm(pkg))

        return packages


class Sync(Database, dict):
    def __init__(self, root: str, dbpath: str, config: str):
        self.root = root
        self.dbpath = dbpath

        parser = configparser.ConfigParser(allow_no_value=True)
        parser.read(config)

        handle = Handle(self.root, self.dbpath)
        super().__init__(
            {
                db: handle.register_syncdb(db, pyalpm.SIG_DATABASE_OPTIONAL)
                for db in parser.sections()[1:]
            }
        )

    def search(self, query: str) -> list:
        """
        Query the database and AUR. Exact matches will always be presented first despite specified sort order

        :param query: The search query to use
        :type query: str
        :param sortby: The package.Package attribute to sort results by

        :returns: A dictionary of integers representing index to package results
        :rtype: dict[int, Package]
        """

        packages = []

        for db in self:
            packages.extend(
                [SyncPackage.from_pyalpm(pkg) for pkg in self[db].search(query)]
            )

        return packages

    def get_packages(
        self,
        *names: str,
    ) -> list[SyncPackage]:
        """
        Get packages based on passed string or strings. Invalid results are ignored/dropped from return result.

        :param pkg_names: A string or series of strings for which SyncPackage or AURPackage objects will be fetched
        :type pkg_names: str
        :param verbose: Flag to induce verbosity. Defaults to False
        :type verbose: bool


        :returns: Package list based on input
        :rtype: list[Package]
        """
        names = set(names)
        packages = []
        for db in self:
            for name in names:
                pkg = self[db].get_pkg(name)
                if pkg:
                    packages.append(SyncPackage.from_pyalpm(pkg))
                    continue

        return packages

    def get_depends(self, *packages: list[AURPackage]) -> list[SyncPackage]:
        """
        Get the sync dependencies from AUR explicit targets

        :param aur_explicit: An AURPackage or series of AURPackage objects
        :type aur_tree: package.AURPackage

        :return: A list of the aur dependencies
        :rtype: list[AurPackage]
        """

        sync_depends = []
        for pkg in packages:
            for dep_type in ["check_depends", "make_depends", "depends"]:
                sync_depends.extend(self.get_packages(*getattr(pkg, dep_type)))

        return sync_depends
