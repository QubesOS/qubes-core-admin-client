.. program:: qubes-prefs

:program:`qubes-prefs` -- List/set various global properties
============================================================

Synopsis
--------

:command:`qubes-prefs` [-h] [--verbose] [--quiet] [--force-root] [--help-properties] [*PROPERTY* [*VALUE*\|--default]]

Options
-------

.. option:: --help, -h

   Show help message and exit.

.. option:: --help-properties

   List available properties with short descriptions and exit.

.. option:: --hide-default

   Do not show properties that are set to the default value.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --default, -D

   Reset propety to default value.

.. option:: --get, -g

   Ignored; for compatibility with older scripts.

.. option:: --set, -s

   Ignored; for compatibility with older scripts.


Common properties
=================

This list is non-exhaustive. For authoritative listing, see
:option:`--help-properties` and documentation of the source code.

clockvm

    Qube used as a time source for dom0

default_template

    Default template for newly created qubes

default_fw_netvm

    Default netvm for qubes providing network (with `provides_network` property
    set to `True`).

default_netvm

    Default netvm for qubes not providing network

default_kernel

    Default value for `kernel` property, see :manpage:`qvm-prefs(1)` for
    details.

default_pool

    Default storage pool for new qubes.

default_pool_kernel, default_pool_private, default_pool_root, default_pool_volatile

    Default storage pool for particular volume for new qubes. Defaults to value
    of `default_pool`.

stats_interval

    Interval (in seconds) at which VM statistics are sent. This is for example
    used by domains widget - this often memory usage will be refreshed.

updatevm

    Qube used to download dom0 updates

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
