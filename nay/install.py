import os
import subprocess
import shlex
from .console import console
from .package import Package, AURPackage, AURBasic, SyncPackage
import networkx as nx
import concurrent.futures
from typing import Optional


def makepkg(pkg: Package, pkgdir, flags: str) -> None:
    """
    Make a package using 'makepkg'. This is a pure pacman wrapper.

    :param pkg: The package.Package object to make the package from
    :type pkg: package.Package
    :param pkgdir: The full path (exclusive of the package path itself)
    :type pkgdir: str
    :param flags: The flags to pass to 'makepkg' (exlusive of the leading '-')
    :type flags: str

    """
    os.chdir(f"{pkgdir}/{pkg.name}")
    return_code = subprocess.run(shlex.split(f"makepkg -{flags}")).returncode
    if return_code != 0:
        console.print(f"[red] -> error making: {pkg.name}-exit status {return_code}")
        console.print(
            f"[red] Failed to install {pkg.name}. Manual intervention is required"
        )
        quit()


def get_aur_tree(
    *packages: Package, multithread: bool = True, recursive: bool = True
) -> nx.DiGraph:
    """
    Get the AUR tree for a package or series of packages

    :param multithread: Optional parameter indicating whether this function should be multithreaded. Default is True
    :type multithread: Optional[bool]
    :param recursive: Optional parameter indicating whether this function should run recursively. If 'False', only immediate dependencies will be returned. Defaults is True
    :type recursive: Optional[bool]

    :return: A dependency tree of all packages passed to the function
    :rtype: nx.DiGraph
    """
    tree = nx.DiGraph()

    if multithread:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for pkg in packages:
                future = executor.submit(pkg.get_dependency_tree)
                futures.append(future)
        for future in futures:
            tree = nx.compose(tree, future.result())
    else:
        for pkg in packages:
            pkg_tree = pkg.get_dependency_tree()
            tree = nx.compose(tree, pkg_tree)

    if recursive is False:
        return tree

    layers = [layer for layer in nx.bfs_layers(tree, packages)]
    if len(layers) > 1:
        dependencies = layers[0]
        tree = nx.compose(tree, get_aur_tree(*dependencies))

    else:
        return tree

    return tree


def install(
    *packages: Package,
    skip_verchecks: Optional[bool] = False,
    skip_depchecks: Optional[bool] = False,
) -> None:
    """
    Get the AUR tree for a package or series of packages

    :param packages: A package or series of package objects to install
    :type packages: package.Package
    :param skip_verchecks: Optional option to skip version checks for dependencies. Default is False
    :type skip_verchecks: Optinoal[bool]=False
    :param skip_depchecks: Optional option to skip all dependency checks. Default is False
    :type skip_depchecks: Optinoal[bool]=False

    """

    def get_dependency_tree() -> nx.DiGraph:
        tree = nx.DiGraph()
        for pkg in packages:
            deps = pkg.dependencies
            sync_deps = [
                pkg for pkg in pkg.dependencies if isinstance(pkg, SyncPackage)
            ]
            aur_query = requests.get(
                f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={'&arg[]='.join(deps)}"
            ).json()

    def get_sync_explicit() -> list[SyncPackage]:
        """
        Get the sync explicit targets

        :return: A list of the sync explicit packages
        :rtype: list[SyncPackage]
        """
        sync_explicit = [pkg for pkg in packages if isinstance(pkg, SyncPackage)]
        return sync_explicit

    def get_aur_explicit() -> list[AURPackage]:
        """
        Get the aur explicit targets

        :return: A list of the aur explicit packages
        :rtype: list[AurPackage]
        """

        aur_explicit = [pkg for pkg in packages if isinstance(pkg, AURPackage)]
        return aur_explicit

    def get_aur_depends(aur_tree: nx.DiGraph) -> list[AURPackage]:
        """
        Get the aur dependencies from installation targets

        :param aur_tree: The dependency tree of the AUR explicit packages
        :type aur_tree: nx.DiGraph

        :return: A list of the aur dependencies
        :rtype: list[AurPackage]
        """

        aur_depends = []
        for pkg, dep in aur_tree.edges:
            if (
                dep.name
                in aur_tree.get_edge_data(pkg, dep)["dtype"]
                in [
                    "check",
                    "make",
                    "depends",
                ]
            ):
                if dep not in INSTALLED:
                    aur_depends.append(dep)
                elif skip_verchecks is False:
                    if INSTALLED[INSTALLED.index(dep)] != dep:
                        aur_depends.append(dep)

        return aur_depends

    def get_sync_depends(*aur_explicit) -> list[SyncPackage]:
        """
        Get the sync dependencies from AUR explicit targets

        :param aur_explicit: An AURPackage or series of AURPackage objects
        :type aur_tree: package.AURPackage

        :return: A list of the aur dependencies
        :rtype: list[AurPackage]
        """

        sync_depends = []
        for pkg in aur_explicit:
            for dep_type in ["check_depends", "make_depends", "depends"]:
                depends = getattr(pkg, dep_type)
                if isinstance(depends, list):
                    sync_depends.extend([dep for dep in depends if dep in SYNC_PKGLIST])

        sync_depends = get_packages(*sync_depends)
        sync_depends = [dep for dep in sync_depends if dep not in INSTALLED]
        return sync_depends

    def preview_job(
        sync_explicit: Optional[list[SyncPackage]] = None,
        sync_depends: Optional[list[SyncPackage]] = None,
        aur_explicit: Optional[list[AURPackage]] = None,
        aur_depends: Optional[list[AURPackage]] = None,
    ) -> None:

        """
        Print a list of packages to be installed to the terminal

        :param sync_explicit: A list of SyncPackage objects to be explicitly installed
        :type sync_explicit: list[SyncPackage]
        :param sync_depends: A list of SyncPackage dependencies to be installed
        :type sync_depends: list[SyncPackage]
        :param aur_explicit: An list of AURPackage objects to be explicitly installed
        :type aur_explicit: list[AURPackage]
        :param aur_depends: A list of AURPackage dependencies to be installed
        :type aur_depends: list[AURPackage]
        """

        if sync_explicit:
            output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in sync_explicit]
            console.print(
                f"Sync Explicit {len(sync_explicit)}: {', '.join([pkg for pkg in output])}"
            )
        if aur_explicit:
            output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in aur_explicit]
            console.print(
                f"AUR Explicit ({len(aur_explicit)}): {', '.join([pkg for pkg in output])}"
            )

        if aur_depends:
            output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in aur_depends]
            console.print(
                f"AUR Dependency ({len(aur_depends)}): {', '.join([out for out in output])}"
            )

        if sync_depends:
            output = [f"[cyan]{pkg.name}-{pkg.version}" for pkg in sync_depends]
            console.print(
                f"Sync Dependency ({len(sync_depends)}): {', '.join([out for out in output])}"
            )

    def preview_install(*packages: AURPackage) -> None:
        """
        Print an overview of the explicit and depends AUR packages to be installed

        :param packages: A package or series of AURPackage objects to be explicitly installed
        :type packages: package.AURPackage
        """

        install_preview = Table.grid(
            Column("num", justify="right"),
            Column("pkgname", width=35, justify="left"),
            Column("pkgbuild_exists"),
            padding=(0, 1, 0, 1),
        )

        for num, pkg in enumerate(packages):
            # TODO: Fix hardcoded "Build Files Exist" -- I'm not how we'd encounter a scenario where we got here and they don't already exist
            install_preview.add_row(
                f"[magenta]{len(packages) - num}[/magenta]",
                pkg.name,
                "[bright_green](Build Files Exist)",
            )

        console.print(install_preview)

    def prompt_proceed() -> None:
        """Present prompt to proceed with installation"""
        prompt = console.input(
            "[bright_green]==>[/bright_green] Install packages? [Y/n] "
        )
        if not prompt.lower().startswith("y"):
            quit()

    def resolve_dependencies(aur_tree: nx.DiGraph) -> nx.DiGraph:
        """
        Recursively resolve dependencies using nx.DiGraph as starting point

        :param aur_tree: A shallow (i.e. consisting only of explicit AUR targets and their immediate dependencies) networkx DiGraph to be recursively filled out
        :type aur_tree: nx.DiGraph

        :returns: A dependency tree of AUR explicit targets and all descendent dependencies
        :rtype: nx.DiGraph
        """
        aur_tree = nx.compose(aur_tree, get_aur_tree(*aur_depends))
        return aur_tree

    def get_missing_pkgbuild(
        *packages: AURPackage, multithread=True, verbose=False
    ) -> None:
        """
        Get missing PKGBUILD files

        :param packages: An AURPackage or series of AURPackage objects to get PKGBUILD data for
        :type packages: AURPackage
        :param multithread: Optional parameter indicating whether this function should be multithreaded. Default is True
        :type multithread: Optional[bool]
        :param verbose: Optional parameter indicating whether success/failure messages should be verbose. Default is False
        :type verbose: Optional[bool]
        """
        missing = []
        for pkg in packages:
            if not pkg.pkgbuild_exists:
                missing.append(pkg)
            else:
                if verbose:
                    console.print(
                        f"[notify]::[/notify] PKGBUILD up to date, skipping download: [notify]{pkg.name}"
                    )

        if multithread:
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                for num, pkg in enumerate(missing):
                    executor.submit(get_pkgbuild, pkg)
                    if verbose:
                        console.print(
                            f"[notify]::[/notify] ({num+1}/{len(missing)}) Downloaded PKGBUILD: [notify]{pkg.name}"
                        )
        else:
            for num, pkg in enumerate(missing):
                get_pkgbuild(pkg)
                if verbose:
                    console.print(
                        f"[notify]::[/notify] {num+1}/{len(missing)} Downloaded PKGBUILD: [notify]{pkg.name}"
                    )

    def install_aur(aur_tree: nx.DiGraph) -> None:
        """
        Install AUR targets according to their location in the hierarchy:

        - A breadth-first layer search is conducted and reversed to separate the ordered 'tiers' `makepkg` and `pacman -U` need to be executed in in order to result in successful makepkg for successors
        - Each layer is iterated through. For each package in a layer:
          - makepkg 'f' (force makepkg in the event package data already exists) 's' (install missing sync dependencies) 'c' (clean up unecessary data after makepkg finishes)
          - Match the filename pattern for the resulting package's tarball archive (i.e. '<pkgname>-<pkgver>-<architecture>.pkg.tar.zst) and append full path to installation targets
        - After all packages in a layer have been iterated and operated on, batch install using pacman -U
        - Repeat for each layer until all packages have been installed
        """
        layers = [layer for layer in nx.bfs_layers(aur_tree, aur_explicit)][::-1]
        for layer in layers:
            targets = []
            for pkg in layer:
                if skip_depchecks is True:
                    makepkg(pkg, CACHEDIR, "fscd")
                else:
                    makepkg(pkg, CACHEDIR, "fsc")
                pattern = f"{pkg.name}-{pkg.version}-"
                for obj in os.listdir(os.path.join(CACHEDIR, pkg.name)):
                    if pattern in obj and obj.endswith("zst"):
                        targets.append(os.path.join(CACHEDIR, pkg.name, obj))

            subprocess.run(shlex.split(f"sudo pacman -U {' '.join(targets)}"))

    def install_sync() -> None:
        """Install explicit sync packages"""
        if skip_verchecks is True:
            subprocess.run(
                shlex.split(
                    f"sudo pacman -Sd {' '.join([pkg.name for pkg in sync_explicit])}"
                )
            )
        elif skip_depchecks is True:
            subprocess.run(
                shlex.split(
                    f"sudo pacman -Sdd {' '.join([pkg.name for pkg in sync_explicit])}"
                )
            )
        else:
            subprocess.run(
                shlex.split(
                    f"sudo pacman -S {' '.join([pkg.name for pkg in sync_explicit])}"
                )
            )

    sync_explicit = get_sync_explicit()
    aur_explicit = get_aur_explicit()

    if skip_depchecks is True:
        preview_job(sync_explicit=sync_explicit, aur_explicit=aur_explicit)
        get_missing_pkgbuild(*aur_explicit, verbose=True)
        preview_install(*aur_explicit)
        prompt_proceed()

        if aur_explicit:
            aur_tree = nx.DiGraph()
            for pkg in aur_explicit:
                aur_tree.add_node(pkg)
            install_aur(aur_tree)

        if sync_explicit:
            install_sync()
        quit()

    aur_tree = get_aur_tree(*aur_explicit, recursive=False)
    aur_depends = get_aur_depends(aur_tree)
    sync_depends = get_sync_depends(*aur_explicit)
    aur = aur_explicit + aur_depends

    preview_job(
        sync_explicit=sync_explicit,
        aur_explicit=aur_explicit,
        aur_depends=aur_depends,
        sync_depends=sync_depends,
    )
    get_missing_pkgbuild(*aur, verbose=True)
    preview_install(*aur)
    prompt_proceed()
    aur_tree = resolve_dependencies(aur_tree)

    remaining_deps = [pkg for pkg in aur_tree if pkg not in aur]
    get_missing_pkgbuild(*remaining_deps, verbose=False)

    if aur_tree:
        install_aur(aur_tree)
    if sync_explicit:
        install_sync()
