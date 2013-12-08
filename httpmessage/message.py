import _setup
import os
import sys
import inspect
import itertools
import urlparse
import socket
import operator
import mimetypes

import httpmessage._headers as _headers
import httpmessage._mapio as _mapio
import httpmessage._headerfield as field
import httpmessage._socketadaptor as _socketadaptor
import httpmessage._entityio as _entityio
import httpmessage._contenttype as _contenttype

import httpmessage.dispatch as dispatch
import httpmessage.exc as exc
from httpmessage.const import const

def class_lookup(arg, superclass=None):
    cls = None
    if inspect.isclass(arg):
        cls = arg
    else:
        thismodule = sys.modules[__name__]
        classname = str(arg)
        if hasattr(thismodule, classname):
            value = getattr(thismodule, classname)
            if inspect.isclass(value):
                cls = value
        else:
            raise ValueError('could not find class for %r' % arg)
    if superclass is not None:
        if not issubclass(cls, superclass):
            raise TypeError('%r is not a subclass of %r' % (cls, superclass))
    return cls


#======================================================================
# main class
#======================================================================

class HttpMessage(_mapio.MapIOHybrid):

    """An :class:`HttpMessage` is represented as a hybrid of dict(-like) and
    file(-like) objects.

    :class:`HttpMessage` assumes a :class:`multidict` API, adding methods
    beyond those of of :class:`dict`. The mapping API of :class:`HttpMessage`
    has been extended to include multimap methods: :meth:`getall`,
    :meth:`delall`, :meth:`len_at`, :meth:`getitem_at`, :meth:`setitem_at`,
    :meth:`delitem_at`, and :meth:`append_at`.

    All keys are converted to *header-case* (lower case except for the first
    letter and first letter after each hyphen). Thus, the keys are
    case-insensitive; key ``'content-type'`` is the same as ``'cOnTenT-TypE'``
    (but, please don't use the latter, it hurts my eyes).

    This class does not allow itself to be instantiated directly. You can (and
    should) call its constructor however, when reading message data from a
    socket or file-like object. ``HttpMessage`` will self-differentiate into a
    suitable subclass based on the data it receives. If no data is provided,
    it will change its class to that of the default subclass.

    Numerous data descriptors are provided for convenience of getting and
    setting header values.
    """

    MappingClass = _headers.Headers
    mapping_methods = [m for m in itertools.chain(
            _mapio.MapIOHybrid.mapping_methods,
            """getall delall len_at getitem_at setitem_at 
            delitem_at append_at""".split()
        )]
    del m

    subclass_request = "RequestMessage"
    subclass_response = "ResponseMessage"
    subclass_auto = subclass_request

    adjust_entity_headers = True
    _receiver = None
    _raw_fileobj = None

    http_version = 'HTTP/1.1'

    # general header descriptors
    cache_control = field.CacheControl()           # LIST
    connection = field.Connection()                # LIST
    date = field.Date()
    pragma = field.Pragma()                        # LIST
    trailer = field.Trailer()                      # LIST
    transfer_encoding = field.TransferEncoding()   # LIST
    upgrade = field.Upgrade()                      # LIST
    via = field.Via()                              # LIST
    warning = field.Warning()                      # LIST
    
    # entity header descriptors
    allow = field.Allow()
    content_encoding = field.ContentEncoding()     # LIST
    content_language = field.ContentLanguage()     # LIST
    content_length = field.ContentLength()
    content_location = field.ContentLocation()
    content_md5 = field.ContentMD5()
    content_range = field.ContentRange()
    content_type = field.ContentType()
    expires = field.Expires()
    last_modified = field.LastModified()

    #----------------------------------------------------------------------
    #
    #----------------------------------------------------------------------

    #......................................................................
    def __init__(self, socket=None, fileobj=None):
        r"""
        Initialize an :class:`HttpMessage`.

        ``socket`` takes precedence over ``fileobj``. If both are set,
        ``fileobj`` is ignored.
        """
        super(HttpMessage,self).__init__()
        

        if socket is not None:
            fileobj = _socketadaptor.SocketAdaptor(socket)
        
        if fileobj:
            # deal with request or status-line, self differentiate
            firstline = fileobj.readline()
            if firstline[:5].upper() == "HTTP/":
                self.__class__ = class_lookup(
                        self.subclass_response, superclass=HttpMessage
                    )
            else:
                self.__class__ = class_lookup(
                        self.subclass_request, superclass=HttpMessage
                    )
            self.process_firstline(firstline)
            
            # read in lines until we find a blank line, or the iterator stops
            headersbuf = []
            for line in fileobj:
                headersbuf.append(line)
                if not line.strip():
                    break
            # and use that to set the headers
            self.set_headers_from(''.join(headersbuf))
            self.set_fileobj(fileobj)

        # fallback; differentiate as necessary
        if type(self) is HttpMessage:
            self.__class__ = class_lookup(
                    self.subclass_auto,
                    superclass=HttpMessage
                )

    #......................................................................
    def set_fileobj(self, fileobj):
        # not entirely sure if this should be a "public" method or not.
        # it was added to facilitate :meth`_refresh_entity_size` (previously,
        # this setting happened only in the constructor), but it *seems* 
        # like it should be safe...

        if self._receiver:
            # if we're replacing a previously set fileobj...
            dispatch.disconnect(self._receiver)

        self._fileobj = _entityio.EntityIO(fileobj, self.entity_size())

        # save the fileobj, in case we need to re-build the :class:`EntityIO`.
        self._raw_fileobj = fileobj

        # create a bound method, save it, and connect it to dispatch
        self._receiver = self._receive_entityio_dispatch
        dispatch.connect(self._receiver, sender=self._fileobj)

    #......................................................................
    def _refresh_entity_size(self):
        try:
            if (not self._fileobj.buffering_started and
                self._raw_fileobj):
                self.set_fileobj(self._raw_fileobj)
        except AttributeError:
            pass

    #......................................................................
    def __dir__(self):
        keys = set()
        keys.update(dir(type(self)))
        keys.update(self.__dict__.keys())
        keys.update(self.mapping_methods)
        keys.update(self.filelike_methods)
        return sorted(keys)

    #......................................................................
    def _receive_entityio_dispatch(self, signal, sender, info):
        # this method is just a relay, to hide the fact that RAW_DATA
        # signals are dispatched from a hidden implementation detail (an
        # EntityIO instance), instead of from us directly
        if sender == self._fileobj:
            # re-emit signals that come from my fileobj
            responses = dispatch.send(signal, self, info)

        if signal == dispatch.signal.END_DATA:
            dispatch.disconnect(self._receiver)
            del self._receiver
            if self._raw_fileobj:
                del self._raw_fileobj
            if self.adjust_entity_headers:
                pos = self.tell()
                self.seek(0,os.SEEK_END)
                self.content_length = self.tell()
                self.seek(pos,os.SEEK_SET)
                del self.transfer_encoding
        
        if dispatch.response.ABORT in responses:
            return dispatch.response.ABORT
        return None

    #......................................................................
    def str_head(self):
        headerbuf = [
                "%s: %s" % (k, str(v)) 
                for k,v in sorted(self.items())
            ]
        return "%s\r\n%s\r\n\r\n" % (self.firstline, "\r\n".join(headerbuf))

    #......................................................................
    def __str__(self):
        try:
            self.seek(0, os.SEEK_SET)
            data = self.read()
        except exc.ReentrantDispatch:
            data = ''

        return '%s%s' % (
                self.str_head(), data
            )

    #......................................................................
    def set_headers_from(self, headertext):
        """
        Replace the current header mapping with the headers defined in the
        ``headertext``. 

        ``headertext`` must be in the standard RFC 822 format.
        """

        raw_headers = []
        lines = headertext.split("\n")
        expect_done = False

        for line in lines:
            line = line.rstrip()
            if not line: break
            elif line[0] != " " and line[0] != '\t':
                raw_headers.append(line)
            else:
                # replace all LWS with a single SP
                raw_headers[-1] += " " + line.lstrip()

        self.clear()
        for raw_header in raw_headers:
            colonpos = raw_header.find(':')
            if colonpos == -1:
                msg = "no colon found in header: %r" % raw_header
                raise exc.MalformedHeaders(msg)
            elif colonpos == 0:
                msg = "no header key in header: %r" % raw_header
                raise exc.MalformedHeaders(msg)

            k,v = raw_header[:colonpos], raw_header[colonpos+1:].strip()
            self.append_at(k,v)

    #......................................................................
    def entity_size(self):
        """Determine the size of the entity we expect, by examining
        various headers and properties.

        :rtype: an :class:`int` or a constant, one of:

            * :data:`httpmessage.const.ZERO_BYTE_CHUNK`
            * :data:`httpmessage.const.MULTIPART_BYTERANGE`
            * :data:`httpmessage.const.CONNECTION_CLOSE`
        """
        if self.transfer_encoding and self.transfer_encoding != 'identity':
            return const.ZERO_BYTE_CHUNK
        elif self.content_length is not None:
            return self.content_length
        elif self.content_type and \
                self.content_type.lower() == 'multipart/byteranges':
            return const.MULTIPART_BYTERANGE
        else:
            return const.CONNECTION_CLOSE

    #......................................................................
    def buffer_all(self):
        """
        Fully read any entity data that has not yet been buffered into memory.

        Entity data is lazily read from the object's data source
        (:attr:`socket` or :attr:`fileobj`), when possible.
        """
        if hasattr(self._fileobj, 'buffer_all'):
            self._fileobj.buffer_all()

    #......................................................................
    def __getattr__(self, attrname):
        #print 'HttpMessage getattr', attrname
        # fallback for attr lookups starting with 'x_', get the 'X-' extension
        # header from the headers
        if attrname[:2] == 'x_':
            key = attrname.replace('_', '-')
            if key in self:
                return self[key]
            return None
        return super(HttpMessage,self).__getattr__(attrname)

    #......................................................................
    def __setattr__(self, attrname, value):
        # intercept attr sets starting with 'x_', set the 'X-' extension
        # header in the headers
        if attrname[:2] == 'x_':
            key = attrname.replace('_', '-')
            if value is None:
                if key in self:
                    del self[key]
            else:
                self[key] = value

        elif hasattr(self, attrname):
            super(HttpMessage,self).__setattr__(attrname, value)
        else:
            # if we have lots of data-descriptors, typos are our enemy. we 
            # don't want to create new attributes by accident; we refuse.
            # if we want an attribute to be 'settable', give it some default
            # value (None) in a class/superclass.
            raise AttributeError('cannot set new attr %r' % attrname)

    #......................................................................
    def filename_extension(self):
        """ Generate the best filename extension for the type of entity data
        used in this message. Will default to ``.data`` if no better extension
        is found. """
        ext = _contenttype.guess_extension(self.content_type)
        encoding = self.get('Content-Encoding', '')
        if 'gzip' in encoding:
            ext += '.gz'
        elif 'compress' in encoding:
            ext += '.zip'
        return ext

#######################################################################
class _RequestFirstline(object):
    """Descriptor; generates an http request-line from an instance."""
    pullattrs = operator.attrgetter('method', 'request_uri', 'http_version')
    def __get__(self, instance, instance_type):
        if instance is None: return self
        return ' '.join([str(a) for a in self.pullattrs(instance)])
    def __set__(self, instance, value):
        raise AttributeError(self, value)
#======================================================================
class _ParsedURI(object):
    """Descriptor; gets and sets a parsed version of the request URI. If
    setting a value, that value must be compatible with
    :func:`urlparse.urlunparse`."""
    def __init__(self, attrname):
        self.attrname = attrname
    def __get__(self, instance, instance_type):
        if instance is None: return self
        return urlparse.urlparse(getattr(instance, self.attrname))
    def __set__(self, instance, value):
        setattr(instance, self.attrname, urlparse.urlunparse(value))

#======================================================================
class RequestMessage(HttpMessage):
    """A :class:`HttpMessage` subclass representing HTTP requests."""

    method = 'GET'
    request_uri = '/'

    # data descriptors
    firstline = _RequestFirstline()
    parsed_request_uri = _ParsedURI('request_uri')
    
    # request header descriptors
    accept = field.Accept()                        # LIST
    accept_charset = field.AcceptCharset()         # LIST
    accept_encoding = field.AcceptEncoding()       # LIST
    accept_language = field.AcceptLanguage()       # LIST
    authorization = field.Authorization()
    expect = field.Expect()                        # LIST
    from_ = field.From()
    host = field.Host()
    if_match = field.IfMatch()                     # LIST
    if_modified_since = field.IfModifiedSince()
    if_none_match = field.IfNoneMatch()            # LIST
    if_range = field.IfRange()
    if_unmodified_since = field.IfUnmodifiedSince()
    max_forwards = field.MaxForwards()
    proxy_authorization = field.ProxyAuthorization()
    range = field.Range()
    referer = field.Referer()
    te = field.TE()                                # LIST
    user_agent = field.UserAgent()                 # LIST
    
    # extension request header descriptors
    cookie = field.Cookie()
    cookie2 = field.Cookie2()

    #......................................................................
    def process_firstline(self, line):
        self.http_version = "HTTP/0.9"
        line_parts = line.strip().split()
        if len(line_parts) == 3:
            (self.method, self.request_uri, self.http_version) = line_parts
        elif len(line_parts) == 2:
            (self.method, self.request_uri) = line_parts
        else:
            raise exc.MalformedFirstline('%r' % line)

    #......................................................................
    def entity_size(self):
        HttpMessage.entity_size.__doc__
        method = self.method
        if method in 'GET HEAD'.split():
            return 0
        return super(RequestMessage,self).entity_size()
    
    #......................................................................
    def fetch_response(self, sock=None):
        r"""
        Send the http request message represented by :attr:`self` to the
        appropriate server, and return the server's response as a
        :class:`ResponseMessage`.

        If ``sock`` is set, that :class:`socket` will be used (and it
        will be assumed that the socket connects to the correct server). If a
        :class:`socket` is not specified, a new one will be created to the
        server referenced by :attr:`host` or :attr:`request_uri`.

        """
        requri = urlparse.urlparse(self.request_uri)
        if requri.hostname and not self.host:
            self.host = requri.hostname

        if not self.host:
            raise ValueError('Host header field not set; cannot fetch.')
            
        if not sock:
            port = requri.port if requri.port else 80 
            sock = socket.socket()
            sock.connect((self.host, port))
        
        sock.send(str(self))
        resp = ResponseMessage(socket=sock)
        resp.request_method = self.method
        return resp



#######################################################################
class _ResponseFirstline(object):
    """Descriptor; generates an http status-line from an instance.
    """
    pullattrs = operator.attrgetter(
            'http_version', 'status_code', 'reason_phrase')
    def __get__(self, instance, instance_type):
        if instance is None: return self
        return ' '.join([str(a) for a in self.pullattrs(instance)])
    def __set__(self, instance, value):
        raise AttributeError(self, value)

#======================================================================
class _RequestMethod(object):
    # The existance of this descriptor is to fix the problem of setting
    # :attr:`request_method` after instance's fileobj (of :class:`EntityIO`)
    # has already heard about the results of :meth:`entity_size`. Setting
    # :attr:`request_method` (to 'HEAD') can *change* the results of
    # :meth:`entity_size`. So, we might need to blow up the old
    # :class:`EntityIO` and make a new one, considering the new info.
    #
    # That's what :meth:`_refresh_entity_size` does, under some circumstances.
    def __init__(self, attrname):
        self.attrname = attrname
    def __get__(self, instance, instance_type):
        if instance is None: return self
        return instance.__dict__.get(self.attrname)
    def __set__(self, instance, value):
        instance.__dict__[self.attrname] = value
        instance._refresh_entity_size()

#======================================================================
class ResponseMessage(HttpMessage):
    """A :class:`HttpMessage` subclass representing HTTP responses."""

    request_method =  _RequestMethod('request_method')
    status_code = 200
    reason_phrase = ''

    # data descriptors
    firstline = _ResponseFirstline()
    
    # response header descriptors
    accept_ranges = field.AcceptRanges()           # LIST
    age = field.Age()
    etag = field.ETag()
    location = field.Location()
    proxy_authenticate = field.ProxyAuthenticate() # LIST
    retry_after = field.RetryAfter()
    server = field.Server()
    vary = field.Vary()                            # LIST
    www_authenticate = field.WWWAuthenticate()     # LIST
    
    # extension response header descriptors
    set_cookie = field.SetCookie()
    set_cookie2 = field.SetCookie2()

    #......................................................................
    def process_firstline(self, line):
        line_parts = line.strip().split()
        if len(line_parts) < 2:
            raise exc.MalformedFirstline('%r' % line)

        self.http_version = line_parts[0]
        self.status_code = int(line_parts[1])
        self.reason_phrase = " ".join(line_parts[2:])

    #......................................................................
    def entity_size(self):
        HttpMessage.entity_size.__doc__
        method = self.request_method
        code = self.status_code
        if code is None:
            code = -1
        
        if (code >= 100 and code < 200) or code == 204 or code == 304:
            return 0
        elif method in 'HEAD'.split():
            return 0
        return super(ResponseMessage,self).entity_size()
        






