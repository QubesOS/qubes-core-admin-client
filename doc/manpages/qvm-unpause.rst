.. program:: qvm-unpause

:program:`qvm-unpause` -- unpause a domain
==========================================

Description
-----------

:program:`qvm-unpause` resumes execution of paused or suspended qubes. It does
not start a halted qube. Multiple qube names may be supplied; a failure to
resume any selected qube makes the command exit with status 1.

Synopsis
--------

| :command:`qvm-unpause` [*options*] *VMNAME* [*VMNAME* ...]
| :command:`qvm-unpause` [*options*] --all [--exclude *VMNAME*]

Options
-------

.. option:: --help, -h

   Show the help message and exit.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --all

   Unpause all non-internal qubes.

.. option:: --exclude=EXCLUDE

   Exclude the qube from :option:`--all`.

.. option:: --version

   Show program's version number and exit

Examples
--------

Resume one paused qube::

   qvm-unpause work

Resume every non-internal qube except ``vault``::

   qvm-unpause --all --exclude vault

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
