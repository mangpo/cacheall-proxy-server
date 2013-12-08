import httpmessage.exc as exc
from httpmessage.const import const

#======================================================================
class EntityReader(object):
    def __init__(self, fileobj, entity_size):
        self._fileobj = fileobj
        self._size = entity_size

        if entity_size == const.ZERO_BYTE_CHUNK:
            self.__class__ = ChunkedEntityReader
        elif entity_size == const.MULTIPART_BYTERANGE:
            self.__class__ = MultipartEntityReader
        elif entity_size == const.CONNECTION_CLOSE:
            self.__class__ = TilCloseEntityReader
        elif entity_size == 0:
            self.__class__ = NullEntityReader
        elif isinstance(entity_size, int):
            self.__class__ = SimpleEntityReader
        else:
            raise ValueError('invalid entity_size %r' % entity_size)


    def readchunk(self):
        """Read a chunk of data from the reader's file object, of whatever
        size it makes sense for this subtype of EntityReader.
        
        Returns a tuple of (transfer_decoded_data, raw_data)"""
        raise NotImplementedError

    def __iter__(self):
        while True:
            data, raw_data = chunk = self.readchunk()
            if not raw_data:
                raise StopIteration
            yield chunk
    
#======================================================================
class SimpleEntityReader(EntityReader):

    """:class:`EntityReader` subclass for HTTP entities whose size is
    accurately reflected by the :mailheader:`Content-Length` header. """


    _pos = 0
    read_size = 4096

    def readchunk(self):
        EntityReader.readchunk.__doc__
        size_left = self._size - self._pos
        this_read_size = min(self.read_size, size_left)
        
        assert this_read_size >= 0, "over-read the data stream!"

        if this_read_size == 0:
            return '', ''
        
        raw_data = self._fileobj.read(this_read_size)
        if not raw_data:
            msg = "data stream ended at %r with %r bytes remaining" % (
                    self._pos, size_left)
            raise exc.EntityReadError(msg, raw_data)
        self._pos += len(raw_data)
        return raw_data, raw_data

#======================================================================
class TilCloseEntityReader(EntityReader):

    """:class:`EntityReader` subclass for HTTP entities who should be read
    until the end of file, or the socket closes."""


    read_size = 4096

    def readchunk(self):
        EntityReader.readchunk.__doc__

        raw_data = self._fileobj.read(self.read_size)
        if not raw_data:
            return '', ''
        
        return raw_data, raw_data


#======================================================================
class ChunkedEntityReader(EntityReader):

    """:class:`EntityReader` subclass for HTTP entities transfered via the 
    *chunked* :mailheader:`Transfer-Encoding`."""

    finished = False
    
    def _verify_read(self, check_data, msg, raw_data):
        if not check_data:
            msg = 'no data read during %r' % msg
            raise exc.EntityReadError(msg, raw_data)

    def readchunk(self):
        EntityReader.readchunk.__doc__
        # we're expecting a chunk to consist of the following:
        # 1. the size of the chunk in hex, followed by '\r\n'
        # 2. the chunk data, of exactly the size specified in (1)
        # 3. and end-chunk separator, consisting exactly of '\r\n'
        #
        # The last chunk there is to read will be the zero chunk (ie, the
        # size will be zero, with no chunk data).

        # did we previously read the zero chunk?
        if self.finished:
            return '', ''

        # read the chunk size from the fileobj
        raw_data = self._fileobj.readline()
        self._verify_read(raw_data, 'read chunk size', raw_data)
        try:
            size = int(raw_data.strip(),16)
        except ValueError:
            msg = 'invalid chunk size %r' % raw_data.strip()
            raise exc.EntityReadError(msg, raw_data)

        # read the chunk data
        if size == 0:
            chunk_data = ''
            self.finished = True
        else:
            chunk_data = self._fileobj.read(size)
            self._verify_read(chunk_data, 'read chunk data', raw_data)
            if len(chunk_data) != size:
                msg = 'expected chunk of size %r, but size was %r' % (
                        size, len(chunk_data))
                raise exc.EntityReadError(msg, chunk_data)
            raw_data += chunk_data

        # read the end separator
        sep = self._fileobj.readline()
        self._verify_read(sep, 'read chunk separator', raw_data)
        if sep != '\r\n':
            msg = r"end separator wrong; expected '\r\n', found %r" % sep
            raise exc.EntityReadError(msg, raw_data+sep)
        raw_data += sep
        
        return chunk_data, raw_data


#======================================================================
class MultipartEntityReader(EntityReader):

    """:class:`EntityReader` subclass...  Not implemented yet."""
    
    
    def readchunk(self):
        EntityReader.readchunk.__doc__
        raise NotImplementedError

#======================================================================
class NullEntityReader(EntityReader):

    """:class:`EntityReader` subclass for HTTP entities of zero length."""

    def readchunk(self):
        EntityReader.readchunk.__doc__
        return '', ''
