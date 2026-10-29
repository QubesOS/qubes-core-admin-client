.. program:: qvm-unpause

:program:`qvm-unpause` -- unpause a domain
==========================================

Synopsis
--------

:command:`qvm-unpause` [-h] [--verbose] [--quiet] [--all] [--exclude *EXCLUDE*] [*VMNAME* ...]

Description
-----------

This tool resumes execution of one or more paused qubes. It is the counterpart
of :program:`qvm-pause`: a qube paused with ``qvm-pause`` has its execution
frozen while still occupying memory; unpausing makes it run again from the
exact point where it was stopped. If a qube was put into (S3) suspend mode
(``qvm-pause --suspend``), it is resumed instead of unpaused.

Multiple qubes may be given on the command line, and the qube names may
contain glob patterns (e.g. ``qvm-unpause 'work-*'``). All matching qubes are
unpaused concurrently.

If unpausing some of the qubes fails, an error is printed for each failed qube
and the exit code is 1; otherwise the exit code is 0.

Options
-------

.. option:: --help, -h

   Show the help message and exit.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --all

   Unpause all the qubes, except those marked with the ``internal`` feature
   (such as preloaded disposables).

.. option:: --exclude=EXCLUDE

   Exclude the qube from :option:`--all`. Can be specified multiple times.

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
