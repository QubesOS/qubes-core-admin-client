.. program:: qvm-shutdown

:program:`qvm-shutdown` -- Gracefully shut down a qube
======================================================

Synopsis
--------

:command:`qvm-shutdown` [-h] [--verbose] [--quiet] [--all] [--force] [--exclude *EXCLUDE*] [--wait] [--timeout *TIMEOUT*] [*VMNAME*]

Options
-------

.. option:: --help, -h

   show the help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --all

   perform the action on all qubes; implies :option:`--force`

.. option:: --exclude=EXCLUDE

   exclude the qube from :option:`--all`

.. option:: --wait

   wait for the VMs to shut down. If some domains are providing network to other
   domains, wait for those domains to shut down before shutting down their
   dependents, unless :option:`--all` was specified

.. option:: --timeout

   timeout after which domains are killed when using :option:`--wait`

.. option:: --force

   force qube shutdown, regardless of whether there exist any connected domains
   (such as those using it as network VM)

.. option:: --dry-run

   don't really shutdown or kill the domains; useful with :option:`--wait`

.. option:: --version

   Show program's version number and exit


Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
