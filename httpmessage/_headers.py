import _setup
import inspect
import pprint

from httpmessage._multidict import MultiDict

def header_case(header_key):
    return "-".join([part.capitalize() for part in header_key.split("-")])

def _key_wrap(func):
    """creates a function where the value of the 'key' argument, if there 
    is one, has the function 'header_case' run on it.
    """
    varnames = func.func_code.co_varnames
    def key_filter(kv):
        name, value = kv
        if name == 'key':
            return header_case(value)
        else:
            return value

    def wrapped(*args):
        if len(args) == len(varnames):
            args = [key_filter(kv) for kv in zip(varnames, args)]
        return func(*args)

    wrapped.func_name = func.func_name
    wrapped.func_doc = func.func_doc
    return wrapped
        

class Headers(MultiDict):
    for attrname in dir(MultiDict):
        attrvalue = getattr(MultiDict, attrname)
        if inspect.ismethod(attrvalue):
            attrvalue = attrvalue.im_func

        if inspect.isfunction(attrvalue) and \
            'key' in attrvalue.func_code.co_varnames:
            locals()[attrname] = _key_wrap(attrvalue)

    #---------------------------------------------------------------
    def iteritems(self):
        return iter(sorted(super(Headers,self).iteritems()))


    #---------------------------------------------------------------
    def __repr__(self):
        data = pprint.pformat(list(self.iteritems()))
        if '\n' in data:
            data = ''.join([data[0], '\n ', data[1:-1], '\n', data[-1]])
        return '<%s(%s)>' % (
                type(self).__name__, data
            )

    #---------------------------------------------------------------
    def __copy__(self):
        dup = Headers()
        for k,v in self.iteritems():
            dup.append_at(k,v)
        return dup
        



if __name__ == "__main__":
    h = Headers()
    h['foo'] = 'bar'
    h['content-lenGth'] = 5
    print h
    h['CONTENT-length'] = 10
    print h
    del h['foO']
    print h
    h['content-type'] = 'wack wack wackiness'
    h['rover-dookie'] = 'oh yah, lots'
    print h