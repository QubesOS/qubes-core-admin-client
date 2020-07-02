# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2020 Marek Marczykowski-Górecki
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
This is a set of helper classes, designed to facilitate importing an X extension
that's not supported by default by xcffib.
"""
import io
import struct
import xcffib



class XkbUseExtensionReply(xcffib.Reply):
    """Helper class to parse XkbUseExtensionReply
    Contains hardcoded values based on X11/XKBproto.h"""
    # pylint: disable=too-few-public-methods
    def __init__(self, unpacker):
        if isinstance(unpacker, xcffib.Protobj):
            unpacker = xcffib.MemoryUnpacker(unpacker.pack())
        xcffib.Reply.__init__(self, unpacker)
        base = unpacker.offset
        self.major_version, self.minor_version = unpacker.unpack(
            "xx2x4xHH4x4x4x4x")
        self.bufsize = unpacker.offset - base


class XkbUseExtensionCookie(xcffib.Cookie):
    """Helper class for use in loading Xkb extension"""
    reply_type = XkbUseExtensionReply


class XkbGetStateReply(xcffib.Reply):
    """Helper class to parse XkbGetState; copy&paste from X11/XKBproto.h"""
    # pylint: disable=too-few-public-methods
    _typedef = """
        BYTE    type;
        BYTE    deviceID;
        CARD16  sequenceNumber B16;
        CARD32  length B32;
        CARD8   mods;
        CARD8   baseMods;
        CARD8   latchedMods;
        CARD8   lockedMods;
        CARD8   group;
        CARD8   lockedGroup;
        INT16   baseGroup B16;
        INT16   latchedGroup B16;
        CARD8   compatState;
        CARD8   grabMods;
        CARD8   compatGrabMods;
        CARD8   lookupMods;
        CARD8   compatLookupMods;
        CARD8   pad1;
        CARD16  ptrBtnState B16;
        CARD16  pad2 B16;
        CARD32  pad3 B32;"""
    _type_mapping = {
        "BYTE": "B",
        "CARD16": "H",
        "CARD8": "B",
        "CARD32": "I",
        "INT16": "h",
    }

    def __init__(self, unpacker):
        if isinstance(unpacker, xcffib.Protobj):
            unpacker = xcffib.MemoryUnpacker(unpacker.pack())
        xcffib.Reply.__init__(self, unpacker)
        base = unpacker.offset

        # dynamic parse of copy&pasted struct content, for easy re-usability
        for line in self._typedef.splitlines():
            line = line.strip()
            line = line.rstrip(';')
            if not line:
                continue
            typename, name = line.split()[:2]  # ignore optional third part
            setattr(self, name, unpacker.unpack(self._type_mapping[typename]))

        self.bufsize = unpacker.offset - base


class XkbGetStateCookie(xcffib.Cookie):
    """Helper class for use in parsing Xkb GetState"""
    reply_type = XkbGetStateReply


class XkbExtension(xcffib.Extension):
    """Helper class to load and use Xkb xcffib extension; needed
    because there is not XKB support in xcffib."""
    # pylint: disable=invalid-name,missing-function-docstring
    def UseExtension(self, is_checked=True):
        buf = io.BytesIO()
        buf.write(struct.pack("=xx2xHH", 1, 0))
        return self.send_request(0, buf, XkbGetStateCookie,
                                 is_checked=is_checked)

    def GetState(self, deviceSpec=0x100, is_checked=True):
        buf = io.BytesIO()
        buf.write(struct.pack("=xx2xHxx", deviceSpec))
        return self.send_request(4, buf, XkbGetStateCookie,
                                 is_checked=is_checked)


key = xcffib.ExtensionKey("XKEYBOARD")
# this is a lie: there are events and errors types
_events = {}
_errors = {}

# pylint: disable=protected-access
xcffib._add_ext(key, XkbExtension, _events, _errors)
