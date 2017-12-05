.. program:: qvm-ls

:program:`qvm-ls` -- List VMs and various information about them
================================================================

Synopsis
--------

:command:`qvm-ls` [-h] [--verbose] [--quiet] [--help-columns] [--help-formats] [--format *FORMAT* | --fields *FIELD*,...]

Options
-------

.. option:: --help, -h

   Show help message and exit

.. option:: --help-columns

   List all available columns with short descriptions and exit.

.. option:: --help-formats

   List all available formats with their definitions and exit.

.. option:: --format=FORMAT, -o FORMAT

   Sets format to a list of columns defined by preset. All formats along with
   columns which they show can be listed with :option:`--help-formats`.

.. option:: --fields=FIELD,..., -O FIELD,...

   Sets format to specified set of columns. This gives more control over
   :option:`--format`. All columns along with short descriptions can be listed
   with :option:`--help-columns`.

.. option:: --raw-data

   Output data in easy to parse format. Table header is skipped and columns are
   separated by `|` character.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

Authors
-------
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

.. vim: ts=3 sw=3 et
