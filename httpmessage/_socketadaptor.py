if __name__ == "__main__":
    import sys 
    from os.path import split, dirname, abspath
    parent_dir = split(dirname(abspath(__file__)))[0]
    sys.path.append(parent_dir)

import socket

class SocketAdaptor(object):
    recv_size = 1024

    def __init__(self, sock):
        self._sock = sock
    
    def readline(self):
        peekbuf = ''
        buffers = []

        while True:
            peekbuf = self._sock.recv(self.recv_size, socket.MSG_PEEK)
            if not peekbuf:
                # socket closed
                break

            nlpos = peekbuf.find('\n')
            if nlpos == -1:
                buffers.append(peekbuf)
                self._sock.recv(len(peekbuf))
            else:
                buffers.append(self._sock.recv(nlpos+1))
                break
        return "".join(buffers)


    def read(self, count=None):
        buffers = []

        if count < 0: 
            count = None

        if count is None:
            while True:
                data = self._sock.recv(self.recv_size)
                if not data:
                    break
                buffers.append(data)
        else:
            buffered_length = 0
            while True:
                left = count - buffered_length
                if left == 0:
                    break
                elif left < 0:
                    # this will only happen if _sock.recv returns more data
                    # than I ask it for, which it should never do...
                    raise Exception('overran socket; should never happen')

                this_recv_size = min(left, self.recv_size)
                data = self._sock.recv(this_recv_size)
                if not data:
                    break
                data_length = len(data)
                buffers.append(data)
                buffered_length += data_length

        return "".join(buffers)

    def __iter__(self):
        while True:
            line = self.readline()
            if not line:
                break
            yield line

if __name__ == '__main__':
    import threading
    def serve():
        servsock = socket.socket()
        servsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        servsock.bind(('', 9111))
        servsock.listen(5)
        for i in range(3):
            print 'server waiting for connect'
            consock, addr = servsock.accept()
            print 'server got connect'
            consock.send('yippidy do!\nand tiger too!\nfloobings\nbabbings\n')
            print 'server sent message'
            consock.close()
    t = threading.Thread(target=serve)

    # daemon doesn't seem to do what I think it should; the serve thread
    # doesn't terminate when we fall of the end (if the loop is while True, 
    # for example)
    # aha!  the property interface doesn't exist in 2.5.  
    #t.daemon = True
    t.setDaemon(True)

    t.start()
    import time
    time.sleep(1)
    consock = socket.socket()
    consock.connect(('', 9111))
    adaptor = SocketAdaptor(consock)
    print 'readline %r' % adaptor.readline()
    print 'read(3) %r' % adaptor.read(3)
    print 'readline %r' % adaptor.readline()
    print 'read(500) %r' % adaptor.read(500)
    
    consock = socket.socket()
    consock.connect(('', 9111))
    adaptor = SocketAdaptor(consock)
    for line in adaptor:
        print 'line %r' % line
    print 'should exit'
