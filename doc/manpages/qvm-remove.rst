.. program:: qvm-remove

:program:`qvm-remove` -- remove domain
======================================

Synopsis
--------
:command:`qvm-remove` [-h] [--verbose] [--quiet] [--force] [--force-root] [--all] [--exclude *EXCLUDE*] [*VMNAME* ...]

Description
-----------

This tool removes qubes from the system, deleting their storage volumes
together with all data and their configuration. Removal is irreversible:
unless you have a backup (see :program:`qvm-backup`), the private storage of
a removed qube cannot be recovered.

Unless :option:`--force` is given, the tool lists the qubes about to be
removed and asks for confirmation. Qube names may contain glob patterns
(e.g. ``qvm-remove 'test-*'``), which makes the confirmation prompt
especially useful for reviewing what actually matched.

A qube that is used by other parts of the system cannot be removed. If the
qube serves as a template for other qubes, provides network to them, or is
referenced by a global property (e.g. ``default_dispvm``), the removal fails
and the tool prints the list of dependencies that need to be removed or
re-assigned first. dom0 can never be removed.

Running qubes cannot be removed; shut them down first (see
:program:`qvm-shutdown`).

The exit code is 0 when all selected qubes were removed, and 1 when the
operation was cancelled or failed.

Options
-------

.. option:: --all

   Remove all qubes except dom0. You can use :option:`--exclude` to limit the
   qubes set. Since removing all qubes may leave the system in an unrecoverable
   state, this asks for an additional confirmation (unless :option:`--force`
   or :option:`--exclude` is given): you need to type ``IKNOWWHATIAMDOING``
   (case-sensitive) to proceed.

.. option:: --exclude=EXCLUDE

   Exclude the qube from :option:`--all`. Can be specified multiple times.

.. option:: --force, -f

   Do not prompt for confirmation; assume 'yes'.

.. option:: --help, -h

   Show this help message and exit

.. option:: --verbose, -v

   Increase verbosity

.. option:: --quiet, -q

   Decrease verbosity

.. option:: --version

   Show program's version number and exit

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Bahtiar `kalkin-` Gadimov <bahtiar at gadimov dot de>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
