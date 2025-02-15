.. program:: qvm-notes

:program:`qvm-notes` -- Manipulate qube notes
=============================================

Synopsis
--------

:command:`qvm-notes` [options] *VMNAME* [--edit | --print | --import *FILENAME* | --set '*NOTES*' | --append '*NOTES*' | --delete]

Description
-----------

This command is used to manipulate individual qube notes. Each qube notes is
limited to 256KB of clear text which could contain most UTF-8 characters.
However, some UTF-8 characters will be replaced with underline (`_`) due to
security limitations. Qube notes will be included in backup/restore.

If this command is run outside dom0, it will require `admin.vm.notes.Get` and/or
`admin.vm.notes.Set` access privileges for the target qube in the RPC policies.

General options
---------------

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --help, -h

   show this help message and exit

.. option:: --version

   show program's version number and exit

.. option:: --force, -f

   Do not prompt for confirmation; assume `yes`

Action options
--------------

.. option:: --edit, -e

   Edit qube notes in $EDITOR (default text editor). This is the default action.

.. option:: --print, -p

   Print qube notes

.. option:: --import=FILENAME, -i FILENAME

   Import qube notes from file

.. option:: --set='NOTES', -s 'NOTES'

   Set qube notes from the provided string

.. option:: --append='NOTES'

   Append the provided string to qube notes. If the last line of existing note
   is not empty, a new line will be automatically inserted.

   Note that by design, qube notes is not suitable for appending automated logs
   because of 256KB size limit and infrior performance compared to alternatives.

.. option:: --delete, -d

   Delete qube notes

Authors
-------

| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Ali Mirjamali <ali at mirjamali dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
