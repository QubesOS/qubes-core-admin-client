.. program:: qvm-volume

:program:`qvm-volume` -- Qubes volume and block device managment
================================================================

Synopsis
--------

| :command:`qvm-volume` *COMMAND* [-h] [--verbose] [--quiet] [options] [arguments]

Description
-----------

.. TODO Add description

Options
-------

.. option:: --help, -h

   Show help message and exit

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

Commands
--------

list
^^^^

| :command:`qvm-volume list` [-h] [--verbose] [--quiet] [-p *POOL_NAME*] [*VMNAME* [*VMNAME* ...]]

List block devices. By default the internal devices are hidden. When the
stdout is connected to a TTY `qvm-volume list` will print a pretty table by
omitting redundant data. This behaviour is disabled when `--full` option is
passed or stdout is redirected to a pipe or file.

.. option:: -p, --pool

   list volumes from specified pool

.. option:: --full

   print domain names

.. option:: --all

   List volumes from all qubes. You can use :option:`--exclude` to limit the
   qubes set. Don't forget — internal devices are hidden by default!

.. option:: --exclude

   Exclude the qube from :option:`--all`.

aliases: ls, l

info
^^^^
| :command:`qvm-volume info` [-h] [--verbose] [--quiet] *VMNAME:VOLUME* [*PROPERTY*]

Show information about given volume - all properties and available revisions
(for `revert` action). If specific property is given, only its value is printed.
For list of revisions use `revisions` value.

aliases: i

config
^^^^^^
| :command:`qvm-volume config` [-h] [--verbose] [--quiet] *VMNAME:VOLUME* *PROPERTY* *VALUE*

Set property of given volume. Properties currently possible to change:

  - `rw` - `True` if volume should be writeable by the qube, `False` otherwise
  - `revisions_to_keep` - how many revisions (previous versions of volume)
    should be keep. At each qube shutdown its previous state is saved in new
    revision, and the oldest revisions are remove so that only
    `revisions_to_keep` are left. Set to `0` to not leave any previous versions.

aliases: c, set, s

resize
^^^^^^
| :command:`qvm-volume resize` [-h] [--force|-f] [--verbose] [--quiet] *VMNAME:VOLUME* *NEW_SIZE*

Resize the volume with *VMNAME:VOLUME* TO *NEW_SIZE*

If new size is smaller than current, the tool will refuse to continue unless
`--force` option is used. One should be very careful about that, because
shrinking volume without shrinking filesystem and other data inside first, will
surely end with data loss.

.. option:: -f, --force

   Force operation even if new size is smaller than the current one.

aliases: extend

revert
^^^^^^

| :command:`qvm-volume revert` [-h] [--verbose] [--quiet] *VMNAME:VOLUME*

Revert a volume to previous revision.

aliases: rv, r

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Bahtiar `kalkin-` Gadimov <bahtiar at gadimov dot de>

.. vim: ts=3 sw=3 et tw=80
