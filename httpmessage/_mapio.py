import cStringIO
import itertools

def getattribute(obj, attrname):
    return object.__getattribute__(obj, attrname)

class MapIOHybrid(object):

    """A hybrid of a dict-like type and a file-like type; whose APIs are
    (fortunately) almost entirely disjoint.

    This class has and proxies for two data objects; an object that conforms
    to the mapping API, and an object that conforms to the file-like API. The
    only API missing is iteration -- we do not define an :meth:`__iter__`
    method (okay, we do, but it raises :exc:`AttributeError`). We omit this
    because both of our underlying objects support iteration, so it isn't
    clear which of the two we *should* iterate over.

    Use :meth:`iterkeys` for equivalent iteration over the mapping data, and
    :meth:`iterlines` for equivalent iteration over the file-like object's
    data.
    """

    _mapobj = None
    _fileobj = None

    MappingClass = dict
    FilelikeClass = cStringIO.StringIO

    mapping_methods = """clear fromkeys get has_key items iteritems 
    iterkeys itervalues keys pop popitem setdefault update values
    """.split()

    filelike_methods = """close flush fileno isatty read readline
    readlines seek tell truncate write writelines
    """.split()

    
    # Annoying; special method lookup doesn't go through normal method
    # lookup procedure; can't wrap these in __getattr__ or __getattribute__;
    # see: http://bugs.python.org/issue643841
    def __len__(self):                  return len(self._mapobj)
    def __getitem__(self, key):         return self._mapobj[key]
    def __setitem__(self, key, value):  self._mapobj[key] = value
    def __delitem__(self, key):         del self._mapobj[key]
    def __contains__(self, key):        return key in self._mapobj

    def __iter__(self):
        # both mapping types and file-like types have iter defined; 
        # we don't know which to do here. so, we do neither.
        raise AttributeError

    def iterlines(self):
        """
        Return an iterator for traversing the underlying File-like object.
        """
        return iter(self._fileobj)

    def __init__(self, mapobj=None, fileobj=None):
        self._mapobj = mapobj if mapobj is not None \
                else self.MappingClass()
        self._fileobj = fileobj if fileobj is not None \
                else self.FilelikeClass()

    def __getattr__(self, attrname):
        #print 'MapIOHybrid getattr', attrname
        if attrname in self.mapping_methods:
            return getattr(self._mapobj, attrname)
        elif attrname in self.filelike_methods:
            return getattr(self._fileobj, attrname)
        else:
            raise AttributeError(attrname)
    
    def __repr__(self):
        return '<%s filepos=%i mapping=(%r)>' % (
                type(self).__name__, self.tell(), self._mapobj 
            )

if __name__ == '__main__':
    
    from IPython.Shell import IPShellEmbed
    ipshell = IPShellEmbed()
    ipshell()
