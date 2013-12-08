from UserDict import DictMixin

class MultiDict(object,DictMixin):
    
    def __init__(self):
        self._data = {}

    def __getitem__(self, key):
        return self._data[key][-1]

    def __setitem__(self, key, value):
        if not self._data.has_key(key):
            self._data[key] = [None]
        self._data[key][-1] = value

    def __delitem__(self, key):
        del self._data[key][-1]
        if not self._data[key]:
            del self._data[key]

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data)

    def __contains__(self, key):
        return self._data.has_key(key)

    def itervalues(self):
        for k in self._data:
            for v in self._data[k]:
                yield v

    def iteritems(self):
        for k in self._data:
            for v in self._data[k]:
                yield k,v

    def clear(self):
        self._data = {}

    def getall(self, key):
        return tuple(self._data[key])
    
    def delall(self, key):
        del self._data[key]

    def len_at(self, key):
        return len(self._data[key])
    
    def getitem_at(self, key, index):
        return self._data[key][index]
    
    def setitem_at(self, key, index, value):
        self._data[key][index] = value
    
    def delitem_at(self, key, index):
        del self._data[key][index]

    def append_at(self, key, value):
        if not self._data.has_key(key):
            self._data[key] = []
        self._data[key].append(value)
