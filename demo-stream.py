import sys
import os
import subprocess


def run(*args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=None):
    return subprocess.Popen(
        args,
        shell=False,  # no need to go via shell
        bufsize=-1,  # default buffer size
        executable=None,  # override the command to run from args

        # TODO: if we know the redirection in advance we can set it here (devnull, STDOUT)
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,  # STDOUT: merge into the stdout pipe

        preexec_fn=preexec_fn,  # required to create process groups
        close_fds=True,  # subcommand won't be able to access the parent descriptors
        pass_fds=(),   # we can provide a list of descriptors for the child to use

        cwd=None,  # run on the parent CWD

        restore_signals=True,  # enables SIGPIPE, SIGXFZ and SIGXFSZ which are disabled in Python
        start_new_session=False,  # calls setsid(), in theory only required for daemons

        env=None,  # pass a dict to override the child environment

        encoding=None,  # force text encoding for the streams
        errors=None,    # how to handle encoding errors
        #universal_newlines=None,   # (aka text) -> streams are TextIOWrapper

        startupinfo=None,  # Windows stuff
        creationflags=0  # Windows stuff (i.e priority)
    )


## http://eyalarubas.com/python-subproc-nonblock.html
## https://lyceum-allotments.github.io/2017/03/python-and-pipes-part-6-multiple-subprocesses-and-pipes/
## https://docs.python.org/3/library/asyncio-subprocess.html
## https://pymotw.com/3/asyncio/subprocesses.html
## http://sarge.readthedocs.io/en/latest/internals.html
## https://github.com/oconnor663/duct.py/blob/master/duct.py
## https://pymotw.com/3/subprocess/#process-groups-sessions


"""
Using AsyncIO support for subprocesses:

 - Needs a custom loop reactor on Windows
 - loop reactor must run from the main thread
 - the protocol based approach looks clean enough

The major downside is probably that it would be hard port to previous Python
versions. Although the protocol abstraction should keep the complexity on check
and offer a target interface to emulate on previous versions.
"""

"""
Common approach relies on spawning a thread per stream and using Queue
to synchronize. Feels heavy but it's probably just fine for this use case.
The major issue would be keeping buffering on check since we are adding
the Queue mechanism in the middle, although perhaps it's possible to go
directly to IOBase instances since we don't really need out-of-band
synchronization.
"""

"""
Lower level would be fnctl and OS select/polling. This has two major
drawbacks, we can't rely on the io classes, instead we'll have to implement
the abstraction on top of the os.xxx primitives. Secondly this is not portable
at all outside unix.
"""

"""
Perhaps it's much simpler if we go low level but not too much. Every stream
will either be created from a subprocess or from os.pipe()+os.fdopen. That gives
us some *file objects* to work with. Now, since all of them have a fileno()
they can be used directly with popen(), and since all of them are wrapped with
an IOBase interface we can use them with the normal python code.

Findings in Bash:

    > X="$(sleep 10)" sleep 10

    - $(sleep) is run first and Bash waits for it to terminate
    - $(sleep) has the same pgid as the parent bash
    - sleep is run when $(sleep) terminates
    - sleep has a different pgid

    > sleep 10 | sleep 11

    - both run at the same time
    - both share a pgid which is different to the parent bash

    So any "subshell" runs on the same pgid as its parent, however
    each statement creates its own pgid. I guess the reason is that
    Bash only models a "job" for a whole statement, which can be
    paused, sent to background, and need careful handling of signals
    and so on. However for subshells, they act as computations in the
    parent one.

    In our case however, without an interactive mode, we don't need
    to create process groups to handle signalling. Every suprocess will
    receive the signals received by the parent process.

    Perhaps the only case where we would need a process group would be
    for commands that have defined a signal handler or choose to ignore
    a signal. In that case they need to run on their own group and the
    parent process will have to handle the forwarding of the signals.
    For that we can simply use the flag ``start_new_session``.
"""

stdin = sys.stdin.fileno()
stdout = sys.stdout.fileno()
stderr = sys.stderr.fileno()


# pipeline = [ ('base64', '/dev/urandom'), ('head', '-c', '10000000'), ('wc', '-c') ]
# pipeline = [ ('base64', '/dev/urandom'),  ('wc', '-c') ]
pipeline = [ ('dd', 'if=/dev/zero', 'of=/dev/stdout', 'count=1048576',  'bs=1024'), ('wc', '-c') ]
# pipeline = [ ('curl', 'https://as.com'), ('sort', '-r'), ('head', '-10') ]
# pipeline = [ ('sleep', '10'), ('sleep', '10') ]
# pipeline = [ ('cat',) ]


#XXX: No Windows support when querying file descriptors
import selectors
selector = selectors.DefaultSelector()

jobs = {}
pgid = None
# for i, cmd in enumerate(pipeline):
#     #XXX actually when piping two subprocesses we can wire them directly.
#     #    Python is already creating a pipe for them.
#     rd, wr = os.pipe()

#     if not pgid:
#         preexec_fn = os.setpgrp  # first will be the group leader
#     else:
#         preexec_fn = lambda: os.setpgid(0, pgid)

#     #XXX setting a pgrp means that signals on the parent won't reache the
#     #    launched processes, which at least for now is problematic, so disable.
#     preexec_fn=None

#     #TODO: set a common process group for the whole pipeline
#     p = run(*cmd, stdin=stdin, stdout=wr, stderr=stderr, preexec_fn=preexec_fn)
#     print('Run <{}> PID: {}'.format(cmd, p.pid))

#     if not pgid:
#         pgid = p.pid

#     sel.register(wr, selectors.EVENT_WRITE, (p, stdin, wr))
#     #XXX: do we need to check stdin too?
#     # sel.register(stdin, selectors.EVENT_READ, (p, stdin, wr))

#     jobs[ p.pid ] = (p, stdin, wr)

#     stdin = rd

for cmd in pipeline:

    p = run(*cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr)
    print('Run <{}> PID: {}'.format(cmd, p.pid))

    extra = (p, stdin, p.stdout.fileno())
    selector.register(p.stdout, selectors.EVENT_WRITE, extra)

    jobs[ p.pid ] = extra
    stdin = p.stdout.fileno()


#HACK: just use an extra process to forward to stdout
p = run('cat', stdin=stdin, stdout=stdout, stderr=stderr)

print('Processes launched!!!!!', flush=True)


# Polling doesn't block!!!!!!!!!!!
# TODO: https://docs.python.org/3/library/selectors.html#module-selectors
import time

cnt = len(jobs)
while True:
    events = selector.select(.1)
    if not events:
        print('TODO: empty select (timeout) -- fallback to manual polling')
        continue

    for key, mask in events:
        # print('Wake up from select!', key)
        p, stdin, stdout = key.data
        ret = p.poll()
        if ret is None:
            continue

        print('Closing stdin={} stdout={}'.format(stdin, stdout))

        try:
            selector.unregister(stdout)
        except KeyError:
            pass  # we might have already closed the pipe-right stdin

        #XXX Do we need to close stdin when program ends?
        try:
            os.close(stdin)  # might be already closed if pipe-left command terminated first
        except OSError:
            pass

        try:
            os.close(stdout)   # very important to close so the pipe-right command knows we're done
        except OSError:
            pass

        if ret < 0:
            print('PID {} Signal {}'.format(p.pid, -ret), flush=True)
        else:
            print('PID {} Exit {}'.format(p.pid, ret), flush=True)

        cnt -= 1

    if cnt <= 0:
        selector.close()
        print('No more jobs')
        break

    # Sleeping a little bit helps with performance when we have a very chatty
    # process generating tons of events.
    time.sleep(.05)

    # # polling based check (windows compatible)
    # for p, rd, wr in jobs.values():
    #     ret = p.poll()
    #     if ret != None:
    #         if ret < 0:
    #             print('PID {} Signal {}'.format(p.pid, -ret), flush=True)
    #         else:
    #             print('PID {} Exit {}'.format(p.pid, ret), flush=True)
    #         os.close(rd)
    #         os.close(wr)
    #         del jobs[p.pid]
    #         cnt -= 1
    #         break
    # if not jobs:
    #     print('Finished all jobs!', flush=True)
    #     break

    # time.sleep(.05)
