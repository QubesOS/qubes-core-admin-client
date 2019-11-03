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
    option multiple times. For supported drivers and their options,
    see ``drivers``.

aliases: a

drivers
^^^^^^^
| :command:`qvm-pool drivers` [-h] [--verbose] [--quiet]

List all known drivers with their options.
The listed driver options can be used with the ``-o options`` switch.

aliases: d

info
^^^^
| :command:`qvm-pool info` [-h] [--verbose] [--quiet] *POOL_NAME*

Print info about a specified pool

aliases: i

list
^^^^
| :command:`qvm-pool list` [-h] [--verbose] [--quiet]

List all available pools.

aliases: l, ls

remove
^^^^^^
| :command:`qvm-pool remove` [-h] [--verbose] [--quiet] *POOL_NAME* [*POOL_NAME* ...]

Remove the specified pools. This removes only the information about the pool
from qubes.xml, but does not delete any content (FIXME: is it really true for
all pool drivers?).

aliases: r, rm

set
^^^
| :command:`qvm-pool set` [-h] [--verbose] [--quiet] *POOL_NAME*

Modify driver options for a pool.

.. option:: --option, -o

    Set option for the driver in `name=value` format. You can specify this
    option multiple times. For supported drivers and their options,
    see ``drivers``.

aliases: s

Examples
--------

Create a pool backed by the `file` driver.

::

    qvm-pool add foo file -o dir_path=/mnt/foo

Authors
-------
| Bahtiar \`kalkin-\` Gadimov <bahtiar at gadimov dot de>
| Saswat Padhi <padhi at cs dot ucla dot edu>
