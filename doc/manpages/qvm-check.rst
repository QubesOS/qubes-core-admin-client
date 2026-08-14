.. program:: qvm-check

:program:`qvm-check` -- check qube state
=========================================

Description
-----------

:program:`qvm-check` tests whether qubes exist or meet selected conditions. It
reports matching qubes at normal verbosity; use :option:`--quiet` to suppress
output in scripts and inspect only the exit status.

When multiple conditions are supplied, a qube must meet all of them. Exit
status 0 means every named qube exists and matches, status 3 means only some of
the existing qubes match, and status 1 means none match or at least one named
qube does not exist. With no condition, existence alone is checked.

Synopsis
--------

| :command:`qvm-check` [*options*] *VMNAME* [*VMNAME* ...]
| :command:`qvm-check` [*options*] --all [--exclude *VMNAME*]

Options
-------

.. option:: --help, -h

   show this help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --all

   perform the action on all qubes

.. option:: --exclude

   Exclude the qube from :option:`--all`.

.. option:: --running

   Determine if (any of given) VM is running

.. option:: --paused

   Determine if (any of given) VM is paused

.. option:: --template

   Determine if (any of given) VM is a template

.. option:: --networked

   Determine if (any of given) VM can reach network

.. option:: --version

   Show program's version number and exit

Examples
--------

Test whether a qube exists::

   if qvm-check --quiet work; then
       echo "work exists"
   fi

List the selected qubes that are both templates and networked::

   qvm-check --verbose --template --networked fedora-42 debian-13

Check all qubes except ``vault`` and distinguish a partial match::

   qvm-check --running --all --exclude vault
   case $? in
       0) echo "all selected qubes are running" ;;
       3) echo "only some selected qubes are running" ;;
       1) echo "no selected qubes are running" ;;
   esac

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>
| Frédéric Pierret <frederic dot pierret at qubes dash os dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
