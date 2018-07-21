"""
A *stream* is a file-like object, inheriting from stdlib's IOBase, allowing
to read and write to it.

Streams are operated by default in buffered binary mode to allow arbitary data
and optimum performance, supporting commands like ``gzip`` transparently.

Commands can customize their streams with their ``.io()`` method.


Buffers, buffers everywhere...

    - StdIn / StdOut:
        - TTY: line buffered (~1Kb)
        - Pipe: buffered (~4Kb)
    - StdErr: is unbuffered according to POSIX


    Then we have that the stdout of a command might be piped to the stdin of
    another, so even if the stdout is unbuffered the stdin might not be, ending
    with the same problem.

    Finally we have streams in Python which also buffer data, so we have quite
    a bunch of buffering going on.


On normal operation the pipes are binary:

    >>> cat | head
    cat.stdin = sys.stdin
    head.stdin = cat.stdout
    head.stdout = sys.stdout

When interacting with Python functions it's interesting to read text though:

    >>> cat.text | pipe_map(lambda ln: ln.upper())
    cat.stdin = sys.stdin
    # detect stdout encoding from environment
    cat.stdout = TextIOWrapper(cat.stdout, encoding=detected)
    pipe_map.stdin = cat.stdout
    pipe_map.stdout = sys.stdout




stdin | wc['-l']        # buffered input
stdin.raw | wc['-l']    # unbuffered input
stdin.text | wc['-l']   # convert to text (infer encoding)
stdin.enc('utf-8') | wc['-l']  # convert to text (force encoding)


cmd.utf8 | gzip
cmd.stdout.utf8 | gzip.binary

cmd -[binary]-> [utf8->unicode] -[utf8]-> gzip -[binary]->

cat('file.gz') | gunzip   # stdout is binary buffered
cat('file.gz').stdout | gunzip   # stdout is binary buffered
cat('file.gz').raw |      # stdout is binary unbuffered
cat('file.gz').binary |   # stdout is binary buffered
cat('file.gz').ascii |   # stdout forces ascii buffered
cat('file.gz').utf8  |   # stdout forces utf8
cat('file.gz').utf16  |   # stdout forces utf16
cat('file.gz').text |     # convert to text (infer encoding)
cat('file.gz').io('utf-8') | # convert to text (force encoding)

cat('file.gz').io(out='raw', err='utf-8')
cat('file.gz').io(in='utf-8', out='binary', err='auto')
cat('file.gz').io(out='utf-8', lines=1, eol='\0', in_bytes=0)

cmd.pipe(out=grep['foo'])

buffer(0) <= cmd             # unbuffered
buffer(lines=1) <= cmd       # 1 line at a time
buffer(kb=10) <= cmd       # 10Kb at a time
buffer(mb=1) | cmd       # 1Mb buffer

cat.io('utf-8') | cmd       # decode utf-8 and pass text to cmd
cmd | cat.io('utf-8')       # get utf-8 binary and produce text
cmd | cat.io(out='utf-8')       # get text and produce binary in utf-8

cmd.raw ^ head  # this will fail because .raw is a stream so ^ doesn't match the command

cat('file.gz').stdout.raw ... same as above

cat | progress(lines=100, kb=4, eol='\n', bytes=10)
cat | progress(lines=100, interval=10)  # display progress every 10 seconds
cat | rate(mb=1, lines=1, eol='\n', enabled=True) | grep['foo']  # rate 1Mb/s

TODO: Check http://www.pixelbeat.org/programming/stdio_buffering/.
      If the stdbuf command is available it can be used to try to setup the
      launched command in a similar fashion to the python streams.
      Guarded under a --pysh:stdbuf flag.
      Can we build stdbuf and bundle it with pysh?

TODO: An alternative that comes with OSX to disable buffering might be
      expect -c 'spawn -noecho  ls -la  ; expect'

TODO: Also for unbuffered some common env vars like `PYTHONUNBUFFERED=1`
      might be set

TODO: Check os.sendfile for optimized pipe copy on Mac/Linux/BSD

"""

from io import IOBase, TextIOWrapper, TextIOBase, BufferedIOBase, BufferedReader


class Stream(IOBase):
    """ The base stream class for pysh streams
    """

    @property
    def utf16(self):
        if isinstance(self, BufferedIOBase):
            buffer = self
        else:
            buffer = BufferedReader(self)
        return TextIOWrapper(buffer, encoding='utf-16')

    @property
    def utf8(self):
        if isinstance(self, BufferedIOBase):
            buffer = self
        else:
            buffer = BufferedReader(self)
        return TextIOWrapper(buffer, encoding='utf-8')

    @property
    def ascii(self):
        if isinstance(self, BufferedIOBase):
            buffer = self
        else:
            buffer = BufferedReader(self)
        return TextIOWrapper(buffer, encoding='ascii')

    @property
    def binary(self):
        if isinstance(self, TextIOBase):
            return self.buffer
        return self



class NullStream(Stream):
    """ Emulates /dev/null semantics on pure Python code so we avoid
        the syscalls.

        TODO: Use os.devnull? https://docs.python.org/3/library/os.html#os.devnull

            io.open(os.devnull, mode='rw') ?
    """

    closed = False

    def isatty(self):
        return False

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    def read(self, size=-1):
        print('Null.read({!r})'.format(size))
        return b''

    def readinto(self, b):
        print('Null.readinto({!r})'.format(b))

    def readline(self, size=-1):
        """ Used for iteration """
        print('Null.readline({!r})'.format(size))
        return b''

    def write(self, b):
        print('Null.write({!r})'.format(b))
        return 0

    def close(self):
        pass  # null streams are always open

    def __del__(self):
        pass



def noblock(stream: IOBase, *, max_size=256*1024):
    #TODO: This is a placeholder, prototype pending

    from threading import Thread
    from queue import SimpleQueue, Empty

    def consume(stream, queue):
        for line in stream: # use .readline(size=XXX)
            #XXX check max_size against queue contents
            queue.put(line)

    q = SimpleQueue()
    t = Thread(target=consume, args=(stream, q))
    t.daemon = True  # do not block the parent from exiting
    t.start()

    class NoBlock(IOBase):
        def readline(self, size=-1, *, timeout=0):
            # pop from queue until we have enough size/nl
            # feed back the remainder at the top of the queue (threadsafe?)
            # return what we got
            line = stream.readline(size)

        def __del__(self):
            pass  # kill thread?

    return NoBlock(stream)


null = NullStream()
stdin = open('/dev/stdin')

for line in null:
    print('!!LINE', line)

for i in range(10):
    print(i, file=null)

