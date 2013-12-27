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
import httpmessage.exc as exc

from multiprocessing import Lock
import commands, os, hashlib, threading, traceback

read_from_cache = True
save_to_cache = True
lock = Lock()
redirect_map = {}
cache_set = set()

working = []
working_lock = Lock()

cache_dir = "../.cache"

class ThreadingProxyServer(ThreadingMixIn, TCPServer):
  allow_reuse_address = True
  daemon_threads = True
  
class ProxyHandler(StreamRequestHandler):
  
  """Buffers the entire request before sending it to server. Buffers entire
  response before sending it to client. Doesn't work at all well for large
  resources (like Youtube videos)."""

  def request_to_server(self):
    request = self.request
    filepath = self.filepath
    key = self.key

    print "SEND REQUEST"
    response = request.fetch_response()
    response.connection = 'close'
    print "RESP", response.firstline, response.status_code, response.server, response.location
    
    # Remove redirect cycle of size two.
    if response.location:
      print "REDIRECT"
      redirect_url = response.location
      for part in response.location.split("&"):
        if part[0:9] == "continue=":
          redirect_url = part[9:]
          break
          
      if redirect_url[0:7] == "http://":
        redirect_url = redirect_url[7:]
        
      redirect_url = redirect_url.replace("%3D","=")
      redirect_map[key] = redirect_url
      print "MAP", key, redirect_url
        
      # Detect cycle.
      if redirect_url in redirect_map and redirect_map[redirect_url] == key:
        print "DEL", redirect_url
        lock.acquire()
        del redirect_map[redirect_url]
        cache_set.remove(redirect_url)
        os.system("rm " + self.key_to_filepath(redirect_url))
        lock.release()
    # END: Remove redirect cycle of size two.

    response = str(response)
    if save_to_cache:
      f = open(filepath, 'w')
      f.write(response)
      f.close()
      
    working_lock.acquire()
    working.remove(filepath)
    working_lock.release()

    self.connection.send(response)
    
  def cache_or_request(self):
    filepath = self.filepath
    key = self.key
    print "LOCK"
    lock.acquire()
    #status, output = commands.getstatusoutput("ls " + filepath)
    #if read_from_cache and status == 0 and output.find("cannot access") == -1:
    if read_from_cache and key in cache_set:
      lock.release()
      print "UNLOCK"
      try:
        f = open(filepath, 'r')
        firstline = f.readline()
        create_date = f.readline().split(" ")
        f.close()
      except IOError:
        print "CALL CACHE_OR_REQUEST", filepath
        self.cache_or_request()
        return
      print "IN-CACHE", firstline
      while firstline == "~empty~\n":
        print "loop on ~empty~"
        print filepath

        # print create_date
        create_day = int(create_date[2])
        create_time = [int(x) for x in create_date[3].split(":")]
        
        status, current_date = commands.getstatusoutput("date")
        current_date = current_date.split(" ")
        current_day = int(current_date[2])
        current_time = [int(x) for x in current_date[3].split(":")]

        if current_day != create_day or \
              current_time[0]*60 + current_time[1] > create_time[0]*60 + create_time[1] + 1:
          lock.acquire()
          cache_set.remove(key)
          os.system("rm " + filepath)
          lock.release()
          print "BREAKING THE LOOP!!!!!!!!!!!!!!!!!!!!!!!!!"
        
        try:
          f = open(filepath, 'r')
          firstline = f.readline()
          create_date = f.readline().split(" ")
          f.close()
        except IOError:
          print "CALL CACHE_OR_REQUEST"
          self.cache_or_request()
          return

      print "CACHE-HIT", filepath
      try:
        f = open(filepath, 'r')
        response = f.read()
        f.close()
      except IOError:
        print "CALL CACHE_OR_REQUEST"
        self.cache_or_request()
        return
      self.connection.send(response)
    else:
      print "CACHE-MISS"
      # print request.host, request.connection
      # print request.cache_control, request.accept
      # print request.user_agent, request.accept_encoding, request.accept_language
      # print request.cookie

      try:
        # Placeholder for locking.
        working_lock.acquire()
        working.append(filepath)
        working_lock.release()

        os.system("echo ~empty~ > " + filepath + " & date >> " + filepath)
        cache_set.add(key)
        lock.release()
        print "UNLOCK"
        self.request_to_server()
      except Exception as e:
        f = open('error.log', 'a')
        f.write(str(type(e)) + ', ' + str(e) + '\n')
        f.write(traceback.format_exc())
        f.close()

        lock.acquire()
        cache_set.remove(key)
        os.system("rm " + filepath)
        lock.release()
        print "CLEAN-UP: rm", filepath
        print traceback.format_exc()
        raise e

  def key_to_filepath(self, key):
    if len(key) > 255:
      filename = hashlib.sha512(key).hexdigest()
    else:
      filename = key

    return cache_dir + "/" + filename.replace("/","#").replace("&","~").replace(";",":").replace("|","-").replace("<","[").replace(">","]").replace("?",",").replace("(","{").replace(")","}").replace("$","%")
  
  def handle(self):
    try:
      request = HttpMessage(socket=self.connection)
      self.request = request
      print "BEFORE", request.method, request.host, request.request_uri
      
      # Need to modify uri because some websites, such as thefreedictionry.com,
      # handle uri that has host as substring incorrectly.
      pos = request.request_uri.find(request.host)
      if pos >= 0:
        request.request_uri = request.request_uri[pos+len(request.host):]
        
      key = request.host + request.request_uri
      self.key = key
      filepath = self.key_to_filepath(key)
      self.filepath = filepath
      print "AFTER", request.method, key #, filepath
    
      self.cache_or_request()

    except exc.MalformedFirstline:
      # self.connection.send("")
      pass
    except Exception as e:
      f = open('error.log', 'a')
      f.write(str(type(e)) + ', ' + str(e) + '\n')
      f.write(traceback.format_exc())
      f.close()

      raise e

      # print "---------------------------------------------------------------"
      # print type(e), e
      # print "---------------------------------------------------------------"

    #   self.connection.send("")
    
if __name__ == "__main__":
  server_address = ('127.0.0.1', 1234)
  f = open('error.log', 'w')
  f.close()
  proxyserver = ThreadingProxyServer(server_address, ProxyHandler)
  print 'proxy serving on %r' % (server_address,)
  print 'sys.args', len(sys.argv)
  os.system("pwd")

  if len(sys.argv) > 1:
    cache_dir = sys.argv[1]

  os.system("mkdir " + cache_dir)
  print cache_dir

  try:
    proxyserver.serve_forever()
  except KeyboardInterrupt:
    for f in working:
      print "CLEAN-UP: rm", f
      os.system("rm " + f)
    print '\nexiting...'
