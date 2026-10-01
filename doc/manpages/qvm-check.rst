.. program:: qvm-check

:program:`qvm-check` --  Check qube
===================================

Synopsis
--------

:command:`qvm-check` [-h] [--verbose] [--quiet] [--all] [--exclude *EXCLUDE*] [--running] [--paused] [--template] [--networked] [*VMNAME* ...]

Description
-----------

This tool checks whether given qubes exist and, optionally, whether they are
in a given state. It is intended mainly for scripting: the result is
reported through the exit code, similar to :program:`test`. Human-readable
messages are printed too, unless :option:`--quiet` is used.

Without any state option, the tool checks only whether the given qubes exist.
When one or more of :option:`--running`, :option:`--paused`,
:option:`--template`, :option:`--networked` are given, the tool checks which
of the given qubes satisfy all the given conditions.

For example, to shut down a qube only if it is currently running::

   if qvm-check -q --running work; then qvm-shutdown --wait work; fi

Exit codes
----------

0
   All given qubes exist (and match all requested state options).

1
   Some given qube does not exist, or none of the (existing) qubes matches
   the requested state options.

3
   Only some of the given qubes match the requested state options.

Options
-------

.. option:: --help, -h

   Show this help message and exit

.. option:: --verbose, -v

   Increase verbosity

.. option:: --quiet, -q

   Decrease verbosity; do not print result messages, only set exit code

.. option:: --all

   Perform the check on all qubes (except dom0)

.. option:: --exclude=EXCLUDE

   Exclude the qube from :option:`--all`. Can be specified multiple times.

.. option:: --running

   Determine if (any of given) VM is running

.. option:: --paused

   Determine if (any of given) VM is paused

.. option:: --template

   Determine if (any of given) VM is a template

.. option:: --networked

   Determine if (any of given) VM can reach network

.. option:: --version

   Show program's version number and exit

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>
| Frédéric Pierret <frederic dot pierret at qubes dash os dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
