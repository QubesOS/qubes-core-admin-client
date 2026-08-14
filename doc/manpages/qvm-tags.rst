.. program:: qvm-tags

:program:`qvm-tags` -- manage domain's tags
===========================================

Description
-----------

Tags are arbitrary labels attached to a qube. They can be used to group qubes
for administrative tasks and policy rules without changing the qubes' names or
classes. A qube may have any number of tags.

With no command, or with the ``list`` command, :program:`qvm-tags` prints the
qube's tags. When a tag is supplied to ``list``, the command instead tests
membership: it prints the tag and exits with status 0 when present, and prints
nothing and exits with status 1 when absent. This form is suitable for shell
scripts.

Synopsis
--------

| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* {list,ls,l} [*TAG*]
| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* {add,a,set} *TAG* ...
| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* {del,d,unset,u} *TAG* ...


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

List tags. If tag name is given, check if this tag is set for the VM and signal
this with exit code (0 - tag is set, 1 - it is not).

aliases: ls, l

add
^^^

| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* add *TAG* [*TAG* ...]

Add tag(s) to a VM. If tag is already set for given VM, do nothing.

aliases: a, set

del
^^^

| :command:`qvm-tags` [-h] [--verbose] [--quiet] *VMNAME* del *TAG* [*TAG* ...]

Delete a tag from a VM. If the tag is not set for the VM, do nothing.

aliases: d, unset, u

Examples
--------

Add two tags to a qube, then list all its tags::

   qvm-tags work add project-x disposable
   qvm-tags work list

Use the membership-test form in a shell script::

   if qvm-tags work list project-x >/dev/null; then
       echo "work belongs to project-x"
   fi

Remove a tag::

   qvm-tags work del project-x


Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
