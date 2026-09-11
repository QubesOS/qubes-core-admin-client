.. program:: qvm-start

:program:`qvm-start` -- start a domain
======================================

Synopsis
--------

:command:`qvm-start` [-h] [options] [--all] [--exclude *EXCLUDE*] [*VMNAME* ...]

Description
-----------

This tool starts one or more qubes. Anything the qube depends on is started
automatically as well - most notably its network-providing qube (``netvm``),
if any. Note that usually there is no need to start qubes explicitly: they
are started automatically on the first attempt to use them (e.g. when
starting an application in the qube).

Multiple qubes may be given on the command line, and the qube names may
contain glob patterns (e.g. ``qvm-start 'work-*'``). All selected qubes are
started in parallel.

Starting a qube that is already running is an error, unless
:option:`--skip-if-running` is given. If starting some of the qubes fails, an
error is printed for each failed qube and the exit code is 1; otherwise the
exit code is 0.

Optionally, a drive (a disk image or a block device, served by any qube) can
be temporarily attached to the started qube, for example to boot an installer
image. The attachment is not persistent - it will not be re-attached on the
next qube startup.

Options
-------

.. option:: --help, -h

   Show help message and exit.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --skip-if-running

   Do not fail if the qube is already running.

.. option:: --all

   Start all qubes (except dom0).

.. option:: --exclude=EXCLUDE

   Exclude the qube from :option:`--all`. Can be specified multiple times.

.. option:: --drive=DRIVE

   Temporarily attach specified drive as CD/DVD or hard disk (can be specified with prefix "hd:" or "cdrom:", default is cdrom).
   The syntax for the device itself is "qube_name:device_name", meaning *device_name* served by *qube_name*.
   See `qvm-block` output for a list of available devices.

   Additionally, "qube_name:path" syntax can be used. This
   will setup loop device inside *qube_name*, pointing at *path*, and will use
   it as device. You need to clean up that loop device yourself, but it will
   also cleanup itself at next qube restart. This syntax is available only when
   calling this tool from dom0.

.. option:: --hddisk=DRIVE

   Temporarily attach specified drive as hard disk. This is equivalent with
   `--drive=hd:DRIVE`.

.. option:: --cdrom=DRIVE

   Temporarily attach specified drive as CD/DVD (read-only). This is
   equivalent with `--drive=cdrom:DRIVE`.

.. option:: --install-windows-tools

   Temporarily attach Windows tools CDROM to the domain. This is equivalent with
   `--cdrom=dom0:/usr/lib/qubes/qubes-windows-tools.iso`.

.. option:: --version

   Show program's version number and exit

The options :option:`--drive`, :option:`--hddisk`, :option:`--cdrom` and
:option:`--install-windows-tools` are mutually exclusive.

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
