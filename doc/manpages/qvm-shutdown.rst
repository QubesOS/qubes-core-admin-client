.. program:: qvm-shutdown

:program:`qvm-shutdown` -- Gracefully shut down a qube
======================================================

Synopsis
--------

:command:`qvm-shutdown` [-h] [--verbose] [--quiet] [--all] [--exclude *EXCLUDE*] [--wait] [--timeout *TIMEOUT*] [*VMNAME*]

Options
-------

.. option:: --help, -h

   show the help message and exit

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --all

   perform the action on all qubes; implies :option:`--force` unless
   :option:`--exclude` is also specified

.. option:: --exclude=EXCLUDE

   exclude the qube from :option:`--all`

.. option:: --wait

   Wait for the VMs to shut down. If a qube cannot be shut down because
   other running qubes depend on it, the command retries the shutdown
   after other requested shutdowns complete. This allows dependent qubes
   to shut down before the qubes they depend on. When :option:`--all` is
   specified without :option:`--exclude`, it implies :option:`--force`,
   which bypasses this dependency check.

.. option:: --timeout

   timeout after which domains are killed when using :option:`--wait`

.. option:: --force

   force qube shutdown, regardless of whether there exist any connected domains
   (such as those using it as network VM)

.. option:: --dry-run

   don't really shutdown or kill the domains; useful with :option:`--wait`

.. option:: --version

   Show program's version number and exit


Examples
--------

To shut down a network stack, waiting for dependent qubes to stop:

.. code-block:: console

   qvm-shutdown --wait sys-net sys-firewall sys-whonix


Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
