.. program:: qvm-remove

:program:`qvm-remove` -- remove domain
======================================

.. warning::

   This page was autogenerated from command-line parser. It shouldn't be 1:1
   conversion, because it would add little value. Please revise it and add
   more descriptive help, which normally won't fit in standard ``--help``
   option.

   After rewrite, please remove this admonition.

Synopsis
--------
:command:`qvm-remove` [-h] [--verbose] [--quiet] [--force] [--force-root] [--all] [--exclude *EXCLUDE*] [--just-db] [*VMNAME* [*VMNAME* ...]]

Options
-------

.. option:: --all

   Remove  all qubes. You can use :option:`--exclude` to limit the
   qubes set. dom0 is not removed

.. option:: --exclude

   Exclude the qube from :option:`--all`.

.. option:: --force, -f

   Do not prompt for confirmation; assume 'yes'.

.. option:: --help, -h

    Show this help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --version

   Show program's version number and exit

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Bahtiar `kalkin-` Gadimov <bahtiar at gadimov dot de> 

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
