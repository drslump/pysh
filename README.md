# pysh

Python for shell scripting

> :warning: This is totally **experimental**, fully **broken**. Do not use yet!

[![Build Status](https://travis-ci.org/drslump/pysh.svg?branch=master)](https://travis-ci.org/drslump/pysh)

## Goals

 - Syntax is standard Python (full IDE support)
 - Ergonomic (pipes, redirections, autoexpr, paths, ...)
 - Sensible defaults (i.e. docopt, env defaults, logging, ...)
 - Strong support for parallelism
 - Biased towards unix scripting (barebones windows support)
 - Wrappers for common commands (cat, head, xargs, ...)
 - No support for interactive mode!


## Requirements

 - Python 3.6 (at least while prototyping)


## AutoExpr

In `cat('foo.txt') | head[-10]`, a normal Python interpreter would call `cat`,
get a slice from `head` and execute the `__or__` of the resulting values. That's
totally fine but on a shell script we want to build a composite command and
execute it. There are a number of ways to solve it:

```py
# Overload the __call__ operator
( cat('foo.txt') | head[-10] )()
# Overload some fancy operator like Plumbum does
cat('foo.txt') | head[-10] & FG
```

However that feels totally unnatural when doing a shell script. Unfortunately
there is no way in Python to detect a *statement* at runtime, although it's
possible to do so when parsing the source code. On the bright side it's fairly
easy to parse Python code and modify it just using the stdlib.

So when a file is executed with `#!/usr/bin/env pysh` it'll actually parse the
source and perform that optimization. The process is a simple transform where
for each expression statement in the module scope (ignoring function bodies)
a wrapper is injected like so:

```py
pysh.autoexpr( cat('foo.txt') | head[-10] )
```

Now that the expression statements are annotated we have a *hook* at runtime,
the `autoexpr` function, which can inspect the expression result and run it
if it's some sort of command.


## Execution flow

Each command in an expression is launched as a child process (popen) or a thread
if the command is implemented in Python. Then it waits until all of them complete.

While the programs are executed we need to manage the streams, since otherwise
the programs could block. There is a configurable buffer for each pipe, so we
don't block too much if both programs run at an approximate rate. Otherwise,
when the buffer fill up the producing program is blocked until there is room for
more.

For a subprocess the blocking is delegated to the OS, we just stop reading from
its stream. In the case of python functions we have to handle it ourselves, since
streams are modelled as generators we just stop consuming from it.

In the case of parallel we just have to spawn an executioner for each worker we
want to use. Each executioner will then run normally, and the whole synchronization
gets delegated to the stream processing mechanism.

> The GIL might affect the operation for python-commands, the external commands
  run on its own process so are not affected. It might be interesting to benchmark
  a bit to see if perhaps it's worth it to launch python commands on
  a subprocess instead of a thread.

TODO: signals


## Command wrappers

Each command wrapper returns a generator, that allows `pysh` to coordinate the
execution by polling from it when required, enabling the efficient use of
stream pipes and easing composition.

By default any exitcode different to 0 results in an exception, although this
can be suppressed for a specific command or with a context manager.

```py
cat('/dev/null') | grep('foo').catch(1)
print('') | ~grep('foo')  # ~ suppresses all errors

with catch(1):
    echo('bar') | grep('foo')

with redirect(stderr=null):
    gcc(files)

with redirect(stderr=stdout), catch(1, 3):
    cmd

with tty():  #redirect(tty=True) ?
    cmd
```

Fine tuning the execution, the command can be configured inside a context
manager, the actual execution will happen upon exiting it.

```py
with ~cat('fname.txt') as p:
    p.stderr >> 'errors.log'  #TODO: >> has higher precedence than |!!
    p | head['-10'] > 'results.csv'

print(p.exitcode)
```

Conditionals

```py
if exitcode(stdin | grep['foo']) > 0:
    print('foo was not found')

if (code := exitcode(stdin | grep['foo'])) > 0:
    print('result was {}'.format(code))

code = int(stdin | grep['foo'])  # __int__ resolves and returns exitcode

if bool(stdin | grep['foo']):  # __bool__ resolves and returns exitcode 0->True
    echo('found')
else:
    echo('not found)

stdin | grep['foo'] and echo('found') or exit(1, 'not found!')
stdin | grep['foo'].and_then( echo('found') ).or_else( exit(1, 'not found!') )
stdin | grep['foo'].map_status({
    0: echo('found'),
    '1..4': echo('error'),
    _: exit(1, 'not found!')
})
stdin | grep['foo'].map_status(
    _0 = echo('found'),
    _1_4 = echo('error'),
    _ = exit(1, 'not found!')
)
stdin | grep['foo'].catch(
    _1 = echo('found'),
    _1_4 = echo('error'),
    _ = exit(1, 'not found!')
)

stdin | pipe.map(str.upper)
stdin | pipe.map(str.upper, split='16K')
stdin | pipe.filter(...)
stdin | pipe.reduce(...)

stdin | pipe.words.map(str.upper).filter(str.isalpha)
# read content and extract words, upper them and retain the alpha ones
stdin | pipe.split('-')...
stdin | pipe.split(re='[,;/]')  # or .resplit
stdin | pipe.match(r'[A-Z]+')

['foo', 'bar'] | stdout  # 'foo\nbar\n' -- by default each item is a line
(json.dumps(x) for x in objects) | cat > 'output.jsonl'
cat('output.jsonl') | pipe.lines.map(json.load).map(modify).jsonl()
jsonl = lambda transform: pipe.lines.map(json.load).map(transform).jsonl()
cat('output.jsonl') | jsonl(modify) > _/'final.jsonl'
```

Sometimes we want to work with the whole data instead of streaming it:

```py
# casting a command to a string automatically executes and consumes it
print(cat(fname))
data = str( cat(fname) )  # unicode() on Py2 -- .to_text()

# work with binary data
bindata = bytes(cat(binfile))  # .to_binary()

# collect into a list
lines = list(cat(fname))

# functional
cat(fname).collect(stdout=lambda s: print(len(s)))
errors = cat(fname).collect(stderr=True)
```

pysh should offer a helpful set of core utilities, some implemented
natively in Python. Popular commands should be available in a `coreutils`
module. More specific ones might be available in an extras module.
It's still unclear if commands offered by pysh should try to normalize
differences across platforms (bsd vs linux vs osx), in principle this
would be really nice but not sure if will work properly.


## Functions

Sometimes we might want to implement some logic in Python instead of using an
external command. However we don't want to special case that functionality, it
should behave exactly as a command.

```py
@pysh.script
def filter_empty():
    cat | grep['-v', '-e', '^$']
```

The `script` decorator takes care of wiring the function execution with the
input/ouput streams, as if it was an external command. If we however want to
have finer control over the process we can also do so:

```py
@pysh.wrapper
def filter_empty(p):
    for line in p.stdin.lines():
        if line.strip() == '':
            continue
        print(line) >> p.stdout
```

### Parallelism

In the era of multicore computing we need to enable those cores on our shell
scripts too:

```py
cat('file.txt') | demux( grep('foo') )
range(4) | demux(lambda: time.sleep(5.0))

for i in range(100):
    fork << echo(i)               # bound to the number of cores
    fork(jobs=4) << echo(i)       # 4 at a time
wait()

# bound to number of cores
with fork as ff:
    for ln in stdin:
        echo(ln) ^ ff
    # waits before continuing

# run commands in parallel but iterate sequentially
for p in stdin | demux(sleep(randint(10))):
    echo(p.exitcode)
```

> GNU's parallel is a beast with a ton of functionality. Our `parallel` is much simpler.


### Streams

Streams are another important abstraction on shell scripts. Commands can consume
a `stdin` stream and produce values on the `stdout` and `stderr` ones. In `pysh`
those streams are generators, whose yielded values are always casted to strings,
this allows to easily integrate with externals commands.

When piping the job scheduler may block some streams if they fill up the internal
buffer, we can have tighter control for the buffering:

```py
cat(fname) | buffer('4kb') | wc[-l]       # chunks of 4kb
cat(fname) | buffer(kb=256) | wc[-l]      # chunks of 256kb
cat(fname) | buffer(lines=True) | wc[-l]  # buffer until a newline
cat(fname) | unbuffer( wc['-l'] )         #
```

Process substitution for instance can be implemented as:

```py
# wc -l <(curl "google.com")
wc['-l'](curl("google.com") | psub)
```

TODO: Check https://github.com/fish-shell/fish-shell/issues/1040 for nifty details
      of the problems of implementing process substitution.

Redirect shortcuts:

```
cat | wc['-l']  # send stdout from cat to stdin for wc
# cat.pipe(stdout=wc['-l'])
cat | +wc['-l'] > outerr.log   # +<cmd> merges stderr into stdout
# cat.pipe(wc['-l'].pipe(stderr=stdout))
cat | -wc['-l']                # -<cmd> dismisses stderr
# cat.pipe(wc['-l'].pipe(stderr=null))
cat | --wc['-l']               # --<cmd> dismisses stdout and stderr
# cat.pipe(wc['-l'].pipe(stdout=null, stderr=null))
```


### sh shortcut

`sh` allows to call external commands without defining them previously.

```py
sh.grep(fname, e=['foo', 'bar'])
sh['pip3.6'] ('freeze')
sh['/path/to/cmd']['--version']
```

note that this launches the command via the system shell, so it allows
to use operators on it:

```py
sh[r'''
    cat | grep -e foo > file.out
    wc -l file.out | cut -f1
''']  # no variable interpolation

local = 10
sh << r'''
    echo $local
'''  # variable interpolation
```


### Paths

For some use cases a path can simply be a string:

```py
cat > 'output.txt'
```

Paths can be constructed safely:

 - `/`: handles right string as path
 - `//`: parses right string as glob

```py
_ / 'escaped?'  # ./escaped\?
_['~'] / 'foo bar'      # ~/foo\ bar
_['/'] / 'abs/nested' / '*.jpg'   # /abs/nested/\*.jpg
_['c'] // 'windows/*.dll'  # c:\windows\*.dll
```

Globs compose:

```py
_ // '*' / '.git' // '{hooks,info,objects}' // '*'
_ // '*' / '.git' // ('hooks','info','objects') // '*'
_ // lambda path: path[-1].startswith('x-') // '*.jpg'
```

> allowing functions in segments might break some use cases that
  require casting to strings. Perhaps they are not worth it.

Subpaths:

```py
_('/foo/bar')[-1]  # /foo
```

TODO: Should paths implement `|` defaulting to cat?

    _/'file.txt' | head
    cat('./file.txt') | head

    ls[ _ * '*.jpg' ]


### Arguments

The docblock of the script is automatically parsed with [docopt](docopt.org)
in order to simplify the handling of script parameters.

```py
#!/usr/bin/env pysh
"""
My script.

Usage: my_script [options] <host> <port>

Options:
  --all         List everything.
  -h --help     Show this screen.
  --version     Show version.
"""

if args['--version']:
    print('1.0')
    exit(0)

print('Endpoint: {}:{}'.format(args['<host>'], args['<port>']))
```

If no docopt is provided then the `args` will contain a generic parsing
of the opts following modern conventions.

```py
# -aab --foo=foo -- arg1 arg2
{'-a':[True, True], '-b':[True], '--foo':['foo'], '*': ['arg1', 'arg2']}
```

Moreover, `argv` is also available and behaves as expected in normal
scripts.

Some interesting features worth investigating:

 - `-` means stdin/stdout (but how to know which one?)
 - read arguments from `--@opts.txt` and data from `@somefile.txt`
 - standarized isatty overrides from env or args (`--pysh:tty=yes`)
 - multi command mode a la git: `cmd sub` -> `cmd-sub`
 - bash/zsh/fish autocompletions
 - `--pysh:xxx` options for pysh itself (i.e logging)
 - apply templating to docopt to insert program name, version, etc.


The `@pysh.main` decorator marks a function to be executed when that script
is run. This means that the script can run with plain Python and pysh will
analyze the function as if it was the script, extracting the docopt from it
or using its parameters to build an automatic arguments parsing.

```py
@pysh.main()  # keyword ``docopt=__doc__`` to override
def main(src:Path, *files, *, plugins=[], verbose=False, *kwargs):
    """ Parses the given files and do cool stuff.
    """
    ...

# alternatively:
if __name__ == '__main__':
    pysh.main(main)
```


### Misc

Simple progress bar helper (determinate and undeterminate).
Reference https://github.com/tqdm/tqdm

Rate limiter filter (bytes/lines).

``noblock(stream: IOBase)`` helper that patches a IO based stream so that it
operates in a pseudo non-blocking mode. Underneth it spaws a thread to do the
blocking operations using a ``Queue`` for synchronization. All methods are
patched to be non-blocking and also to accept a ``timeout=seconds`` keyword.


### Shebang

Most shells will parse shebangs as a command with an optional argument, even if
multiple arguments are provided they are bundled into a single one. For instance
`#!/usr/bin/env pysh --trace` will execute as `env "pysh --trace"`.

We can define additional options by having an extra line:

```
#!/usr/bin/env pysh
#pysh: --trace
```

Which is equivalent to `#!/usr/bin/env -S pysh --trace` on supported systems.

pysh will check the comments at the top of the file looking for the `pysh: ...`
pattern. If it's found then the options will be parsed and applied for that script.


### bangexpr

It might be interesting to optionally allow typical shell syntax for some
use cases where we don't actually need composition. It would help for instance
when porting simple bash scripts.

These are some examples of the transformations:

```py
! cat -u | grep -e foo > output.txt
# cat('-u') | grep('-e', 'foo') > 'output.txt'

result = ! echo foo
# result = echo('foo')

needle = 'foo'
! echo $PATH | grep $needle  # uppercase are envs, otherwise locals
# echo(env['PATH']) | grep(needle)

! echo foo \
       bar \
       baz
# echo('foo', 'bar', 'baz')
```

Additionally a `!!` can be used to defer the execution into a subshell,
in that mode pipes and redirections are not handled by `pysh` but by the
default `$SHELL`:

```py
needle = !! echo foo
!! echo $PATH | grep $needle
# pysh.bangbang('echo $PATH | grep $needle', vars={'PATH': env['PATH'], 'needle': needle})
# env needle=foo "$SHELL" -c 'echo $PATH | grep $needle'
```

> the parser will look for `$<ident>` and `${expr}` patterns (bash syntax)
  and make their values available as environment variables.

These expressions are not automatically evaluated, the evaluation relies on
the *autoexpr* pass like the normal DSL.

> Probably this feature should be gated under a `pysh --bangexpr` option


### Eval mode

    pysh -e 'random.randint(1, 9)'

The eval mode is useful for one liners, mainly to use on interactive shells.
It's similar to `python -c` but with the following twists:

 - identifiers fallback to automatically try to import a package.
 - last expression is automatically printed to stdout unless it's `None`.
 - when last expression is a boolean True exits with 0 and False with 1.
 - perhaps: support $env interpolation


### Packaging

Leverage Python packaging to automatically generate a distributable script.

    pysh --pkg my-script.pysh *.py

> first argument is the entry point, the rest are importable files

It will generate a temporary package structure with a setup.py configured
and run `bdist` on it to get a distributable.

Dependencies and metadata can be defined on the command line or included as
`#pysh:` comments.
