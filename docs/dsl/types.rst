Types
=====

These are the main types exposed in the DSL, while their internal details are
out of the scope for this section or even required for using them in a script,
it's important to understand their semantics.


Streams
-------

A *stream* is a file-like object, inheriting from *Python's stdlib* IOBase_,
it allows to read and write to it. Since we build upon the stdlib it simplifies
the integration with plain Python code, for instance the file object returned
by the open_ function is fully compatible.

Every script starts with the following streams defined:

**null**

    Ignores anything we send to it, so it's always empty.

**stdin**

    Receives data from another program.

**stdout**

    Used to output data from our script.

**stderr**

    Used to output diagnosis information from our script.


Paths
-----

Python offers the pathlib_ module in the *standard library*, which offers an
object oriented interface for paths, while we inherit from its ``Path`` class
we have **quite different semantics**:

    **lazy evaluation**

        When a path is defined, or even globbed, the result is not immediately
        evaluated. Instead it stores the current configuration so it gets applied
        when we force its evaluation (for instance when casting ``str(path)``).

        This detail is specially important if we are defining relative paths
        and then change the directory between their definition and their
        evaluation. In that case the paths will evaluate with the working
        directory currently active.

    **immutability**

        While Python usually mutates the internal state of an object when we
        modify it somehow, in the case of paths this doesn't happen, instead a
        cloned instance is returned with its current configuration and then the
        modification is applied to it.

        This is required for **lazy evaluation** to work without surprises,
        otherwise we might inadvertily modify a path instance that might be used
        in the future.

Given those semantics we should think about *pysh paths* as *path builders*, where
there is a setup step that is later used as many times as required.


Path factory: _
~~~~~~~~~~~~~~~

.. TODO:: move to operators path section??

Allows to easily define paths in a concise style. The symbol by itself refers
to the *current working directory* (the ``$PWD`` variable in *Bash*).

>>> print( _ )
the current working dir

Additionally it allows to create a path to an arbitrary file or directory,
accepting relative and absolute paths:

>>> _('relative/path/to/file')
resolves to: ./relative/path/to/file

>>> _('/usr/bin/bash')
absolute path: /usr/bin/bash


For accessing more special paths the slicing syntax can be used as follows:

    ``_['.']``
        current working directory, exactly equal to plain ``_``.

    ``_['..']``
        parent directory, meaning ``./../`` in a shell. Each additional dot will
        navigate one level up in the directory structure, so ``_['....']`` means
        ``./../../../``.

    ``_[-N]``
        navigates up the path the given number of directories. For example ``-2``
        would mean ``../../``.

    ``_['/']``
        root directory of the file system, same as ``_('/')``.

    ``_['~']`` or ``_['~user']``
        home directory of the logged user or a specific user.

    ``_['*.jpg']``
        glob syntax can be used to match multiple paths.

    ``_['c:']``
        select a drive for the path (Windows only).

    ``_['//']`` or ``_[r'\\']``
        UNC path (Windows only).


.. note::
    the slicing syntax is available on all path instances, even if they already
    point to a different path than the default ``.``. So it's possible to have
    something like: ``_('/absoulute/path/to')['..']``.

.. Caution::
    The ``_`` variable name is considered protected on *pysh* scripts. If you
    try to assign a value to it (i.e: ``_ = None``) the script will fail with a
    syntax error.
    This is done because in some programming styles the ``_`` symbol is used
    to signify an unused value, usually when unpacking, so we try to catch these
    cases as early as possible.



Commands
--------

Commands also have **lazy evaluation** and **immutability** semantics. They need
them to simplify composition, which is a core mechanic in *pysh* to make scripts
ergonomic but easy to maintain.

Creating a command for an external utility is as simple as calling the ``command``
factory function:

>>> grep = command('grep')
    CommandBuilder<grep>

Now we can *build an invocation* by providing arguments to it. There are two
ways to do so, with slightly different behaviors:

    **call**

        The value provided as argument is used verbatim on the called command.
        No need to think about strange quoting and escaping rules.

        >>> grep('-e', 'foo bar')
            grep -e 'foo bar'

        Keyword arguments are automatically converted to options following a
        set of rules which can be tuned when creating a command.

        >>> grep('foo bar', 'myfile.txt', A=3, line_buffered=True)
            grep -A 3 --line-buffered 'foo bar' myfile.txt

        .. Hint:: See :class:`pysh.command.ExternalCommandSpec` for more details.

    **slice**

        When slicing the value is splitted on whitespace, similarly to what a
        shell would do, so one or more arguments can be added to the command.

        >>> grep['-e   foo    bar']
            grep -e foo bar
        >>> grep[r'-e escaped\ whitespace\ \ is\ \ preserved']
            grep -e "escaped whitespace  is  preserved"

        .. Caution:: There is no parsing of quoted strings on the value, **only
                     whitespace** has special meaning. If you need to provide some
                     text with quotes use the **call** style.

        .. TODO:: experiment with supporing globing inside slice syntax.

Each time we *call* or *slice* on a command a cloned instance is returned with the
changes, this usually works transparently due to the chained nature of the DSL.
However if you try to use a more imperative style you need to be aware of it:

>>> grep['-e']
>>> grep('foo')
    grep foo  # not what we might be expecting
>>> grep['-e']('foo')
    grep -e foo  # now it works
>>> a_grep = grep['-e']
>>> a_grep = a_grep('foo')
>>> a_grep
    grep -e foo  # also works since we're using the returned copy

Evaluation of the built command happens explicitly when we cast it to a
primitive value:

>>> str( grep['foo'] )
    executes and returns stdout as a string
>>> bytes( grep['foo'] )
    executes and returns stdout as binary data
>>> int( grep['foo'] )
    executes and returns the exit status code
>>> bool( grep['foo'] )
    executes and returns True if it exited with 0, False otherwise
>>> for line in grep['foo']:
>>>     print(line)
    execution is also triggered by iteration


AutoExpr transformation
~~~~~~~~~~~~~~~~~~~~~~~

.. TODO:: move to operators??

A key ergonomics feature is a transformation applied to scripts by *pysh*
where it will detect expressions that form a statement on their own,
usually meaning that they are not part of an assignment or a flow control
construct. Those expressions will be automatically evaluated when the
script executes, given the laziness semantics of a *command* this allows
to overcome the requirement of casting it to force its evaluation.

>>> grep('foo')        # grep is invoked when the script reaches this line
>>> cmd = grep('foo')  # only built and assigned, grep is not invoked
>>> cmd                # grep is invoked now

.. Note:: This transformation is applied by default when executing a script
          with the ``pysh`` command line interface.


Shell command: sh
~~~~~~~~~~~~~~~~~

.. TODO:: move out to a section about utilities.

There are many good reasons to use an *sh compatible shell* to run a command,
sometimes it's just easier to express something with its syntax, maybe we're
copy-pasting a one liner from a Stack Overflow answer or perhaps we're porting
some existing shell script and want to have something running quick.

With the ``sh`` command we can do that easily and with some degree of safety if
it's used sparingly.

>>> sh('ls *.jpg')
    /bin/sh -e -c 'ls *.jpg'   # globing is done by the shell
>>> sh(' cat file.txt | grep foo ')
    /bin/sh -e -c 'cat file.txt | grep foo'  # piping is handled by the shell

Additional arguments are supported so we don't have to worry about quoting and
escaping stuff:

>>> sh('grep', '-e', 'foo')
    /bin/sh -e -c 'grep "$@"' -- -e foo  # note how "$@" was added to receive the args

It also implements the *attribute access protocol*  as a quick way to use external
commands without interacting with the ``command`` factory.

>>> ext_cat = sh.cat
>>> ext_cat('file.txt')
    /bin/sh -e -c 'cat "$@"' -- file.txt

>>> sh.git_status['--pretty']  # _ will fallback to - if not found
    /bin/sh -e -c 'git-status "$@"' -- --pretty

Variables in the scope can also be used, the ``sh`` command will parse the
**first argument** to detect references like ``$variable`` or ``${variable``,
making those available in the *environment* when executing the script.

>>> fname = _ / 'file.txt'
>>> pattern = 'foo'
>>> sh('cat "$fname" | grep "pre-${pattern}"')
    fname=./file.txt pattern=foo /bin/sh -e -c 'cat "$fname" | grep "pre-${pattern}"'

For longer snippets where we don't want to pipe or redirect its output, it's handy
to use the :ref:`Lazy: <= 🚧` operator with a raw multiline literal:

>>> sh <= r'''
>>>     num_files=$(ls | wc -l)
>>>     echo "Number of files: $num_files"
>>> '''


.. Note::
    ``sh`` will launch ``/bin/sh`` which on many systems is actually *bash* or
    *dash* in *posix mode*. However restricting to *posix syntax* is recommended
    if you want to keep the script portable.


Pipeline
--------

A pipeline groups *one or more commands* with their redirection configurations.
It's a helpful abstraction to handle arbitrarily complex chains of commands as
a simple entity.

>>> pipeline = cat | wc['-l']
  # the above generates a pipeline composed of two commands
>>> pipeline > 'results.txt'
  # redirects the output of the pipeline to a file
>>> echo("foo") | pipeline
  # feed some content to the first command in the pipeline


.. Note::
    *Command* and *Pipeline* are used interchangeably in the documentation since
    almost all operations available for a command are also exposed in a pipeline.



.. _open: https://docs.python.org/3/library/functions.html#open
.. _IOBase: https://docs.python.org/3/library/io.html?highlight=stringio#io.IOBase
.. _pathlib: https://docs.python.org/3/library/pathlib.html