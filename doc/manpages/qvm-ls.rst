.. program:: qvm-ls

:program:`qvm-ls` -- List VMs and various information about them
================================================================

Synopsis
--------

:command:`qvm-ls` [-h] [--verbose] [--quiet] [--help-columns] [--help-formats] [--format *FORMAT* | --fields *FIELD*,...] [--tags *TAG* [*TAG* ...]] [--running] [--paused] [--halted]

Positional arguments
--------------------

.. option:: VMNAME

   Zero or more domain names

General options
---------------

.. option:: --help, -h

   Show help message and exit

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --all

   List all qubes, this is default.

.. option:: --exclude

   Exclude the qube from --all. You need to use --all option explicitly to use
   --exclude.

.. option:: --spinner

   Have a spinner spinning while the spinning mainloop spins new table cells.

.. option:: --no-spinner

   No spinner today.

Formatting options
------------------

.. option:: --format=FORMAT, -o FORMAT

   Sets format to a list of columns defined by preset. All formats along with
   columns which they show can be listed with :option:`--help-formats`.

.. option:: --fields=FIELD,..., -O FIELD,...

   Sets format to specified set of columns. This gives more control over
   :option:`--format`. All columns along with short descriptions can be listed
   with :option:`--help-columns`.

.. option:: --tree, -t

   List domains as a network tree. Domains are sorted as they are connected to
   their netvms. Names are indented relative to the number of connected netvms.

.. option:: --raw-data

   Output data in easy to parse format. Table header is skipped and columns are
   separated by `|` character.

.. option:: --raw-list

   Give plain list of VM names, without header or separator. Useful in scripts.
   Same as --raw-data --fields=name

.. option:: --disk, -d

   Same as --format=disk, for compatibility with Qubes 3.x

.. option:: --network, -n

   Same as --format=network, for compatibility with Qubes 3.x

.. option:: --kernel, -k

   Same as --format=kernel, for compatibility with Qubes 3.x

.. option:: --help-columns

   List all available columns with short descriptions and exit.

.. option:: --help-formats

   List all available formats with their definitions and exit.

Filtering options
-----------------

.. option:: --class CLASS ...

   Show only qubes of specific class(es)

.. option:: --label LABEL ...

   Show only qubes with specific label(s)

.. option:: --tags TAG ...

   Shows only VMs having specific tag(s).

.. option:: --exclude-tags TAG ...

   Exclude VMs having specific tag(s).

.. option:: --running, --paused, --halted

   Shows only VMs matching the specified power state(s). When none of these
   options is used (default), all VMs are shown.

.. option:: --template-source TEMPLATE ...

   Filter results to the qubes based on the TEMPLATE(s)

.. option:: --netvm-is NETVM ...

   Filter results to the qubes connecting via NETVM(s)

.. option:: --internal <y|n>

   Show only internal qubes or exclude them from output

.. option:: --servicevm <y|n>

   Show only servicevms or exclude them from output

.. option:: --pending-update

   Filter results to qubes pending for update

.. option:: --features FEATURE=VALUE ...

   Filter results to qubes that match all specified features. Omitted VALUE
   means None (not set). "" or '' means blank

.. option:: --prefs PREFERENCE=VALUE ...

   Filter results to qubes that match all specified preferences. Omitted VALUE
   means None (not set). "" or '' means blank

Sorting options
---------------

.. option:: --sort COLUMN

   Sort based on provided column rather than NAME. Sort key should be in the
   output columns

.. option:: --reverse

   Reverse sort

.. option:: --ignore-case

   Ignore case distinctions for sorting

Authors
-------
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et
