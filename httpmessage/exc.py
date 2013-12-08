
class HttpMessageException(Exception): pass

class MalformedFirstline(HttpMessageException): pass
class MalformedHeaders(HttpMessageException): pass

class BufferingAbort(HttpMessageException): pass
class EntityReadError(HttpMessageException): pass

class ReentrantDispatch(HttpMessageException): pass
