EXTENDED PACMAN OPERATIONS
===============================

       -S, -Si, -Ss, -Su, -Sc, -Qu
              These operations are extended to support both AUR and repo packages.

       -Sc    Nay will also clean cached AUR package and any untracked Files in the cache. Cleaning untracked files will wipe any
              downloaded sources or built packages but will keep already downloaded vcs sources.

       -R     Nay will also remove cached data about devel packages.
