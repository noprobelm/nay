import os
import shlex
import subprocess

from .operations import Operation


class GetPKGBUILD(Operation):
    def run(self):
        cwd = os.getcwd()
        sync_explicit = []
        targets = list(set(self.targets))
        for db in self.sync:
            for target in targets:
                pkg = self.sync[db].get_pkg(target)
                if pkg:
                    sync_explicit.append(pkg)
                    targets.pop(targets.index(target))

        aur_explicit = self.aur.get_packages(*targets)
        for pkg in aur_explicit:
            if pkg.name in targets:
                targets.pop(targets.index(pkg.name))

        missing = targets

        total = len(sync_explicit) + len(aur_explicit)
        for num, pkg in enumerate(sync_explicit):
            num += 1
            subprocess.run(shlex.split(f"asp checkout {pkg.name}"), capture_output=True)
            self.console.notify(
                f"({num}/{total}) Downloaded PKGBUILD from ABS: [bright_green]{pkg.name}[/bright_green]"
            )

        for num, pkg in enumerate(aur_explicit):
            num = num + 1 + len(sync_explicit)
            self.aur.get_pkgbuild(pkg, os.path.join(cwd, pkg.name))
            self.console.notify(
                f"({num}/{total}) Downloaded PKGBUILD: [bright_green]{pkg.name}[/bright_green]"
            )

        if missing:
            self.console.alert(
                f"Unable to find the following packages: {', '.join(pkg for pkg in missing)}"
            )
