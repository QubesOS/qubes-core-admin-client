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

"""
Qubes OS exception hierarchy
"""


class QubesException(Exception):
    """Exception that can be shown to the user"""

    def __init__(self, message_format: str, *args, **kwargs):
        # TODO: handle translations
        super().__init__(
            message_format % tuple(int(d) if d.isdigit() else d for d in args),
            **kwargs
        )


class QubesVMNotFoundError(QubesException, KeyError):
    """Domain cannot be found in the system"""

    def __str__(self) -> str:
        # KeyError overrides __str__ method
        return QubesException.__str__(self)


class QubesVMInvalidUUIDError(QubesException):
    """Domain UUID is invalid"""


class QubesVMError(QubesException):
    """Some problem with domain state."""


class QubesVMInUseError(QubesVMError):
    """VM is in use, cannot remove."""


class QubesVMNotStartedError(QubesVMError):
    """Domain is not started.

    This exception is thrown when machine is halted, but should be started
    (that is, either running or paused).
    """


class QubesVMNotRunningError(QubesVMNotStartedError):
    """Domain is not running.

    This exception is thrown when machine should be running but is either
    halted or paused.
    """


class QubesVMNotPausedError(QubesVMNotStartedError):
    """Domain is not paused.

    This exception is thrown when machine should be paused, but is not.
    """


class QubesVMNotSuspendedError(QubesVMError):
    """Domain is not suspended.

    This exception is thrown when machine should be suspended but is either
    halted or running.
    """


class QubesVMNotHaltedError(QubesVMError):
    """Domain is not halted.

    This exception is thrown when machine should be halted, but is not (either
    running or paused).
    """


class QubesVMShutdownTimeoutError(QubesVMError):
    """Domain shutdown timed out."""


class QubesNoTemplateError(QubesVMError):
    """Cannot start domain, because there is no template"""


class QubesPoolInUseError(QubesException):
    """VM is in use, cannot remove."""


class QubesValueError(QubesException, ValueError):
    """Cannot set some value, because it is invalid, out of bounds, etc."""


class QubesPropertyValueError(QubesValueError):
    """
    Cannot set value of qubes.property, because user-supplied value is wrong.
    """


class QubesNoSuchPropertyError(QubesException, AttributeError):
    """Requested property does not exist"""


class QubesNotImplementedError(QubesException, NotImplementedError):
    """Thrown at user when some feature is not implemented"""


class BackupCancelledError(QubesException):
    """Thrown at user when backup was manually cancelled"""


class BackupAlreadyRunningError(QubesException):
    """Thrown at user when they try to run the same backup twice at
    the same time"""


class QubesMemoryError(QubesVMError, MemoryError):
    """Cannot start domain, because not enough memory is available"""


class QubesFeatureNotFoundError(QubesException, KeyError):
    """Feature not set for a given domain"""

    def __str__(self) -> str:
        # KeyError overrides __str__ method
        return QubesException.__str__(self)


class QubesTagNotFoundError(QubesException, KeyError):
    """Tag not set for a given domain"""

    def __str__(self) -> str:
        # KeyError overrides __str__ method
        return QubesException.__str__(self)


class QubesLabelNotFoundError(QubesException, KeyError):
    """Label does not exists"""

    def __str__(self) -> str:
        # KeyError overrides __str__ method
        return QubesException.__str__(self)


class ProtocolError(AssertionError):
    """Raised when something is wrong with data received"""


class PermissionDenied(Exception):
    """Raised deliberately by handlers when we decide not to cooperate"""


class DeviceNotAssigned(QubesException, KeyError):
    """
    Trying to unassign not assigned device.
    """


class DeviceAlreadyAttached(QubesException, KeyError):
    """
    Trying to attach already attached device.
    """


class DeviceAlreadyAssigned(QubesException, KeyError):
    """
    Trying to assign already assigned device.
    """


class UnrecognizedDevice(QubesException, ValueError):
    """
    Device identity is not as expected.
    """


class UnexpectedDeviceProperty(QubesException, ValueError):
    """
    Device has unexpected property such as backend_domain, devclass etc.
    """


class StoragePoolException(QubesException):
    """A general storage exception"""


### core-admin-client specific exceptions:


class QubesDaemonCommunicationError(QubesException):
    """Error while communicating with qubesd, may mean insufficient
    permissions as well"""


class BackupRestoreError(QubesException):
    """Restoring a backup failed"""

    def __init__(self, msg: str, backup_log: bytes | None=None):
        super().__init__(msg)
        self.backup_log = backup_log


# pylint: disable=too-many-ancestors
class QubesDaemonAccessError(QubesDaemonCommunicationError):
    """Got empty response from qubesd. This can be lack of permission,
    or some server-side issue."""


class QubesPropertyAccessError(QubesDaemonAccessError, AttributeError):
    """Failed to read/write property value, cause is unknown (insufficient
    permissions, no such property, invalid value, other)"""

    def __init__(self, prop: str):
        super().__init__("Failed to access '%s' property" % prop)



class QubesNotesError(QubesException):
    """Some problem with qube notes."""

# legacy name
QubesDaemonNoResponseError = QubesDaemonAccessError
