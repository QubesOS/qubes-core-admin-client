.. program:: qvm-top

:program:`qvm-top` -- top-like monitoring tool
==============================================

Synopsis
--------

:command:`qvm-top` [--verbose] [--quiet] [--help] [--version] [--all] [--exclude *EXCLUDE*] [--show-halted] [--filter *FILTER*,...] [--columns *COLUMN*,... | --format *FORMAT*] [--help-columns] [--help-formats] [--sort-column *COLUMN*] [--reverse] [--no-color] [*VMNAME* ...]

Top-like info for Qubes. Defaults is to show all non-halted qubes.

Positional arguments
--------------------

.. option:: VMNAME ...

   Zero or more domain names. If none spcified, the default is to show all.

General Options
---------------

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --help, -h

   Show this help message and exit.

.. option:: --version

   Show program's version number and exit.

.. option:: --all

   Perform the action on all qubes

.. option:: --exclude EXCLUDE

   Exclude the qube from ``--all``.

.. option:: --show-halted, -S

   Don't hide halted qubes.

.. option:: --filter, -f FILTER,...

   Filter domains name matching each fixed string separated by comma.

.. option:: --no-color

   Do not colorize the screen. If this option is not provided, but environment
   variable `NO_COLOR` is set, the screen will not be colorized.

Formatting Options
------------------

.. option:: --columns, -C COLUMN,...

   Show only specified columns.

.. option:: --format, -F FORMAT

   Show only columns declared by format: `min`, `default, `max-no-internal`,
   `max`.

.. option:: --help-columns

   List all available columns with short descriptions and exit.

.. option:: --help-formats

   List all available formats with short descriptions and exit.

Sorting Options
---------------

.. option:: --sort-column, -k COLUMN

   Sort by specified column.

.. option:: --reverse, -r

   Reverse sorting.

Interaction - Navigation
------------------------

.. option:: Up, k, ^N

   Scroll one row up.

.. option:: Down, j, ^P

   Scroll one row down.

.. option:: ^B, ^F

   Scroll one page up or down.

.. option:: ^U, ^D

   Scroll half page up or down.

.. option:: Home, ^A

   Scroll to the first page.

.. option:: End, ^E

   Scroll to the last page.

Interaction - Visualization
---------------------------

.. option:: Left, h

   Sort the column to the left.

.. option:: Right, l

   Sort the column to the right.

.. option:: r

   Reverse sorting order.

.. option:: /

   Filter by qube name, CSV.

.. option:: S

   Toggle showing halted qubes.

.. option:: Enter

   Apply filter and return to main screen.

.. option:: ^L

   Redraw the screen on the next refresh.

.. option:: q, Q, ESC, ^C

   Quit filter mode.

Interaction - Execution
-----------------------

.. option:: Double-Left-Click, Space

   Tag a row and move one line, down if row was not previously selected, else
   up.

.. option:: T

   Toggle tag all visible rows.

.. option:: U

   Untag all rows.

.. option:: a

   Toggle action column, which shows only actions that can be executed to all
   tagged qubes. If none is tagged, act based on the current selection.

.. option:: Numbers

   If action column is active, typing a number will select the corresponding
   action.

.. option:: Enter

   If action column is active, apply action and return to main screen.

.. option:: q, Q, ESC, ^C

   Quit action mode.

Columns
-------

Columns are identified by a machine header followed by a pretty header if
necessary.

.. option:: name - NAME

   Qube name.

.. option:: state - STATE

   Current power state.

.. option:: memory_used - MU

   How much memory the domain is using.

.. option:: memory_used_with_swap - MSU

   How much memory including swap the domain is using.

.. option:: memory_assigned - MS

   How much memory the domain is allowed to claim at any time.

.. option:: memory_max - MM

   How much memory the domain can try to scale up to.

.. option:: memory_usage_used - MU/MM

   How much memory the domain is using in percentage.

.. option:: memory_usage_used_with_swap - MSU/MU

   How much memory the domain is swapping over what it is using.

.. option:: memory_usage_assigned - MS/MM

   How much memory the domain has assigned in percentage.

.. option:: memory_usage_used_assigned - MU/MS

   How much memory the domain is using from the assigned amount, in percentage.

.. option:: cpu_time - CPUsec

   How many seconds the domain has used from the CPU.

.. option:: cpu_usage - CPU%

   How much CPU the domain is using in percentage.

.. option:: online_vcpus - VC

   How many VCPUs are online.

.. option:: memory_used_internal - MUi

   How much memory the domain is using indirectly.

.. option:: memory_assigned_internal - MSi

   How much memory the domain is allowed to claim at any time.

.. option:: cpu_time_internal - CPUisec

   How many seconds the domain has used indirectly from the CPU.

.. option:: cpu_usage_internal - CPUi%

   How much CPU the domain is using indirectly in percentage.

.. option:: online_vcpus_internal - VCi

   How many VCPUs are online indirectly.

.. option:: memory_used_total - MUT

   How much memory the domain is using in total.

.. option:: memory_assigned_total - MST

   How much memory the domain is allowed to claim at any time.

.. option:: cpu_time_total - CPU(s)T

   How many seconds the domain has used in total from the CPU.

.. option:: online_vcpus_total - VCT

   How many VCPUs are online in total.

Notes
-----

Time printed represents the last moment the screen was refreshed. It only
happens when information is outdated.

Values for HVMs are aggregated with its companion device model stub domain,
therefore a HVM such as `sys-net` which has 2 VCPUs, with it's device model
having 1 VCPU, will show 3 VCPUs. Same process is done for other properties when
applicable.

Authors
-------

| Benjamin Grande <ben.grande.b at gmail dot com>
| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
