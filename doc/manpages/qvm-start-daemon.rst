.. program:: qvm-start-daemon

:program:`qvm-start-daemon` -- start GUI/AUDIO for qube(s)
==========================================================

.. note::

   `qvm-start-gui` has been renamed to `qvm-start-daemon` as it handles now
   `gui` and `audio`.

Description
-----------

:program:`qvm-start-daemon` launches the GUI and audio processes that connect
running qubes to their configured GuiVM and AudioVM. It is normally started by
Qubes system services inside those service qubes rather than run directly by
users.

Without :option:`--watch`, the command starts missing GUI or audio processes
for the selected qubes that are already running. In watch mode it keeps an
event connection open, handles later qube startups and shutdowns, and keeps a
PID file so only one watcher runs. :option:`--notify-monitor-layout` signals
the watcher to resend the current monitor layout; it cannot be combined with
:option:`--watch`.

Synopsis
--------

:command:`qvm-start-daemon` [*options*] [*VMNAME* [*VMNAME* ...]]

Options
-------

.. option:: --help, -h

   show this help message and exit

.. option:: --debug, -d

   Show debug messages

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --all

   perform the action on all qubes

.. option:: --exclude

   exclude the qube from --all

.. option:: --watch

   Keep watching for further domain startups

.. option:: --force-stubdomain

   Start GUI to stubdomain-emulated VGA, even if gui-agent is running in the VM

.. option:: --force

   Force running, even if this isn't GUI/Audio domain. GUI domain is a domain
   with 'guivm' qvm-service enabled. Similarly for Audio domain it is
   'audiovm' qvm-service.

.. option:: --kde

   Set KDE specific arguments to gui-daemon - required for proper windows
   decoration on KDE.

.. option:: --pidfile

   Pidfile path to create in --watch mode

.. option:: --notify-monitor-layout

   Notify running instance in --watch mode about changed monitor layout

.. option:: --version

   Show program's version number and exit

Operation modes
---------------

One-shot mode
^^^^^^^^^^^^^

With explicit qube names, or with :option:`--all`, start the missing GUI and
audio processes for running qubes assigned to the local GuiVM or AudioVM.
Halted qubes are ignored.

Watch mode
^^^^^^^^^^

Use :option:`--watch` to keep listening for lifecycle events. The watcher also
handles qubes that were already running when its event connection was
established, and cleans up generated state after a qube stops.

Monitor-layout notification
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Use :option:`--notify-monitor-layout` from the same service qube to notify the
watching instance after the display layout changes.

Authors
-------

| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Wojtek Porczyk <woju at invisiblethingslab dot com>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git

.. vim: ts=3 sw=3 et tw=80
