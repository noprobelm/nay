# Not *Another* Yaourt

`nay` is a wrapper for pacman that includes support for AUR package management. It can be used in the same way as `pacman`, with additional features.


## USE AT YOUR OWN RISK
---
This project is a work in progress. Many commands are not supported, and behavior may be erratic during development. You should use a different package manager when doing important things with your system.

## Installation

```
pip install git+https://github.com/noprobelm/nay
```

## Supported Commands

| Operation                              | Description                                                                                            |
|----------------------------------------|--------------------------------------------------------------------------------------------------------|
| None                                   | Refresh the database and perform a full system upgrade (i.e. `sudo pacman -Syu`)                       |
| None `<targets>`                       | Refresh the database; query the Sync DB and AUR for packages; install selected                         |
| `-S`                                   | Install targets                                                                                        |
| `-Ss`                                  | Query the Sync DB and AUR for packages                                                                 |
| `-Sy <optional targets>`               | Refresh the Sync DB; optionally install targets                                                        |
| `-Syu <optional targets>`              | Refresh the Sync DB; perform full system upgrade; optionally install targets                           |
| `-Sw <targets>`                        | Retrieve package data from server; do not install (AUR packages go to `~/.cache/nay`)               |
| `-Sc`                                  | Remove packages that are no longer installed from the cache as well as currently unused sync databases |
| `-R<flags> <targets>`                  | Remove packages from the system                                                                        |
| `-Q<flags> <optional targets>`         | All `pacman` query operations are currently supported                                                  |
| `-G <targets>` * Partially implemented | Get the `PKGBUILD` from ABS or AUR                                                                     |


# License

Copyright © 2023 Jeff Barfield

