.. program:: qvm-remove

:program:`qvm-remove` -- remove domain
======================================

Description
-----------

:program:`qvm-remove` permanently removes the selected qubes and their
storage. By default it lists the qubes and asks for confirmation. The command
refuses to remove ``dom0`` and reports dependencies that prevent a qube from
being removed, such as another qube using it as a template or NetVM.

Use :option:`--force` only when confirmation has been handled by the caller; it
skips the prompt but does not override dependency checks. Removing all qubes
without :option:`--force` or :option:`--exclude` requires an additional
``IKNOWWHATIAMDOING`` confirmation.

Synopsis
--------
| :command:`qvm-remove` [*options*] *VMNAME* [*VMNAME* ...]
| :command:`qvm-remove` [*options*] --all [--exclude *VMNAME*]

Options
-------

.. option:: --all

   Remove all qubes. You can use :option:`--exclude` to limit the qube set.
   ``dom0`` is never removed.

.. option:: --exclude

   Exclude the qube from :option:`--all`.

.. option:: --force, -f

   Do not prompt for confirmation; assume 'yes'.

.. option:: --help, -h

    Show this help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --version

   Show program's version number and exit

Examples
--------

Remove one qube after reviewing the confirmation prompt::

   qvm-remove old-work

Remove several qubes without an interactive prompt::

   qvm-remove --force test-1 test-2

Remove all qubes except the named ones::

   qvm-remove --all --exclude vault --exclude sys-net

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Bahtiar `kalkin-` Gadimov <bahtiar at gadimov dot de> 

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
