#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2019  WillyPillow <wp@nerde.pw>
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
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Template management for Qubes OS."""

import os
import subprocess
import tempfile
import typing
import sys

import qubesadmin.exc

PATH_PREFIX = '/var/lib/qubes/vm-templates'
PACKAGE_NAME_PREFIX = 'qubes-template-'
TAR_HEADER_BYTES = 512


def verify_rpm(path: str, key: str, *, nogpgcheck: bool = False,
               template_name: typing.Optional[str] = None) -> typing.Any:
    """Verify the digest and signature of a RPM package and return the package
    header.

    Note that verifying RPMs this way is prone to TOCTOU. This is okay for
    local files, but may create problems if multiple instances of
    **qvm-template** are downloading the same file, so a lock is needed in that
    case.

    :param path: Location of the RPM package
    :param key: Path to the GPG key file
    :param nogpgcheck: Whether to allow invalid GPG signatures
    :param template_name: expected template name - if specified, verifies if
           the package name matches expected template name

    :return: RPM package header. If verification fails, raises an exception.
    """
    import rpm

    assert isinstance(nogpgcheck, bool), 'Must pass a boolean for nogpgcheck'
    with open(path, 'rb') as fd:
        if not nogpgcheck:
            with tempfile.TemporaryDirectory() as rpmdb_dir:
                subprocess.check_call(
                    ['rpmkeys', '--dbpath=' + rpmdb_dir, '--import', key])
                try:
                    output = subprocess.check_output([
                        'rpmkeys',
                        '--dbpath=' + rpmdb_dir,
                        '--define=_pkgverify_level all',
                        '--define=_pkgverify_flags 0x0',
                        '--checksig',
                        '-',
                    ], env={'LC_ALL': 'C', **os.environ}, stdin=fd)
                except subprocess.CalledProcessError as e:
                    raise qubesadmin.exc.SignatureVerificationError(
                        f"Signature verification failed: {e.output.decode()}")
                if output != b'-: digests signatures OK\n':
                    raise qubesadmin.exc.SignatureVerificationError(
                        f"Signature verification failed: {output.decode()}")
            fd.seek(0)
        tset = rpm.TransactionSet()
        tset.setVSFlags(rpm.RPMVSF_MASK_NOSIGNATURES)
        hdr = tset.hdrFromFdno(fd)
    if template_name is not None:
        if hdr[rpm.RPMTAG_NAME] != PACKAGE_NAME_PREFIX + template_name:
            raise qubesadmin.exc.SignatureVerificationError(
                'Downloaded package does not match expected template name')
    return hdr


def extract_rpm(name: str, path: str, target: str) -> bool:
    """Extract a template RPM package.

    If the package contains root.img file split across multiple parts,
    only the first 512 bytes of the 00 part is retained (tar header) and
    a symlink to the rpm file is created in target directory.

    :param name: Name of the template
    :param path: Location of the RPM package
    :param target: Target path to extract to

    :return: Whether the extraction succeeded
    """
    with open(path, 'rb') as pkg_f:
        with subprocess.Popen(['rpm2archive', "-"],
                stdin=pkg_f,
                stdout=subprocess.PIPE) as rpm2archive:
            with subprocess.Popen([
                'tar', 'xz', '-C', target, f'.{PATH_PREFIX}/{name}/',
                '--exclude=root.img.part.?[!0]',
                '--exclude=root.img.part.[!0]0'
            ], stdin=rpm2archive.stdout, stdout=subprocess.DEVNULL) as tar:
                pass
    if rpm2archive.returncode != 0 or tar.returncode != 0:
        return False

    part_00_path = f'{target}/{PATH_PREFIX}/{name}/root.img.part.00'
    if os.path.exists(part_00_path):
        with subprocess.Popen([
            'truncate', f'--size={TAR_HEADER_BYTES}', part_00_path
        ]) as truncate:
            pass
        if truncate.returncode != 0:
            return False
        link_path = f'{target}/{PATH_PREFIX}/{name}/template.rpm'
        try:
            os.symlink(os.path.abspath(path),
                       f'{target}/{PATH_PREFIX}/{name}/template.rpm')
        except OSError as e:
            print(f"Failed to create {link_path} symlink: {e!s}",
                  file=sys.stderr)
            return False
    return True
