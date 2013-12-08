import os, sys

try:
    import httpmessage
except ImportError:
    from os.path import split, dirname, abspath
    parent_dir = split(dirname(abspath(__file__)))[0]
    sys.path.append(parent_dir)

import httpmessage