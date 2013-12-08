# package: httpmessage
#
# Copyright (c) 2009 Matt Anderson.
#  
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#  
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#  
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import time

from httpmessage.message import HttpMessage, RequestMessage, ResponseMessage
import httpmessage.dispatch as dispatch
import httpmessage.const as const
import httpmessage.exc as exc

__author__ = "Matt Anderson (manders2k.dev (at) gmail.com)"
__copyright__ = "Copyright 2009-%i, Matt Anderson" % time.localtime().tm_year
__contributors__ = []
__license__ = "MIT"

__all__ = """HttpMessage RequestMessage ResponseMessage dispatch const
exc""".split()

__version_info__ = (0, 2, 'alpha')
__version__ = '%i.%i %s' % __version_info__



