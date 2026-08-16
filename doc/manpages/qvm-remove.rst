.. program:: qvm-remove

:program:`qvm-remove` -- remove qubes (virtual machines) from the system
========================================================================

Description
-----------

:program:`qvm-remove` permanently deletes one or more qubes (virtual machines)
from a Qubes OS system. This operation is **irreversible** -- all data stored in
the removed qube(s), including private volumes and stored snapshots, will be
permanently lost.

If a qube is still in use by another qube (for example as its template or
default disposable qube), the removal fails with a clear error message listing
the dependencies. You must first reconfigure the dependent qubes before the
removal can proceed.

For safety, :program:`qvm-remove` prompts for confirmation before deleting any
qube(s). Use :option:`--force` to skip the confirmation prompt (useful for
scripts), but be cautious -- there is no undo.

The protected domain ``dom0`` can never be removed.

**Note:** To temporarily stop a qube without deleting it, use
:program:`qvm-shutdown` or :program:`qvm-kill`.

Synopsis
--------

:command:`qvm-remove` [-h] [--verbose] [--quiet] [--force] [--all] [--exclude *EXCLUDE*] [*VMNAME* [*VMNAME* ...]]

Options
-------

.. option:: --all

   Remove all qubes at once. dom0 is never removed. This operation will
   prompt for an extra safety confirmation ("IKNOWWHATIAMDOING") unless
   :option:`--force` or :option:`--exclude` is also specified. Use
   :option:`--exclude` to preserve specific qubes from the removal.

.. option:: --exclude

   Exclude a specific qube from the :option:`--all` removal set. Can be
   specified multiple times.

.. option:: --force, -f

   Skip the confirmation prompt and proceed immediately with removal.
   Useful for scripting, but dangerous -- use with care.

.. option:: --help, -h

   Show this help message and exit.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --version

   Show program's version number and exit.

Examples
--------

Remove a single qube named ``work-vm`` (with confirmation prompt)::

    qvm-remove work-vm

Remove multiple qubes at once::

    qvm-remove old-vm1 old-vm2 old-vm3

Remove all qubes except ``work-vm`` and ``personal-vm``::

    qvm-remove --all --exclude work-vm --exclude personal-vm

Remove a qube without confirmation (for scripts)::

    qvm-remove --force temp-vm

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Bahtiar `kalkin-` Gadimov <bahtiar at gadimov dot de>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
