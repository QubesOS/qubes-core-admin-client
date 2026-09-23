.. program:: qvm-backup-restore

===============================================================
:program:`qvm-backup-restore` -- Restores Qubes VMs from backup
===============================================================

Synopsis
========
:command:`qvm-backup-restore` [*options*] *backup_location* [*vms* ...]

Description
===========

This tool restores qubes from a backup created with :program:`qvm-backup`.
Restored qubes are added to the system as new qubes; existing qubes are never
removed or overwritten (see :option:`--rename-conflicting` and
:option:`--skip-conflicting` for handling name conflicts).

*backup_location* is the path to the backup file (or directory containing
it). Together with :option:`--dest-vm`, the path is interpreted inside the
given qube, which allows restoring from a backup stored in another qube
(e.g. one with access to an external disk or network storage).

If *vms* are given, only those qubes are restored from the backup; otherwise
all qubes contained in the backup are selected.

Before anything is restored, the tool asks for the backup passphrase (unless
:option:`--passphrase-file` is used), verifies backup integrity, prints a
summary of the qubes to be restored together with any detected problems
(name conflicts, missing templates or net qubes) and asks for confirmation.

The backup passphrase protects both confidentiality and integrity of the
backup. However, the backup metadata has to be parsed before its
authenticity is verified, and a maliciously crafted backup could try to
exploit this. If you restore a backup that may have been tampered with (for
example, it was stored on an untrusted medium), use :option:`--paranoid-mode`
to isolate the whole restore process in a disposable qube.

If the backup contains a dom0 home directory, it is not restored in place:
the archived home directory is placed in a new directory named
``home-restore-<timestamp>`` inside the current dom0 home directory, and
files should be copied or moved out of it manually.

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

    Ignore missing templates or netvms, restore VMs anyway (the system
    default template/netvm will be assigned instead)

.. option:: --skip-conflicting

    Do not restore VMs that are already present on the host

.. option:: --rename-conflicting

   Restore VMs that are already present on the host under different names
   (with numbers appended at the end)

.. option:: --exclude=EXCLUDE, -x EXCLUDE

    Skip restore of specified VM (might be repeated)

.. option:: --skip-dom0-home

    Do not restore dom0 user home dir

.. option:: --ignore-username-mismatch

    Ignore dom0 username mismatch while restoring homedir. Without this
    option, restoring a dom0 home directory that was archived under a
    different username than the current one is refused, since some settings
    referencing the home directory path could break.

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

    Restore from a backup located in a specific AppVM. The backup location is
    then a path (or command) interpreted inside that qube.

.. option:: --passphrase-file, -p

   Read passphrase from file, or use '-' to read from stdin. With this
   option, the restore proceeds without asking for confirmation
   (non-interactive mode).

.. option:: --location-is-service

   Provided backup location is a qrexec service name (optionally with an
   argument, separated by ``+``), instead of file path or a command. Requires
   :option:`--dest-vm`.

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

Authors
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git
