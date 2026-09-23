.. program:: qvm-tags

:program:`qvm-tags` -- manage domain's tags
===========================================

Synopsis
--------

| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* [{list,ls,l}] [*TAG*]
| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* {add,a,set} *TAG* [*TAG* ...]
| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* {del,d,unset,u} *TAG*

Description
-----------

This tool lists, adds, and removes tags of a qube. A tag is a simple label
attached to a qube; it holds no value, it is either present or absent.

Tags matter mostly for qrexec policy: rules in
``/etc/qubes/policy.d`` may match qubes by tag using the ``@tag:some-tag``
keyword instead of listing qube names one by one. This allows granting (or
denying) a service to a whole group of qubes and having new qubes join the
group by simply receiving the tag.

Some tags are managed automatically by Qubes OS. For example, each qube
created through the Admin API by another qube gets a ``created-by-<name>``
tag, and qubes with ``audiovm-<name>`` or ``guivm-<name>`` tags have the
respective qube as their Audio/GUI virtual machine. Tags of this kind are
maintained by the system and cannot be freely modified.

When run without any command, the default is ``list``.

Options
-------

.. option:: --help, -h

   Show the help message and exit.

.. option:: --verbose, -v

   Increase verbosity.

.. option:: --quiet, -q

   Decrease verbosity.

.. option:: --version

   Show program's version number and exit

Commands
--------

list
^^^^

| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* list [*TAG*]

List tags of the given qube, one per line, sorted alphabetically. If a tag
name is given, check whether this tag is set for the qube and signal the
result with the exit code (0 - tag is set, 1 - it is not); the tag is also
printed if present.

aliases: ls, l

add
^^^

| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* add *TAG* [*TAG* ...]

Add tag(s) to a qube. If a tag is already set for the given qube, do nothing.

aliases: a, set

del
^^^

| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* del *TAG*

Delete a tag from a qube. If the tag is not set for the given qube, do
nothing.

aliases: d, unset, u


Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
