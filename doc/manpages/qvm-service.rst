.. program:: qvm-service

========================================================================
:program:`qvm-service` -- Manage (Qubes-specific) services started in VM
========================================================================

Synopsis
========
| :command:`qvm-service` [-l] <*vmname*>
| :command:`qvm-service` [-e|-d|-D] <*vmname*> <*service*>
| :command:`qvm-service` <*vmname*> <*service*> [on|off]

Options
=======
.. option:: --help, -h

    Show this help message and exit

.. option:: --list, -l

    List services (default action)

.. option:: --enable, -e

    Enable service

.. option:: --disable, -d

    Disable service

.. option:: --default, -D, --delete, --unset

    Reset service to its default state (remove from the list). Default state
    means "lets VM choose" and can depend on VM type (NetVM, AppVM etc).

.. option:: --verbose, -v

   increase verbosity

.. option:: --quiet, -q

   decrease verbosity

.. option:: --version

   Show program's version number and exit

Supported services
==================

This list can be incomplete as VM can implement any additional service without
knowledge of qubes-core code.

meminfo-writer
    Default: enabled everywhere excluding NetVM

    This service reports VM memory usage to dom0, which effectively enables
    dynamic memory management for the VM.

    .. note::

        This service is managed by dom0 code and is not visible for *qvm-service* tool.

qubes-firewall
    Default: enabled only in ProxyVM

    Dynamic firewall manager, based on settings in dom0 (qvm-firewall, firewall tab in qubes-manager).
    This service is not supported in netvms.

qubes-network
    Default: enabled only in NetVM and ProxyVM

    Expose network for other VMs. This includes enabling network forwarding,
    MASQUERADE, DNS redirection and basic firewall.

qubes-update-check
    Default: enabled

    Notify dom0 about updates available for this VM. This is shown in
    qubes-manager as 'update-pending' flag.

cups
    Default: enabled only in AppVM

    Enable CUPS service. The user can disable cups in VM which do not need
    printing to speed up booting.

crond
    Default: disabled

    Enable CRON service.

network-manager
    Default: enabled in every qube that has no netvm and has provides_network
    preference set to True

    Enable NetworkManager. Only VM with direct access to network device needs
    this service, but can be useful in ProxyVM to ease VPN setup.

clocksync
    Default: disabled

    Enable NTPD (or equivalent) service. If disabled, VM will sync clock with
    selected VM (aka ClockVM) instead. ClockVM for particular VM can be set in
    policy of qubes.GetDate service, using target= parameter.

qubes-yum-proxy
    Deprecated name for qubes-updates-proxy.

qubes-updates-proxy
    Default: enabled in NetVM

    Provide proxy service, which allow access only to yum repos. Filtering is
    done based on URLs, so it shouldn't be used as leak control (pretty easy to
    bypass), but is enough to prevent some erroneous user actions.

yum-proxy-setup
    Deprecated name for updates-proxy-setup.

updates-proxy-setup
    Default: enabled in AppVM (also in templates)

    Setup yum at startup to use qubes-yum-proxy service.

    .. note::

       this service is automatically enabled when you allow VM to access updates
       proxy and disabled when you deny access to updates proxy.

disable-default-route
    Default: disabled

    Disables the default route for networking.  Enabling  this  service
    will  prevent the creation of the default route, but the VM will
    still be able to reach it's direct neighbors.  The functionality
    is implemented in /usr/lib/qubes/setup-ip.

disable-dns-server
    Default: disabled

    Enabling this service will result in an empty /etc/resolv.conf.
    The functionality is implemented in /usr/lib/qubes/setup-ip.

lightdm:
    Default: disabled

    Start `lightdm` and avoid starting `qubes-gui-agent`.
    In this case, `lightdm` is responsible to start the `X.org` server.

software-rendering:
    Default: enabled

    Sets variables that enforces the use of software rendering. Disable this
    service in case your qube has access to a graphics card.

guivm:
    Default: disabled

    Enable common mandatory functionalities in a GuiVM.

guivm-gui-agent:
    Default: disabled

    When enabled, it starts hybrid GuiVM specific functionality.

guivm-vnc:
    Default: disabled

    When enabled, it starts VNC GuiVM specific functionality.

tracker:
    Default: disabled

    When enabled, GNOME Tracker is started.  This provides desktop search
    features for the GNOME desktop and for certain GNOME applications  By
    default, it will parse and index files in:

    - ~/Documents, ~/Pictures, ~/Music, and ~/Videos, including all subdirectories
      of these directories.

    - The directories ~ and ~/Downloads, but _not_ including any subdirectories
      thereof.

    If GNOME Tracker is not installed in the qube, this has no effect.

evolution-data-server:
    Default: disabled

    When enabled, Evolution Data Server is started.  This provides
    an API for applications to integrate with the Evolution mail and calendar
    client, and is mostly used by GNOME applications.  If Evolution Data
    Server is not installed in the qube, this has no effect.

usb-reset-on-attach:
    Default: disabled

    Reset devices when attaching them using qvm-usb (or its GUI equivalent).
    This is known to help with some devices, that cannot deal with re-attaching
    to another driver.

Authors
=======
| Joanna Rutkowska <joanna at invisiblethingslab dot com>
| Rafal Wojtczuk <rafal at invisiblethingslab dot com>
| Marek Marczykowski <marmarek at invisiblethingslab dot com>
| Frédéric Pierret <frederic dot pierret at qubes dash os dot org>

| For complete author list see: https://github.com/QubesOS/qubes-core-admin-client.git
