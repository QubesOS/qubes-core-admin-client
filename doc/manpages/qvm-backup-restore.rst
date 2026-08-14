.. program:: qvm-backup-restore

===============================================================
:program:`qvm-backup-restore` -- Restores Qubes VMs from backup
===============================================================

Description
===========

:program:`qvm-backup-restore` verifies a Qubes backup, displays a restore
summary, and restores the selected qubes after confirmation. Existing qubes
are not overwritten: name conflicts stop the restore unless they are skipped
or the restored qubes are renamed with the corresponding options.

The backup may be read from dom0, from an AppVM selected with
:option:`--dest-vm`, or from a qrexec service. Positional qube names restrict
the restore to those entries; :option:`--exclude` removes individual entries
from the selection.

Backups should be treated as untrusted input. :option:`--paranoid-mode`
isolates the restore process in a DisposableVM and omits data that cannot be
restored safely in that mode. Use :option:`--verify-only` to check integrity
without restoring data.

Synopsis
========
:command:`qvm-backup-restore` [*options*] *BACKUP-LOCATION* [*VMNAME* ...]

Options
=======

.. option:: --help, -h

    Show this help message and exit

.. option:: --verbose, -v

   Increase verbosity

.. option:: --quiet, -q

   Decrease verbosity


.. option:: --verify-only

    Do not restore the data, only verify backup integrity

.. option:: --skip-broken

    Do not restore VMs that have missing templates or netvms

.. option:: --ignore-missing

    Ignore missing templates or netvms, restore VMs anyway

.. option:: --skip-conflicting

    Do not restore VMs that are already present on the host

.. option:: --rename-conflicting

   Restore VMs that are already present on the host under different names

.. option:: --exclude=EXCLUDE, -x EXCLUDE

    Skip restore of specified VM (might be repeated)

.. option:: --skip-dom0-home

    Do not restore dom0 user home dir

.. option:: --ignore-username-mismatch

    Ignore dom0 username mismatch while restoring homedir

.. option:: --ignore-size-limit

    Backup metadata contains expected size of each VM. By default if backup
    contains more data than expected, it is rejected. Use this option to ignore
    this limit and restore such (broken, or potentially malicious) backup
    anyway.

.. option:: --compression-filter, -Z

    Force specific compression filter, instead of the one named in the backup
    header. The compression filter is a command that accepts ``-d`` option to
    decompress data on stdin and output it to stdout.  This can be used to
    override built-in protection against uncommon compression.

.. option:: --dest-vm=APPVM, -d APPVM

    Restore from a backup located in a specific AppVM

.. option:: --passphrase-file, -p

   Read passphrase from file, or use '-' to read from stdin

.. option:: --location-is-service

   Provided backup location is a qrexec service name (optionally with an
   argument, separated by ``+``), instead of file path or a command.

.. option:: --paranoid-mode, --plan-b

  Isolate restore process in a DisposableVM, defend against potentially
  compromised backup. In this mode some parts of the backup are skipped,
  specifically:

    - dom0 home directory (desktop environment settings)
    - PCI devices assignments

  This operation requires `qubes-core-admin-client` package in the DisposableVM

.. option:: --auto-close

  When running with --paranoid-mode (see above), automatically close restore
  progress window after the restore process is finished and display restore log
  on the standard output. The log will be colored red if the standard output is
  a terminal.

.. option:: --version

   Show program's version number and exit

Examples
========

Verify a backup without restoring it::

   qvm-backup-restore --verify-only /media/backup/qubes-backup

Restore only ``work`` and ``vault`` from a backup stored in ``backup-vm``::

   qvm-backup-restore -d backup-vm /home/user/qubes-backup work vault

Restore an untrusted backup in a DisposableVM::

   qvm-backup-restore --paranoid-mode /media/backup/qubes-backup

Authors
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git
