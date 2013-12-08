__all__ = """
ZERO_BYTE_CHUNK
MULTIPART_BYTERANGE
CONNECTION_CLOSE
""".split()

#======================================================================
# place for constants, type of constants
#======================================================================
class const(object):
    def __init__(self, ident):
        self._ident = ident
    
    def __repr__(self):
        return '<%s %r id=%i>' % (type(self).__name__, self._ident, id(self))

#======================================================================
# constants
#======================================================================

ZERO_BYTE_CHUNK = const.ZERO_BYTE_CHUNK = const('ZERO_BYTE_CHUNK')
MULTIPART_BYTERANGE = const.MULTIPART_BYTERANGE = const('MULTIPART_BYTERANGE')
CONNECTION_CLOSE = const.CONNECTION_CLOSE = const('CONNECTION_CLOSE')


