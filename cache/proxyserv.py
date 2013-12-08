#!/usr/bin/evn python
# examples/proxyserv_v1.py

try:
  import httpmessage
except ImportError:
  import sys
  from os.path import dirname, abspath, join
  sys.path.append(abspath(join(dirname(__file__), '..')))
  
from SocketServer import TCPServer, StreamRequestHandler, ThreadingMixIn
from httpmessage import HttpMessage
import commands

read_from_cache = True
save_to_cache = True

class ThreadingProxyServer(ThreadingMixIn, TCPServer):
  allow_reuse_address = True
  daemon_threads = True
  
class ProxyHandler(StreamRequestHandler):
  
  """Buffers the entire request before sending it to server. Buffers entire
  response before sending it to client. Doesn't work at all well for large
  resources (like Youtube videos)."""
  
  def handle(self):
    request = HttpMessage(socket=self.connection)
    print "BEFORE", request.method, request.host, request.request_uri

    # Need to modify uri because some websites, such as thefreedictionry.com,
    # handle uri that has host as substring incorrectly.
    pos = request.request_uri.find(request.host)
    if pos >= 0:
      request.request_uri = request.request_uri[pos+len(request.host):]

    key = request.host + request.request_uri
    filepath = "../.cache/" + key.replace("/","#")
    print "AFTER", request.method, key #, filepath
    
    status, output = commands.getstatusoutput("ls " + filepath)
    if read_from_cache and status == 0 and not (output[:17] == "ls: cannot access"):
      print "CACHE-HIT", filepath
      f = open(filepath, 'r')
      response = f.read()
      f.close()
      self.connection.send(response)
    else:
      print "CACHE-MISS"
      # print request.host, request.connection
      # print request.cache_control, request.accept
      # print request.user_agent, request.accept_encoding, request.accept_language
      # print request.cookie
      response = request.fetch_response()
      response.connection = 'close'
      print "RESP", response.firstline, response.status_code, response.server, response.location
      response = str(response)
      if save_to_cache:
        f = open(filepath, 'w')
        f.write(response)
        f.close()
      self.connection.send(response)
    
if __name__ == "__main__":
  server_address = ('127.0.0.1', 8000)
  proxyserver = ThreadingProxyServer(server_address, ProxyHandler)
  print 'proxy serving on %r' % (server_address,)
  try:
    proxyserver.serve_forever()
  except KeyboardInterrupt:
    print '\nexiting...'

