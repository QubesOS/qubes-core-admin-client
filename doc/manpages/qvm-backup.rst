.. program:: qvm-backup

:program:`qvm-backup` -- Create a backup of Qubes
=================================================

Synopsis
--------

:command:`qvm-backup` [-h] [--verbose] [--quiet] [--profile *PROFILE*] [--exclude EXCLUDE_LIST] [--dest-vm *APPVM*] [--encrypt] [--passphrase-file PASSPHRASE_FILE] [--compress] [--compress-filter *COMPRESSION*] [--save-profile SAVE_PROFILE] backup_location [vms [vms ...]]


Options
-------

.. option:: --profile

   Specify backup profile to use, which must be in /etc/qubes/backup/, without
   the file path or file extension. This option is mutually exclusive with all
   other options. This is also the only working mode when running from non-dom0.

.. option:: --save-profile

   Save backup profile based on given options. This is possible only when
   running in dom0. Otherwise, prepared profile is printed on standard output
   and user needs to manually place it into /etc/qubes/backup in dom0.

.. option:: --help, -h

   show help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --exclude, -x

   Exclude the specified VM from the backup (may be repeated)

.. option:: --dest-vm, -d

   Specify the destination VM to which the backup will be sent (implies -e)

.. option:: --encrypt, -e

   Ignored, backup is always encrypted

.. option:: --passphrase-file, -p

   Read passphrase from a file, or use '-' to read from stdin

.. option:: --compress, -z

   Compress the backup. This is default.

.. option:: --no-compress

   Do not compress the backup.

.. option:: --compress-filter, -Z

   Specify a non-default compression filter program (default: gzip)

.. option:: --yes, -y

   Do not ask for confirmation

Arguments
---------

The first positional parameter is the backup location (absolute directory path,
or command to pipe backup to). After that you may specify the qubes you'd
like to backup. If not specified, the default list based on the VM's "include
in backups" property will be used.

Notes
-----

The backup always contains the names and metadata of VMs on the system, in an
effort to preserve the dependencies between them as best as possible. As such,
using ``qvm-backup`` to export a subset of VMs on your system and share them
might inadvertently leak sensitive information.

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
