import functools
import weakref
import inspect
import operator
import itertools
from collections import defaultdict


#======================================================================
class base(object):
    def __init__(self, ident):
        self.ident = ident
    def __repr__(self):         # pragma: no cover
        return '<%s %s id=%i>' % (type(self).__name__, self.ident, id(self))

#======================================================================
class signal(base): pass
_signal = signal
signal.RAW_DATA = signal('RAW_DATA')
signal.END_DATA = signal('END_DATA')
signal.ANY = signal('ANY')
signal.ALL = signal('ALL')

#======================================================================
class response(base): pass
_response = response
response.ABORT = response('ABORT')

#======================================================================
class sender(base): pass
_sender = sender
sender.ANY = sender('ANY')
sender.ALL = sender('ALL')

#======================================================================
class receiver(base): pass
_receiver = receiver
receiver.ALL = receiver('ALL')


#======================================================================
# okay -- what is this?  it's a dict of dicts of sets.  more accurately, a
# defaultdict of defaultdicts of sets.  that way, we can say:
#   _connections[key1][key2] 
# and get a set without having to initialize things first.
_connections = defaultdict(functools.partial(defaultdict, set))

#======================================================================


class WeakMethodRef(object):

    """Expects a method. If :func:`inspect.ismethod` isn't true for
    ``method``, it will probably blow up.

    Saves weak references to the method's :attr:`im_self` and :attr:`im_func`
    so that the method can be reconstructed as needed."""

    meth_attrs = operator.attrgetter('im_self', 'im_func')    
    def __init__(self, method):
        self._wref = [weakref.ref(a) for a in self.meth_attrs(method)]

    def __call__(self):
        im_self, im_func = [wr() for wr in self._wref]
        if im_self is None or im_func is None:
            return None
        return im_func.__get__(im_self, type(im_self))
    
    def __eq__(self, other):
        if not isinstance(other, WeakMethodRef):
            return False
        return self._wref == other._wref
    
    def __hash__(self):
        return hash(tuple(self._wref))

    def __repr__(self):
        return "<%s id=%i wref=%r>" % (
            type(self).__name__, id(self), self._wref)

#======================================================================
def send(signal, sender=None, info=None):
    """Calls-back all callables which have been previously :func:`connect`-ed
    to a dispatch path matching this ``signal`` / ``sender`` pair. Each
    callable will get three arguments; the same three arguments :func:`send`
    was called with.

    The return values of those callbacks will be returned as a :class:`tuple`
    of values to the caller of :func:`send`. If any of those callbacks raises
    an exception, the exception will be trapped and placed in the
    response-:class:`tuple` instead of the receiver's return value. """
    receivers = set()
    for sigkey in set([id(k) for k in (signal, _signal.ANY)]):
        for sendkey in set([id(k) for k in (sender, _sender.ANY)]):
            if sigkey in _connections and sendkey in _connections[sigkey]:
                receivers |= _connections[sigkey][sendkey]
    
    responses = []
    for weakobj in receivers:
        try:
            obj = weakobj()
            if obj:
                responses.append(obj(signal, sender, info))
            else:
                disconnect(weakobj)
        except Exception, e:
            responses.append(e)
    return tuple(responses)

#======================================================================
def connect(receiver, signal=_signal.ANY, sender=_sender.ANY):

    """Register a callable to receive dispatches matching a ``signal`` /
    ``sender`` pair. 

    One can express interest in a specific :data:`signal`, or one can express
    interest in every signal by using the wildcard :data:`signal.ANY`.
    Similarly, one can express interest in specific senders (potentially any
    python object), or all senders, using the wildcard :data:`sender.ANY`. 

    A record to ``receiver`` is kept as a weak reference. Receivers who are
    garbage collected elsewhere are automatically disconnected. A special case
    is made for bound methods (which don't always play nice when kept as weak
    references), so it is safe to pass a bound method as receiver and not keep
    another reference to it yourself."""

    if signal is _signal.ALL:
        raise ValueError('cannot connect to signal ALL; use ANY instead')
    if sender is _sender.ALL:
        raise ValueError('cannot connect to sender ALL; use ANY instead')
    if inspect.ismethod(receiver):
        wrecv = WeakMethodRef(receiver)
    else:
        wrecv = weakref.ref(receiver)

    _connections[id(signal)][id(sender)].add(wrecv)

#======================================================================
def disconnect(receiver, signal=_signal.ALL, sender=_sender.ALL):

    """Unregisters callables matching the arguments so that they will no
    longer receive dispatches. The arguments are the same as :func:`connect`,
    with the addition of three possible constant values:

    * :data:`receiver.ALL` 
    * :data:`signal.ALL`
    * :data:`sender.ALL`
    """

    if signal is _signal.ALL:
        signals = _connections.keys()
    else:
        signals = [id(signal)]

    for sigkey in signals:
        if sender is _sender.ALL:
            senders = _connections[sigkey].keys()
        else:
            senders = [id(sender)]
        
        for sendkey in senders:
            rset = _connections[sigkey][sendkey]
            if receiver is _receiver.ALL:
                rset.clear()
            else:
                for wref in list(rset):
                    obj = wref()
                    if obj is None or obj == receiver:
                        rset.remove(wref)

            if not rset:
                del _connections[sigkey][sendkey]
            if not _connections[sigkey]:
                del _connections[sigkey]



#======================================================================
def _num_connections():
    # hook for testing
    return sum([len(rset) 
                for senddict in _connections.values() 
                    for rset in senddict.values()])


def _sender_isconnected(sender):
    # hook for testing
    sendkey = id(sender)
    return any([sendkey in senddict.keys() 
                for senddict in _connections.values()])

def _signal_isconnected(signal):
    # hook for testing
    sigkey = id(signal)
    return sigkey in _connections.keys()

def _all_receivers(): 
    # hook for testing
    rsets = [rset 
            for senddict in _connections.values() 
                for rset in senddict.values()]
    return set().union(*rsets)

def _receiver_isconnected(receiver):
    # hook for testing
    allrecv = _all_receivers()
    if inspect.ismethod(receiver):
        wrecv = WeakMethodRef(receiver)
    else:
        wrecv = weakref.ref(receiver)
    return wrecv in allrecv



#======================================================================


if __name__ == '__main__':  # pragma: no cover
    import sys, os
    sys.path.append(os.path.join(os.environ['HOME'], 'hg/projects/misclib'))

    def info(signal, sender, info):
        print 'signal: %r\nsender: %r\ninfo: %r' % (signal, sender, info)

    class Listener(object):
        def listen(self, signal, sender, info):
            print 'watcher %i saw %r from %r' % (id(self), signal, sender)
            return response.ABORT

    obj = object()

    dude = Listener()
    connect(dude.listen, signal.RAW_DATA)
    
    dudette = Listener()
    connect(dudette.listen, signal.RAW_DATA, obj)
    
    connect(info)
    print send('foo', object(), {'fruit' : 'tree'})
    # try:
    #     import misclib.code
    #     misclib.code.best_interact()
    # except:
    #     pass
