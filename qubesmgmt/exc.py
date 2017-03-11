# -*- encoding: utf8 -*-
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

'''Exception hierarchy.'''


class QubesException(Exception):
    '''Base exception for all Qubes-related errors.'''
    def __init__(self, message_format, *args, **kwargs):
        # TODO: handle translations
        super(QubesException, self).__init__(
            message_format % tuple(int(d) if d.isdigit() else d for d in args),
            **kwargs)


class QubesVMNotFoundError(QubesException, KeyError):
    '''Domain cannot be found in the system'''


class QubesVMError(QubesException):
    '''Some problem with domain state.'''


class QubesVMNotStartedError(QubesVMError):
    '''Domain is not started.

    This exception is thrown when machine is halted, but should be started
    (that is, either running or paused).
    '''


class QubesVMNotRunningError(QubesVMNotStartedError):
    '''Domain is not running.

    This exception is thrown when machine should be running but is either
    halted or paused.
    '''


class QubesVMNotPausedError(QubesVMNotStartedError):
    '''Domain is not paused.

    This exception is thrown when machine should be paused, but is not.
    '''


class QubesVMNotSuspendedError(QubesVMError):
    '''Domain is not suspended.

    This exception is thrown when machine should be suspended but is either
    halted or running.
    '''


class QubesVMNotHaltedError(QubesVMError):
    '''Domain is not halted.

    This exception is thrown when machine should be halted, but is not (either
    running or paused).
    '''


class QubesNoTemplateError(QubesVMError):
    '''Cannot start domain, because there is no template'''


class QubesValueError(QubesException, ValueError):
    '''Cannot set some value, because it is invalid, out of bounds, etc.'''
    pass


class QubesPropertyValueError(QubesValueError):
    '''Cannot set value of qubes.property, because user-supplied value is wrong.
    '''


class QubesNotImplementedError(QubesException, NotImplementedError):
    '''Thrown at user when some feature is not implemented'''


class BackupCancelledError(QubesException):
    '''Thrown at user when backup was manually cancelled'''


class QubesMemoryError(QubesException, MemoryError):
    '''Cannot start domain, because not enough memory is available'''


class QubesDaemonCommunicationError(QubesException, IOError):
    '''Error while communicating with qubesd, may mean insufficient
    permissions, as well'''


# pylint: disable=too-many-ancestors
class QubesDaemonNoResponseError(QubesDaemonCommunicationError):
    '''Got empty response from qubesd'''
