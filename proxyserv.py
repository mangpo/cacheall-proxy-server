#!/usr/bin/evn python

import sys, re
from optparse import OptionParser

try:
  import httpmessage
except ImportError:
  from os.path import dirname, abspath, join
  sys.path.append(abspath(join(dirname(__file__), '..')))

from SocketServer import TCPServer, StreamRequestHandler, ThreadingMixIn
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from httpmessage import HttpMessage
from PooledProcessMixIn import PooledProcessMixIn
import httpmessage.exc as exc
import socket

from multiprocessing import Lock, Process
import commands, os, hashlib, threading, traceback

n_process = 8
n_thread = 16

read_from_cache = True
save_to_cache = True
lock = Lock()
redirect_map = {}

working = []
working_lock = Lock()

cache_dir = None
determinize = None

# Set type_on = False if do not want to dump content-type counts
type_on = None
type_file = "content-type.csv"
type_map = {}
type_lock = Lock()
count = 0

class ThreadingProxyServer(ThreadingMixIn, TCPServer):
  allow_reuse_address = True
  daemon_threads = True

class PooledProxyServer(PooledProcessMixIn, HTTPServer):
  def __init__(self,address,handler):
    self._process_n=n_process  # if not set will default to number of CPU cores
    self._thread_n=n_thread  # if not set will default to number of threads
    HTTPServer.__init__(self, address, handler)
  
class ProxyHandler(StreamRequestHandler):
  
  """Buffers the entire request before sending it to server. Buffers entire
  response before sending it to client. Doesn't work at all well for large
  resources (like Youtube videos)."""

  def request_to_server(self):
    request = self.request
    filepath = self.filepath
    key = self.key
    redirect_url = None

    # print "SEND REQUEST"
    sock = socket.socket()
    sock.connect(('127.0.0.1',1235))
    response = request.fetch_response(sock=sock)
    response.connection = 'close'
    # print "RESP", response.firstline, response.status_code, response.server, response.location

    # count += 1

    # # Clear redirect map
    # if count > 1000:
    #   count = 0
    #   redirect_url = {}
    
    # Remove redirect cycle of size two.
    if response.location:
      # print "REDIRECT"
      redirect_url = response.location
      for part in response.location.split("&"):
        if part[0:9] == "continue=":
          redirect_url = part[9:]
          break
          
      if redirect_url[0:7] == "http://":
        redirect_url = redirect_url[7:]
        
      redirect_url = redirect_url.replace("%3D","=")
      redirect_map[key] = redirect_url
      # print "MAP", key, redirect_url
        
      # Detect cycle.
      if redirect_url in redirect_map and redirect_map[redirect_url] == key:
        # print "DEL", redirect_url
        del redirect_map[redirect_url]
        st, o = commands.getstatusoutput("rm " + self.key_to_filepath(redirect_url))
        # print "rm", self.key_to_filepath(redirect_url)
        # print st, o
    # END: Remove redirect cycle of size two.

    response = str(response)
    type_match = None

    if type_on:
      type_match = re.search('(Content-Type *: *) *([^;\n]*)',response,re.IGNORECASE)
    
    if determinize:
      insert = re.search('< *head[^>]*>',response,re.IGNORECASE)
      if insert:
        insert = insert.end()
        response = response[:insert] + determinize + response[insert:]
      else:
        insert = re.search('< *html[^>]*>',response,re.IGNORECASE)
        if insert:
          insert = insert.end()
          response = response[:insert] + "<head>" + determinize + "</head>" + response[insert:]

    if save_to_cache and not (key == redirect_url):
      # print "SAVE", key

      f = open(filepath, 'w')
      f.write(response)
      f.close()

      # count content_type
      if type_on:
        #type_lock.acquire()
        if type_match:
          t = type_match.group(2)
          if t in type_map:
            type_map[t] = type_map[t] + 1
          else:
            type_map[t] = 1

        f = open(type_file,'w')
        for key in type_map:
          f.write(key + "," + str(type_map[key]) + "\n")
        f.close()
        #type_lock.release()
      
    #working_lock.acquire()
    while filepath in working:
      working.remove(filepath)
    #working_lock.release()

    self.connection.send(response)
    
  def cache_or_request(self):
    filepath = self.filepath
    # print "LOCK"
    #lock.acquire()
    status, output = commands.getstatusoutput("ls " + filepath)
    if read_from_cache and status == 0 and output.find("cannot access") == -1:
      #lock.release()
      # print "UNLOCK"
      try:
        f = open(filepath, 'r')
        firstline = f.readline()
        create_date = f.readline().split(" ")
        f.close()
      except IOError:
        # print "CALL CACHE_OR_REQUEST", filepath
        self.cache_or_request()
        return
      # print "IN-CACHE", firstline
      while firstline == "~empty~\n":
        # print "loop on ~empty~"
        # print filepath

        # # print create_date
        create_day = int(create_date[2])
        create_time = [int(x) for x in create_date[3].split(":")]
        
        status, current_date = commands.getstatusoutput("date")
        current_date = current_date.split(" ")
        current_day = int(current_date[2])
        current_time = [int(x) for x in current_date[3].split(":")]

        if current_day != create_day or \
              current_time[0]*60 + current_time[1] > create_time[0]*60 + create_time[1] + 1:
          os.system("rm " + filepath)
          # print "BREAKING THE LOOP!!!!!!!!!!!!!!!!!!!!!!!!!"
        
        try:
          f = open(filepath, 'r')
          firstline = f.readline()
          create_date = f.readline().split(" ")
          f.close()
        except IOError:
          # print "CALL CACHE_OR_REQUEST"
          self.cache_or_request()
          return

      # print "CACHE-HIT", filepath
      try:
        f = open(filepath, 'r')
        response = f.read()
        f.close()
      except IOError:
        # print "CALL CACHE_OR_REQUEST"
        self.cache_or_request()
        return
      self.connection.send(response)
    else:
      # print "CACHE-MISS"
      # # print request.host, request.connection
      # # print request.cache_control, request.accept
      # # print request.user_agent, request.accept_encoding, request.accept_language
      # # print request.cookie

      try:
        # Placeholder for locking.
        #working_lock.acquire()
        working.append(filepath)
        #working_lock.release()

        os.system("echo ~empty~ > " + filepath + " & date >> " + filepath)
        #lock.release()
        # print "UNLOCK"
        p = Process(target=(lambda:self.request_to_server()))
        p.start()
        p.join(10)
        if p.is_alive():
          # print "waiting... let's kill it..."
          p.terminate()
          p.join()

          os.system("rm " + filepath)
          #working_lock.acquire()
          working.remove(filepath)
          #working_lock.release()
      except Exception as e:
        f = open('error.log', 'a')
        f.write(str(type(e)) + ', ' + str(e) + '\n')
        f.write(traceback.format_exc())
        f.close()

        os.system("rm " + filepath)
        # print "CLEAN-UP: rm", filepath
        # # print traceback.format_exc()
        raise e

  def key_to_filepath(self, key):

    cleanedfilename = key.replace("/","#").replace("&","~").replace(";",":").replace("|","-").replace("<","[").replace(">","]").replace("?",",").replace("(","{").replace(")","}").replace("$","%")
    direc = cleanedfilename[0:cleanedfilename.find("#")]

    if len(cleanedfilename) > 255:
      cleanedfilename = hashlib.sha512(cleanedfilename).hexdigest()

    path = cache_dir + "/" + direc + "/" + cleanedfilename 
    path = path.encode('ascii', 'ignore')

    #make sure this path can be used
    dirnm = os.path.dirname(path)
    if not os.path.exists(dirnm):
      print "trying to make", dirnm
      os.makedirs(dirnm)

    return path

  def handle(self):
    try:
      request = HttpMessage(socket=self.connection)
      self.request = request
      # print "BEFORE", request.method, request.host, request.request_uri
      
      # Need to modify uri because some websites, such as thefreedictionry.com,
      # handle uri that has host as substring incorrectly.
      pos = request.request_uri.find(request.host)
      if pos >= 0:
        request.request_uri = request.request_uri[pos+len(request.host):]
        
      key = request.host + request.request_uri
      self.key = key
      filepath = self.key_to_filepath(key)
      self.filepath = filepath
      # print "AFTER", request.method, key #, filepath
    
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

      # # print "---------------------------------------------------------------"
      # # print type(e), e
      # # print "---------------------------------------------------------------"

    #   self.connection.send("")
    
if __name__ == "__main__":

  parser = OptionParser()
  parser.add_option("-d", "--cache-dir", default=".cache")
  parser.add_option("-i", "--insert", default=False)
  parser.add_option("-c", "--count", action="store_true", default=False)
  (options, args) = parser.parse_args()

  determinize = options.insert
  if (determinize):
    f = open('determinize.js')
    determinize_file = f.read()
    f.close()
    determinize ="<script>"+determinize_file+"determinize("+determinize+");</script>"
  type_on = options.count
  cache_dir = options.cache_dir

  server_address = ('127.0.0.1', 1234)
  #proxyserver = ThreadingProxyServer(server_address, ProxyHandler)
  proxyserver = PooledProxyServer(server_address, ProxyHandler)
  print 'proxy serving on %r' % (server_address,)

  os.system("mkdir " + cache_dir)
  print "cache directory:", cache_dir

  try:
    proxyserver.serve_forever()
  except KeyboardInterrupt:
    for f in working:
      # print "CLEAN-UP: rm", f
      os.system("rm " + f)
    # print '\nexiting...'
    # print "Redirect!!!!!!!!!!!!!!!!!!", len(redirect_map)

