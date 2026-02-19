#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki
#                               <marmarek@invisiblethingslab.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program; if not, see <http://www.gnu.org/licenses/>.

'''Configuration variables/constants'''

#: path to qubesd socket
QUBESD_SOCKET = '/var/run/qubesd.sock'
QREXEC_CLIENT = '/usr/lib/qubes/qrexec-client'
QREXEC_CLIENT_VM = '/usr/bin/qrexec-client-vm'
QUBESD_RECONNECT_DELAY = 1.0
QREXEC_SERVICES_DIR = '/etc/qubes-rpc'

defaults = {
    'template_label': 'black',
    'shutdown_timeout': 60,
}
