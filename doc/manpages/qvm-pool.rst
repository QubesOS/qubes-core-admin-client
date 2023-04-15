.. program:: qvm-pool

:program:`qvm-pool` -- Manage pools
===================================

Synopsis
--------
| :command:`qvm-pool` {add,a} [*options*] <*pool_name*> <*driver*>
| :command:`qvm-pool` {drivers,d} [*options*]
| :command:`qvm-pool` {info,i} [*options*] <*pool_name*>
| :command:`qvm-pool` {list,ls,l} [*options*]
| :command:`qvm-pool` {remove,rm,i} [*options*] <*pool_name*> ...
| :command:`qvm-pool` {set,s} [*options*] <*pool_name*>

Legacy Mode
^^^^^^^^^^^
| :command:`qvm-pool` [*options*] {-a, --add} <*pool_name*> <*driver*>
| :command:`qvm-pool` [*options*] {-i, --info} <*pool_name*>
| :command:`qvm-pool` [*options*] {-l, --list}
| :command:`qvm-pool` [*options*] {-r, --remove} <*pool_name*>
| :command:`qvm-pool` [*options*] {-s, --set} <*pool_name*>
| :command:`qvm-pool` [*options*] --help-drivers

.. deprecated:: 4.0.18

Options
-------

.. option:: --help, -h

    Show this help message and exit

.. option:: --quiet, -q

    Be quiet

.. option:: --verbose, -v

    Increase verbosity

Commands
--------

add
^^^
| :command:`qvm-pool add` [-h] [--verbose] [--quiet] *POOL_NAME* *DRIVER*

Add a new pool.

.. option:: --option, -o

    Set option for the driver in `name=value` format. You can specify this
    option multiple times.

    .. seealso:: The `drivers` command for supported drivers and their options.

aliases: a

Legacy mode: :command:`qvm-pool` [-h] [--verbose] [--quiet] --add *POOL_NAME* *DRIVER* -o *OPTIONS*

drivers
^^^^^^^
| :command:`qvm-pool drivers` [-h] [--verbose] [--quiet]

List all known drivers with their options.
The listed driver options can be used with the ``-o options`` switch.

aliases: d

Legacy mode: :command:`qvm-pool` [-h] [--verbose] [--quiet] --help-drivers

info
^^^^
| :command:`qvm-pool info` [-h] [--verbose] [--quiet] *POOL_NAME*

Print info about a specified pool

aliases: i

Legacy mode: :command:`qvm-pool` [-h] [--verbose] [--quiet] --info *POOL_NAME*

list
^^^^
| :command:`qvm-pool list` [-h] [--verbose] [--quiet]

List all available pools.

aliases: l, ls

Legacy mode: :command:`qvm-pool` [-h] [--verbose] [--quiet] --list

remove
^^^^^^
| :command:`qvm-pool remove` [-h] [--verbose] [--quiet] *POOL_NAME* [*POOL_NAME* ...]

Remove the specified pools. This removes only the information about the pool
from qubes.xml, but does not delete any content (FIXME: is it really true for
all pool drivers?).

aliases: r, rm

Legacy mode: :command:`qvm-pool` [-h] [--verbose] [--quiet] --remove *POOL_NAME* [*POOL_NAME* ...]

set
^^^
| :command:`qvm-pool set` [-h] [--verbose] [--quiet] *POOL_NAME*

Modify driver options for a pool.

.. option:: --option, -o

    Set option for the driver in `name=value` format. You can specify this
    option multiple times.

    .. seealso:: The `drivers` command for supported drivers and their options.

aliases: s

Legacy mode: :command:`qvm-pool` [-h] [--verbose] [--quiet] --set *POOL_NAME* -o *OPTIONS*

Examples
--------

Create a pool backed by the `file-reflink` driver.

::

    qvm-pool add foo file-reflink -o dir_path=/mnt/foo

Have pool ``lvm`` encrypt its volatile volumes with an ephemeral key for
anti-forensics:

::

    qvm-pool set -o encrypted_volatile=True lvm

Authors
-------
| Bahtiar \`kalkin-\` Gadimov <bahtiar at gadimov dot de>
| Saswat Padhi <padhi at cs dot ucla dot edu>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git
