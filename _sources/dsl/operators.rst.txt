Operators
=========

.. Caution::
    In Python it's not possible to overload the logical operators (``not``,
    ``and``, ``or``) since they have short-circuiting semantics (PEP-532_ is
    deferred right now).

    The problem manifests when trying to use the ``cmd and ok or fail``
    and similar constructs which are quite common in shell scripts. We would
    like to keep that expression lazily evaluated but is not possible since
    the Python interpreter will try to resolve it immediately, trigering the
    evaluation of ``cmd` to know if it should go to the ``and`` or the ``or``
    branch.

    Some times it would work as expected, that is, when the expression is its
    own statement even if the command is lazily evaluated it would happen at
    that point anyway. However this could become very confusing when storing
    the command in a variable for later invocation or trying to use it with a
    *parallelization utility* which would break the *lazy semantics*.

    🚧 Experimentation will be needed to see if it's possible to solve this
    problem using an AST transformation. In theory the above could be rewritten
    as ``OR(AND(cmd, lambda: ok), lambda: fail)`` but we need to make sure that
    only *commands* are lazily evaluated, respecting the default behaviour for
    other values.


Pipe: |
-------

**command** ``|`` **command**

    The typical shell piping operation where the output of the program
    on the left is feed as input for the program on the right.

    >>> head['-10'] | grep('foo')
    head['-10'].pipe( stdout = grep('foo') )

    .. admonition:: meanwhile in Bash

        just as above sans the braces: ``head -10 | grep foo``

**command** ``|`` **function**

    When the right operand is a function then it acts as a *reverse application
    operator*, where the right operand receives the left one as argument.

    >>> head['-10'] | ','.join
    ','.join( line for line in head['-10'] )

**value** ``|`` **command**

    An arbitrary value as left operand is automatically wrapped in an iterator
    so it can be feed to the *command* on the right.

    >>> __doc__ | wc['-l']
    echo(__doc__).pipe( stdout = wc['-l'] )

    .. admonition:: meanwhile in Bash

        this is commonly ``echo "$variable" | command``.


Piperr: ^ 🚧
------------

.. Warning:: 🚧 Validate that it'll work as documented

🚧 **command** ``^`` (**stream** | **path** | **str**) 🚧

    Redirect *stderr* to a stream or a file.

    >>> gcc ^ null
    discard stderr output

    >>> gcc ^ stdout | wc['-l']
    merge stderr into stdout and count all the lines from both

    >>> gcc ^ errors.txt | wc['-l']
    store stderr in a file and count the lines on stdout

    .. admonition:: meanwhile in Bash

        quite similar, the ``^`` is ``2>``. An example: ``gcc 2>errors.txt | wc -l``

🚧 **command** ``^`` **command** 🚧

    Pipe *stderr* from the command on the left to *stdin* from the command on
    the right.

    >>> gcc ^ wc['-l']
    count lines on stderr (stdout is unused)

    >>> gcc ^ wc['-l'] | head
    count lines on stderr (unused), get head from stdout

    >>> gcc ^ (wc['-l'] > 'errcnt.txt') | head
    count lines on stderr and store them, get head from stdout

    >>> gcc > null ^ (grep['foo'] > stdout) | head
    dismiss stdout, grep stderr and send to stdout to get the head

    .. Note::
        ``^`` has higher precedence than ``|`` so parenthesis are probably
        required if you want to create a pipeline to process the stderr
        redirection.


    .. admonition:: meanwhile in Bash

        a bit cryptic but not far off: ``gcc 2>&1 >/dev/null | grep foo | head``


Redirection: > and >>
---------------------

**command** ``>`` (**stream** | **path** | **str**)

    Like in a standard shell the redirection places the output from the *command*
    on the left in the file referenced on the right, creating the file if necessary.

    >>> cat > stderr
    # the output of cat gets redirected to stderr

    Note that the ``>`` operator precedence is lower than ``|``, meaning that when
    redirecting a pipe expression its the output of the whole expression what gets
    redirected. You can use parenthesis to force a different interpretation.

    >>> cat | head > 'first-lines.txt'
    # runs cat to feed head and stores the result in a file

    Alternatively you can use its reverse operator ``<`` to make the expression
    more readable.

    >>> stderr < sh.git['status']
    # get the git status and output it to stderr

    .. admonition:: meanwhile in Bash

        exactly the same... ``cat | head > 'first-lines.txt'``

**command** ``>`` **function**

    An interesting use case for the redirection operator is to set a function as
    its target. In this scenario the whole output of the command will be buffered
    and then passed as an argument to the target function.

    >>> echo("hello") > len
    6  # len(b"hello\n")

**command** ``>>`` (**path** | **str**)

    Works exactly like the redirection operator ``>`` but if the target file exists
    it will append the contents at the end of it instead of replacing the previous
    data.

    >>> cat | head >> 'historic-data.txt'
    # Appends the new conetnts to the target file

    .. Danger::
        ⚠️ the precedence of this operator is higher than ``|``:

        >>> cat | head >> 'accum.txt'
            cat | (head >> 'accum.txt')

        Although in practice it should work with the proper semantics, there might
        be some construct that behaves unexpectedly.

    .. admonition:: meanwhile in Bash

        again exactly the same... ``cat | head >> 'historic-data.txt'``


Reckless: ~
-----------

``~`` **command**

    Ignores the *exit status* and *stderr* of the command. Normally a non 0 exit
    status would raise an exception that needs to be handled by the code, however
    some times we expect a command to fail under some conditions.

    This is specially useful since, unlike *sh*, we do raise errors if they
    happen on a pipeline. For instance, ``grep`` exits with 1 if it couldn't
    match anything.

    >>> cat(fname) | ~grep['foo'] | wc['-l']
    we don't really care if it could match something or not


    .. admonition:: meanwhile in Bash

        assuming Bash is running with ``-o pipefail``, this can be accomplished
        with a conditional and a subshell:
        ``cat fname | (grep foo 2>/dev/null || true) | wc -l``


Lazy: <= 🚧
-----------

.. Warning:: 🚧 Validate that it'll work as documented

🚧 **command** ``<=`` **expresion** 🚧

🚧 **function** ``<=`` **command** 🚧

    The operand on the left side will be called with the one in the right as
    argument. Since it has a very low precedence it can be used to receive a
    complex pipelined expression without having to use a function call with
    wrapping parenthesis.

    >>> echo['Seconds in a day:'] <= 60 * 60 * 24
    evaluates as: echo['Seconds in a day:'](86400)

    >>> print <= cat | wc['-l']
    evaluates as: print( cat | wc['-l'] )

    .. Hint::
        Due to it's low precendence it's an ideal operator to be used for control
        flow constructs. For instance to run pipelined commands in parallel.

    .. Caution::
        the reverse operator is ``>=`` which looks weird for this use case,
        so it's better to avoid it.


    .. admonition:: meanwhile in Bash

        nothing similar, it's solved with some substitution but that's equivalent
        to *pysh* function calls: ``echo 'Seconds in a day' "$((60*60*24))"`` or
        ``echo "$(cat | wc['-l'])"``.


Context Manager: with 🚧
------------------------

.. Warning:: 🚧 Validate this will work as intended

🚧 ``with`` **command** ``as`` **name**: 🚧

    Commands implement the `Context Manager`_ protocol, upon entering one the
    command is evaluated and a ``CommandInvocation`` object is provided. Unlike
    normal invocation the standard streams are not wired to the script ones,
    allowing to consume them imperatively inside the block.

    Upon reaching the exit of the block, if the standard streams haven't been
    redirected they'll be wired to the script ones and it'll block waiting for
    the execution to terminate if needed.

    This pattern is useful for complex pipelines, where the DSL operators might
    be harder to read and maintain.

    >>> with cat('fname.txt') as proc:
    >>>     proc.stderr | ~grep('ERROR') >> 'errors.log'
    >>>     for line in proc.stdout.text:
    >>>         print(line.upper())
    >>> # wait for proc to terminate


Path concatenation: /
---------------------

**path** ``/`` **str**

    Append the path segment on the right to the path on the left. The path segment
    can itself contain directories.

    >>> _ / 'docs'
    ./docs
    >>> _ / 'path/to/my/file.txt'
    ./path/to/my/file.txt


Path globing: * and **
-----------------------

**path** ``*`` **str**

    Performs a shell style globbing match against the directory entries under
    *path*.

    >>> _ * '*.jpg'
    ./*.jpg
    >>> _ * 'part-?.dat'
    ./part-?.dat

    .. seealso::
        for more details about the supported syntax see https://docs.python.org/3/library/glob.html


**path** ``**`` **str**

    Same as above but recursive by default. It will try to match the given
    glob all over the directory tree under *path*.

    >>> _ ** '.gitignore'
    ./**/.gitignore
    >>> _ ** '*.jpg'
    ./**/*.jpg


Path regex: //
--------------

**path** ``//`` (**str** | **pattern**)

    .. Caution::
        Try to use the globing operators when possible, matching by regexp is
        expensive unless the pattern is very well defined, since for non anchored
        cases like ``\.jpe?g$`` it has to traverse the whole directory tree.




.. _PEP-532: https://www.python.org/dev/peps/pep-0532/
.. _`Context Manager`: https://docs.python.org/3/reference/datamodel.html#context-managers