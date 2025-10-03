.. program:: qvm-restart

:program:`qvm-restart` -- Restart selected or currently running qubes
=====================================================================

Synopsis
--------

:command:`qvm-restart` [-h] [--verbose] [--quiet] [--all] [--exclude *EXCLUDE*] [--timeout *TIMEOUT*] [*VMNAME*]

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

.. option:: --timeout

   timeout after which domains are killed. The default is decided by global
   `default_shutdown_timeout` property and qube `shutdown_timeout` property

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
