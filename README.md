# Not *Another* Yaourt

`nay` is a wrapper for `pacman` which includes support for AUR packages. It can be used in the same way as `pacman`, with additional features.


## USE AT YOUR OWN RISK
This project is a work in progress. Many commands are not supported, and behavior may be erratic during development. You should use a different package manager when doing important things with your system.

## Installation

Install directly from the AUR

```
git clone https://aur.archlinux.org/nay.git && cd nay && makepkg -si && cd ../ && rm -rf nay
```

Use your favorite AUR helper

```
yay nay
```

Use `pip`

```
pip install git+https://github.com/noprobelm/nay
```

## Supported Commands

To update all system packages:

`nay`

To install a package from a database/AUR query, run `nay` optionless:

`nay yay`


| Operation                      | Description                                                                                            |
|--------------------------------|--------------------------------------------------------------------------------------------------------|
| `<optionless>`                   | Refresh the database and perform a full system upgrade (i.e. `sudo pacman -Syu`)                       |
| `<optionless> <targets>`       | Refresh the database; query the Sync DB and AUR for packages; install selected                         |
| `-S`                           | Install targets                                                                                        |
| `-Ss`                          | Query the Sync DB and AUR for packages                                                                 |
| `-Sy <optional targets>`       | Refresh the Sync DB; optionally install targets                                                        |
| `-Syu <optional targets>`      | Refresh the Sync DB; perform full system upgrade; optionally install targets                           |
| `-Si <targets>`                | Print information about a package to the terminal                                                      |
| `-Sc`                          | Remove packages that are no longer installed from the cache as well as currently unused sync databases |
| `-R<flags> <targets>`          | Remove packages from the system                                                                        |
| `-Q<flags> <optional targets>` | All `pacman` query operations are currently supported                                                  |
| `-G <targets>`                 | Get `PKGBUILD` from ABS or AUR                                                                         | 


# License

Copyright © 2023 Jeff Barfield

