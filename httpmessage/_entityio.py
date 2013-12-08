import cStringIO, os
import httpmessage.dispatch as dispatch
import httpmessage.exc as exc
from httpmessage._entityreader import EntityReader

class FilelikeWrap(object):

    """A proxy for a wrapped file-like object. Shares internal data storage
    format with :class:`EntityIO`, so that things will continue to work if an
    object of type :class:`EntityIO` has its class changed to
    :class:`FilelikeWrap` (which is exactly what :class:`EntityIO` does when
    it finishes reading an external data source).

    Uses the internal object to implement the following methods:
    :meth:`close`, :meth:`flush`, :meth:`fileno`, :meth:`isatty`,
    :meth:`read`, :meth:`readline`, :meth:`readlines`, :meth:`seek`,
    :meth:`tell`, :meth:`truncate`, :meth:`write`, :meth:`writelines`.

    """

    FilelikeClass = cStringIO.StringIO

    filelike_methods = """close flush fileno isatty read readline
    readlines seek tell truncate write writelines
    """

    def __init__(self):
        self._fileobj = self.FilelikeClass()

    def __iter__(self):
        return iter(self._fileobj)
    
    def __getattr__(self, attrname):
        if attrname in self.filelike_methods:
            return getattr(self._fileobj, attrname)
        raise AttributeError(attrname)


class EntityIO(object):

    """A file-like object which knows how to read an HTTP entity out of some
    underlying file-like object, given an ``entity_size``.

    ``entity_size`` can be a non-negative integer, or it can be a constant;
    one of:
    
    * :attr:`httpmessage.const.ZERO_BYTE_CHUNK`
    * :attr:`httpmessage.const.MULTIPART_BYTERANGE`
    * :attr:`httpmessage.const.CONNECTION_CLOSE`

    :class:`EntityIO` implements the following file-like methods:
    :meth:`read`, :meth:`readline`, :meth:`seek`, :meth:`tell`, :meth:`write`.
    """

    FilelikeClass = cStringIO.StringIO 
    _pos = None 
    _entityreader = None
    _is_dispatching = False
    buffering_started = False

    #......................................................................
    def __init__(self, raw_fileobj, entity_size):
        self._entityreader = EntityReader(raw_fileobj, entity_size)
        self._pos = 0
        self._fileobj = self.FilelikeClass()
    
    #......................................................................
    def _transmogrify(self):
        if self._is_dispatching: raise exc.ReentrantDispatch('_transmogrify')
        #print 'transmogrifying %r' % self
        del self._entityreader
        pos = self.tell()
        self.__class__ = FilelikeWrap
        self.seek(pos, os.SEEK_SET)
        dispatch.send(dispatch.signal.END_DATA, self, None)
        self.seek(pos, os.SEEK_SET)

    #......................................................................
    def _fileobj_len(self):
        if self._is_dispatching: raise exc.ReentrantDispatch('_fileobj_len')
        self._fileobj.seek(0, os.SEEK_END)
        return self._fileobj.tell()

    
    #......................................................................
    def buffer_chunk(self):
        """Buffers the next chunk of whatever size is appropriate, given the
        nature of the underlying
        :class:`httpmessage._entityreader.EntityReader` subclass. 

        When the last chunk is buffered, the :class:`EntityIO` object should
        transform itself (by changing its :attr:`__class__`) into a
        :class:`FilelikeWrap` object instead."""
        if self._is_dispatching: raise exc.ReentrantDispatch('buffer_chunk')
        self.buffering_started = True
        #print 'call buffer_chunk'
        self._fileobj.seek(0, os.SEEK_END)
        data, raw_data = self._entityreader.readchunk()
        if not raw_data:
            self._transmogrify()
        else:
            self._fileobj.write(data)
            try:
                self._is_dispatching = True
                responses = dispatch.send(
                        dispatch.signal.RAW_DATA, self, raw_data
                    )
            finally:
                self._is_dispatching = False
            if dispatch.response.ABORT in responses:
                raise exc.BufferingAbort(
                        'received response.ABORT while buffering', responses)
        return data, raw_data

    #......................................................................
    def buffer_all(self):

        """By calling :meth:`buffer_chunk` repeatedly, buffer all available
        data."""

        #print 'call buffer_all'
        if self._entityreader:
            while True:
                data, raw_data = self.buffer_chunk()
                if not raw_data:
                    break

    #......................................................................
    def buffer_to(self, size):

        """By calling :meth:`buffer_chunk` as necessary, buffer data until
        reaching a size greater than or equal to the specified ``size``, or
        until all available data is buffered. """

        if self._entityreader:
            current_size = self._fileobj_len()
            while current_size < size:
                data, raw_data = self.buffer_chunk()
                current_size += len(data)
                if not raw_data:
                    break

    #......................................................................
    def read(self, size=None):
        if self._is_dispatching: raise exc.ReentrantDispatch('read')
        current_data_size = self._fileobj_len()
        if size is None:
            self.buffer_all()
        else:
            need = max(0, self._pos + size - current_data_size)
            if need:
                self.buffer_to(current_data_size + need)

        self._fileobj.seek(self._pos, os.SEEK_SET)
        if size is not None:
            data = self._fileobj.read(size)
        else:
            data = self._fileobj.read()
        self._pos = self._fileobj.tell()
        return data
    
    #......................................................................
    def readline(self, size=None):
        if self._is_dispatching: raise exc.ReentrantDispatch('readline')
        #print 'calling readline'
        # this isn't ideal; I don't *actually* need to  buffer the entire
        # input before being able to find a newline in the entity body.
        # but, this f'n is considerably more complicated (read, check,
        # read, check, ...) if I do it efficiently...maybe that isn't
        # necessary
        self.buffer_all()
        return self.readline()
        # # I just became a different class.  I could call myself.
        # self._fileobj.seek(self._pos, os.SEEK_SET)
        # if size is not None:
        #     data = self._fileobj.readline(size)
        # else:
        #     data = self._fileobj.readline()
        # 
        # # this is irrelelvant; I'll never look at _pos again...
        # self._pos = self._fileobj.tell()
        # return data

    #......................................................................
    def seek(self, position, whence=os.SEEK_SET):
        # whence os.SEEK_SET or 0 == relative to start
        # whence os.SEEK_CUR or 1 == relative to current position
        # whence os.SEEK_END or 2 == relative to end
        if self._is_dispatching: raise exc.ReentrantDispatch('seek')
        if whence not in [os.SEEK_SET, os.SEEK_CUR, os.SEEK_END]:
            raise ValueError('invalid whence %r' % whence)

        if whence == os.SEEK_END:
            self.buffer_all()
        else:
            need = 0
            current_data_size = self._fileobj_len()
            if whence == os.SEEK_CUR:
                need = max(0, self._pos + position - current_data_size )
            elif whence == os.SEEK_SET:
                need = max(0, position - current_data_size)
            if need:
                self.buffer_to(current_data_size + need)
        
        self._fileobj.seek(position, whence)
        self._pos = self._fileobj.tell()

    #......................................................................
    def tell(self):
        return self._pos

    #......................................................................
    def write(self, data):
        if self._is_dispatching: raise exc.ReentrantDispatch('write')
        self.buffer_all()
        self._fileobj.seek(self._pos, os.SEEK_SET)
        self._fileobj.write(data)
        # I became another class; I won't look at _pos again, but still...
        self._pos = self._fileobj.tell()
