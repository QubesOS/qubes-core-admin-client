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

.. option:: S

   Toggle showing halted qubes.

.. option:: ^L

   Redraw the screen on the next refresh.

.. option:: q, Q, ESC, ^C

   Quit the application.

Interaction - Filter
--------------------

.. option:: /

   Filter by qube name, CSV.

.. option:: Enter

   Apply filter and return to main screen.

.. option:: q, Q, ESC, ^C

   Quit filter mode.

Interaction - Execution
-----------------------

.. option:: Double-Left-Click, Space

   Tag a row and move one line, down if row was not previously selected, else
   up.

.. option:: T

   Toggle tag all visible rows. Great when used with filter.

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

   Qube's name.

.. option:: state - STATE

   Qube's power state.

.. option:: memory_used -> MU

   How much memory the qube alleges to use. This value or part of it is broadcast by the qube, it can be a lie.

.. option:: memory_used_with_swap -> MSU

   How much memory including swap the qube alleges to use. This value or part of it is broadcast by the qube, it can be a lie.

.. option:: memory_assigned -> MS

   How much memory has been assigned to the qube, including videoram. A qube is allowed to claim this amount at any time, and it cannot use more memory than what has been assigned to it. When the system is under no memory pressure, this value is close to ``MM``, while when the system isunder memory pressure, the value can be as low as enough for the qube to survive.

.. option:: memory_max -> MM

   How much memory the qube can use from the system. Part of this value is reserved to videoram, while the rest is up to qmemman to balloon up this qube when there is enough free memory on the host.

.. option:: memory_usage_used -> MU/MM

   How much memory the qube alleges to use compared to the maximum it canuse from the system, in percentage.

.. option:: memory_usage_assigned -> MS/MM

   How much memory the qube has assigned compared to the maximum it can use from the system, in percentage. A high percentage means the system is not pressuring the qube to release memory.

.. option:: memory_usage_used_assigned -> MU/MS

   How much memory the qube alleges to use from the assigned amount, in percentage. A high percentage on non-memory-balanced qubes is irrelevant. On memory balanced qubes, a higher value indicates the qube is using a lot of the memory it has assigned, which might be near exhaustion, if ``MS`` can't be ballooned up anymore.

.. option:: memory_usage_used_with_swap -> MSU/MU

   How much memory the qube alleges to be swaping from what it alleges touse, in percentage. When it is over 10%, the qube might be swaping too much.

.. option:: cpu_time -> CPUsec

   How many seconds the qube has used from the CPU.

.. option:: cpu_usage -> CPU%

   How much CPU the qube is using, in percentage.

.. option:: online_vcpus -> VC

   How many Virtual CPUs are online.

.. option:: memory_used_internal -> MUi

   Same as MU, but internal usage.

.. option:: memory_assigned_internal -> MSi

   Same as ``MS``, but internal usage.

.. option:: cpu_time_internal -> CPUisec

   Same as ``CPUsec``, but internal usage.

.. option:: cpu_usage_internal -> CPUi%

   Same as ``CPU%``, but internal usage.

.. option:: online_vcpus_internal -> VCi

   Same as ``VC``, but internal usage.

.. option:: memory_used_total -> MUT

   ``MU`` + ``MUi``.

.. option:: memory_assigned_total -> MST

   ``MS`` + ``MSi``.

.. option:: cpu_time_total -> CPUsecT

   ``CPUsec`` + ``CPUisec``.

.. option:: online_vcpus_total -> VCT

   ``VC`` + ``VCi``.

Notes
-----

The clock shows the last time the screen was refreshed. It only happens when
information is outdated.

Authors
-------

| Benjamin Grande <ben.grande.b at gmail dot com>
| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
