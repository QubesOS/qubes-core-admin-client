# RPM header tags
# Generated with the following command:
# ``grep -Po '(RPMTAG[A-Z_]*)' tools/qvm_template.py | sort | uniq``
RPMTAG_BUILDTIME   = 1
RPMTAG_DESCRIPTION = 2
RPMTAG_EPOCHNUM    = 3
RPMTAG_LICENSE     = 4
RPMTAG_NAME        = 5
RPMTAG_RELEASE     = 6
RPMTAG_SIGGPG      = 7
RPMTAG_SIGPGP      = 8
RPMTAG_SUMMARY     = 9
RPMTAG_URL         = 10
RPMTAG_VERSION     = 11

class error(BaseException):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class hdr():
    pass

class keyring():
    def addKey(self, *args):
        pass

class pubkey():
    pass

class TransactionSet():
    def setKeyring(self, *args):
        pass

class transaction():
    class TransactionSet():
        def setKeyring(self, *args):
            pass

def labelCompare(a, b):
    # Pretend that we're comparing the versions lexographically in the stub
    return (a > b) - (a < b)
