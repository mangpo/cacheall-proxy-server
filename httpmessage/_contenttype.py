import mimetypes

# When :func:`mimetypes.guess_extension` finds multiple possibles, it does a
# really LOUSY job at picking one. The following map is a set of preferred
# default values. 
extmap = {
    'application/mathematica': 'ma',
    'application/msword': '.doc',
    'application/octet-stream': None,
    'application/postscript': '.ps',
    'application/vnd.ms-excel': '.xls',
    'application/vnd.ms-powerpoint': '.ppt',
    'application/x-msdownload': '.exe',
    'application/xhtml+xml': 'xhtml',
    'application/xml': '.xml',
    'audio/basic': '.au',
    'audio/midi': '.midi',
    'audio/mpeg': '.mp3',
    'audio/ogg': '.ogg',
    'audio/x-aiff': '.aiff',
    'image/jpeg': '.jpg',
    'image/svg+xml': '.svg',
    'image/tiff': '.tif',
    'message/rfc822': '.eml',
    'text/calendar': '.ics',
    'text/html': '.html',
    'text/plain': '.txt',
    'text/sgml': '.sgml',
    'text/x-c': '.c',
    'text/x-creole' : '.creole',
    'text/x-markdown' : '.markdown',
    'text/x-textile' : '.textile',
    'text/x-rst' : '.rst',
    'video/mp4': '.mp4',
    'video/mpeg': '.mpg',
    'video/quicktime': '.mov',
    'video/vnd.mpegurl': '.m4u',
    'video/x-dv': '.dv',
    'video/x-flv': '.flv',
}

def guess_extension(mimetype):
    if mimetype is None:
        mimetype = ''
    semipos = mimetype.find(';')
    if not semipos == -1:
        mimetype = mimetype[:semipos]
    ext = extmap.get(
            mimetype, mimetypes.guess_extension(mimetype))
    if not ext:
        ext = '.data'
    return ext







