.. program:: qvm-restart

:program:`qvm-restart` -- Restart selected or currently running qubes
=====================================================================

Synopsis
--------

:command:`qvm-restart` [-h] [--verbose] [--quiet] [--all] [--exclude *EXCLUDE*] [--force] [--timeout *TIMEOUT*] [*VMNAME*]

Options
-------

.. option:: --help, -h

   show the help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --all

   perform the action on all running qubes except dom0 & unnamed DispVMs

.. option:: --exclude=EXCLUDE

   exclude the qube from :option:`--all`

.. option:: --force, -f

   force restart if other qubes depend on selected qubes, e.g. as NetVM or AudioVM; does not affect how the qube itself is shut down. Use with caution.

.. option:: --start, -s

   start selected domains if they are down initially. By default skips halted domains.

.. option:: --version

   Show program's version number and exit


Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
