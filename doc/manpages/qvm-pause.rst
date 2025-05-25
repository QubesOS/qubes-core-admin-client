.. program:: qvm-pause

:program:`qvm-pause` -- pause a domain
======================================

Synopsis
--------

:command:`qvm-pause` [-h] [--all] [--exclude EXCLUDE] [--verbose] [--quiet] [--suspend] [*VMNAME* ...]

Options
-------

.. option:: --help, -h

   Show the help message and exit.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --all

   Pause all the qubes.

.. option:: --exclude=EXCLUDE

   Exclude the qube from :option:`--all`.

.. option:: --suspend, -S

   Put the qube to (S3) suspend mode instead of emergency pause

.. option:: --version

   Show program's version number and exit

Notes
-----

Paused qubes will be killed on system shutdown. Emergency paused qubes will
remain paused after computer suspend/resume; however, unpausing them may take
longer than usual.

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
