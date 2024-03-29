.. program:: qvm-ls

:program:`qvm-ls` -- List VMs and various information about them
================================================================

Synopsis
--------

:command:`qvm-ls` [-h] [--verbose] [--quiet] [--help-columns] [--help-formats] [--format *FORMAT* | --fields *FIELD*,...] [--tags *TAG* [*TAG* ...]] [--running] [--paused] [--halted]

Options
-------

.. option:: --help, -h

   Show help message and exit

.. option:: --help-columns

   List all available columns with short descriptions and exit.

.. option:: --help-formats

   List all available formats with their definitions and exit.

.. option:: --all

   List all qubes, this is default.

.. option:: --exclude

   Exclude the qube from --all. You need to use --all option explicitly to use
   --exclude.

.. option:: --format=FORMAT, -o FORMAT

   Sets format to a list of columns defined by preset. All formats along with
   columns which they show can be listed with :option:`--help-formats`.

.. option:: --fields=FIELD,..., -O FIELD,...

   Sets format to specified set of columns. This gives more control over
   :option:`--format`. All columns along with short descriptions can be listed
   with :option:`--help-columns`.

.. option:: --tags TAG ...

   Shows only VMs having specific tag(s).

.. option:: --running, --paused, --halted

   Shows only VMs matching the specified power state(s). When none of these
   options is used (default), all VMs are shown.

.. option:: --raw-data

   Output data in easy to parse format. Table header is skipped and columns are
   separated by `|` character.

.. option:: --raw-list

   Give plain list of VM names, without header or separator. Useful in scripts.
   Same as --raw-data --fields=name

.. option:: --tree, -t

   List domains as a network tree. Domains are sorted as they are connected to
   their netvms. Names are indented relative to the number of connected netvms.

.. option:: --disk, -d

   Same as --format=disk, for compatibility with Qubes 3.x

.. option:: --network, -n

   Same as --format=network, for compatibility with Qubes 3.x

.. option:: --kernel, -k

   Same as --format=kernel, for compatibility with Qubes 3.x

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --spinner

   Have a spinner spinning while the spinning mainloop spins new table cells.

.. option:: --no-spinner

   No spinner today.

Authors
-------
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et
