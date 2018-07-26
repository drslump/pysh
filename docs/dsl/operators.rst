Operators
=========

The *pysh domain specific language* overloads a few Python operators to
better suit the syntax for shell scripting, where constructing *command pipelines*
and *paths* is a common operation. Additionally some operators have their binding
precedence changed to behave more closely to a shell language, which is crucial
when chaining commands in a pipeline. Here is a table with the operator binding
precedence from **lower to higher**:

=========================   =====================================================
        operator                         notes
=========================   =====================================================
                    ``|``

        ``^`` ``<`` ``>``   ``<`` and ``>`` modified to match Python's ``^``
                            (see :mod:`pysh.transforms.precedence`)
            ``>>`` ``<<``

      ``/`` ``//`` ``**``   ``**`` modified to match Python's ``//``
                            (see :mod:`pysh.transforms.pathpow`)

                    ``~``
=========================   =====================================================


Pipe: |
-------

**pipeline** ``|`` **command**

    The typical shell piping operation where the output of the last command
    on the left is feed as input for the command on the right.

    >>> head['-10'] | grep('foo')
    head['-10'].pipe( stdout = grep('foo') )

    .. admonition:: meanwhile in Bash

        just as above sans the braces: ``head -10 | grep foo``

**pipeline** ``|`` **callable**

    When the right operand is a callable then it acts as a *reverse application
    operator*, where the right operand receives the *stdout stream* of the last
    command on the pipeline as argument.

    >>> head['-10'] | ','.join
    ','.join( line for line in head['-10'] )

**value** ``|`` **pipeline**

    An arbitrary value as left operand is automatically wrapped in an iterator
    so it can be feed to the *stdin* of the *first command* on the pipeline.

    >>> __doc__ | wc['-l']
    echo(__doc__).pipe( stdout = wc['-l'] )
    >> range(10) | wc['-l']
    seq 0 9 | wc['-l]

    .. admonition:: meanwhile in Bash

        this is commonly ``echo "$variable" | command``.


Piperr: ^ 🚧
------------

🚧 **pipeline** ``^`` (**stream** | **path** | **str**) 🚧

    Redirect *stderr* from the *last command* in the pipeline to a stream or
    a file.

    >>> gcc ^ null
    discard stderr output

    >>> gcc ^ stdout | wc['-l']
    merge stderr into stdout and count all the lines from both

    >>> gcc ^ errors.txt | wc['-l']
    store stderr in a file and count the lines on stdout

    .. admonition:: meanwhile in Bash

        quite similar, the ``^`` is ``2>``. An example: ``gcc 2>errors.txt | wc -l``

🚧 **pipeline** ``^`` **pipeline** 🚧

    Pipe *stderr* from the *last command* in the pipeline on the left to *stdin*
    of the *first command* from the pipeline on the right.

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


.. Caution::
    In *pysh* scripts the ``>`` and ``<`` operators have their binding
    precedence modified to match that of the ``^`` operator, higher than
    ``|`` instead of lower. This change is required to ensure proper
    ergonomics when building pipelines. Check :mod:`pysh.transforms.precedence`
    for more details.


**pipeline** ``>`` (**stream** | **path** | **str**)

    Like in a standard shell the redirection places the output from the last
    *command* in the pipeline on the left to a file referenced on the right,
    creating the file if necessary.

    >>> cat > stderr
    # the output of cat gets redirected to stderr
    >>> cat | head > 'first.txt'
    # only the first lines from cat will be written in the file

    Alternatively you can use its reverse operator ``<`` to make the expression
    more readable.

    >>> 'status.txt' < sh.git['status']
    # get the git status and save it in a file

    Note that the operator precedence is higher than ``|``, meaning that when
    redirecting a pipe expression its the output of the closest *command* what gets
    redirected. In practice this is only an issue when using its *reverse version*
    ``<`` but parenthesis can be used to force a different interpretation.

    >>> 'first-lines.txt' < cat | head
    # redirects cat to a file, nothing is left to pipe into head
    >>> 'first-lines.txt' < (cat | head)
    # now it's the ouput of the whole pipeline what gets redirected to the file


    .. admonition:: meanwhile in Bash

        exactly the same... ``cat | head > 'first-lines.txt'``


(**stream** | **path** | **str**) ``>`` **pipeline**

    When the target is a *pipeline* then the file referenced on the left operand
    is read and provided to the *stdin* of the pipeline's *first command*.

    >>> fname > head
    # get first lines from the file referenced in fname


**pipeline** ``>`` **callable**

    An interesting use case for the redirection operator is to set a *callable*
    as its target. In this scenario the whole output of the pipeline will be
    *buffered* and then passed as an argument to the target function.

    >>> echo("hello") > len
    6  # len(b"hello\n")

**pipeline** ``>>`` (**path** | **str**)

    Works exactly like the redirection operator ``>`` but if the target file
    exists it will append the contents at the end of it instead of replacing
    the previous data.

    >>> cat | head >> 'historic-data.txt'
    # Appends the new conetnts to the target file

    Its *reverse operator* is ``<<`` although it might be best to avoid its
    use as to not create confusion with the *application operator* explained
    below.

    .. admonition:: meanwhile in Bash

        again exactly the same... ``cat | head >> 'historic-data.txt'``

**command** ``<<`` **any**

**callable** ``<<`` **pipeline** 🚧

    Acts as an *application operator*, the operand on the left will be called
    with the one on the right as argument. It results in the same operation as
    a *call* ``left(right)``, the advantge is that it avoids the wrapping
    parenthesis of a call so it reduces syntax noise for some use cases.

    >>> echo['Seconds in a day:'] << 60 * 60 * 24
    evaluates as: echo['Seconds in a day:'](86400)

    .. admonition:: meanwhile in Bash

        *sh* syntax really shines here for common cases, the whitespace acts as
        its *application operator*. For more complex uses however it requires
        interpolation, which would be similar to a normal *call* with parenthesis,
        reproducing the example above: ``echo 'Seconds in a day' "$((60*60*24))"``.


Reckless: ~
-----------

``~`` **pipeline**

    Ignores the *exit status* and *stderr* of the pipeline. Normally a non 0
    exit status would raise an exception that needs to be handled by the script,
    however some times we expect a command to fail under some conditions.

    This is particulary useful since, unlike *sh*, we do raise errors if they
    happen on a pipeline. For instance, ``grep`` exits with 1 if it couldn't
    match anything.

    >>> cat(fname) | ~grep['foo'] | wc['-l']
    we don't really care if it could match something or not


.. admonition:: meanwhile in Bash

    assuming Bash is running with ``-o pipefail``, this can be accomplished
    with a conditional and a subshell:
    ``cat fname | (grep foo 2>/dev/null || true) | wc -l``


Boolean operators
-----------------

.. Warning::

    In Python is not possible to overload the boolean operators (``not``,
    ``and``, ``or``) since they have short-circuiting semantics (PEP-532_
    is deferred right now).

The problem manifests when trying to use the ``cmd and ok_expr or fail_expr``
and similar constructs which are quite common in shell scripts. We would
like to keep that expression lazily evaluated but is not possible since
the Python interpreter will try to resolve it immediately, triggering the
evaluation of ``cmd` to know if it should go to the ``and`` or the ``or``
branch.

Some times it would work as expected, that is, when the expression is its
own statement even if the command was lazily evaluated it would happen at
that point anyway. However this could become very confusing when storing
the command in a variable for later invocation or trying to use it with a
*parallelization utility* since it breaks the *lazy semantics*.

.. Note::
    There is an experimental transformation in :mod:`pysh.transforms.alpha.lazybools`
    which implements the basis for making lazy *boolean operators*, however
    it's a complex modification of how Python normally works and as such it's
    disabled and not ready for general use until it can prove its utility.


Context Manager: with 🚧
------------------------

.. Warning:: 🚧 Validate this will work as intended

``with`` **pipeline** ``as`` **name**: 🚧

    Pipelines implement the `Context Manager`_ protocol, upon entering one the
    pipeline is invoked and a :class:`pysh.command.Result` instance is provided.
    Unlike normal invocation the standard streams are not wired to the script
    ones, allowing to consume them imperatively inside the block.

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


.. TODO:: Move this section out, not really an operator?


Path operators
--------------

Path concatenation: /
~~~~~~~~~~~~~~~~~~~~~

**path** ``/`` **str**

    Append the path referenced on the right to the path on the left. The
    referenced path can itself contain directories, if so all of its segments
    will be appended.

    >>> _ / 'docs'
    ./docs
    >>> _ / 'path/to/my/file.txt'
    ./path/to/my/file.txt


Path matching: //
~~~~~~~~~~~~~~~~~

**path** ``//`` **str**

    Performs a *shell style globbing* match against the directory entries under
    *path*.

    >>> _ // '*.jpg'
    ./*.jpg
    >>> _ // 'part-?.dat'
    ./part-?.dat

    Additionally to *globbing* it also supports *brace expansion*, for each
    expansion a globbing operation will be executed and their results merged
    without duplicates.

    >>> _ // '{foo,bar}-*.jpg'
        set(foo-*.jpg) + set(bar-*.jpg)

    Escaping for globbing or brace expansion special characters ``*?[{,`` is done
    performed with a backslash ``\``. Escapes for non special characters are
    handled too.

    >>> _ // r'foo-\*?.jpg'
      # matches jpg files named as "foo-*" followed by any char
    >>> _ // r'\f\o\o\*\.\j\p\g'
      # matches the file "foo*.jpg"
    >>> _ // 'foo-[*].jpg'
      # uses glob syntax to perform a escape, it'll match "foo-*.jpg"


    .. Note::
        unless a *glob* starts with a ``.`` prefix, those files are considered
        hidden and won't be matched by the expression. Also *globs* can include
        ``/`` characters to signal directories. It's perfectly valid to have
        something like ``_ // 'path/prefix-*/dir/*.txt'``.

        For more details about the supported *glob* syntax see Python's documentation
        for the `glob module`_, for details about *brace expansion* check this
        `article from Linux Journal`_.

    .. Caution::
        unlike globbing in an *sh* shell the output is not sorted alphabetically.


.. _`glob module`: https://docs.python.org/3/library/glob.html
.. _`article from Linux Journal`: https://www.linuxjournal.com/content/bash-brace-expansion

**path** ``//`` **pattern**

    Tries to match the given *regex pattern* against entries from *path*.
    The **matching is anchored**, meaning that a *pattern* only succeeds if it
    can match the whole entry name.

    >>> _ // re.compile('\w+-\d{1,3}\.jpg')
        echo * | grep '^\w\+-\d\d\?\d\?\.jpg$'    # roughly equivalent

    .. Caution::
        unlike *globs*, *patterns* cannot expand multiple directories, the match
        is performed only against the current path segment.

    .. Note::
        entries starting with ``.`` will be matched except for the navigation
        ones: ``.`` and ``..``.


**path** ``//`` **callable**

    For each directory entry in *path* it'll provide a *Path* instance to
    *callable* and collect those for which it returns a truthy value.

    >>> _ // Path.is_file
        find . -maxdepth 1 -type f
    >>> _ // lambda p: p.name.isalpha
        echo * | grep '^\w\+$'      # roughly equivalent

    .. Note::
        Entries starting with ``.`` will be processed except for the navigation
        ones: ``.`` and ``..``.


Path traversal: ``**``
~~~~~~~~~~~~~~~~~~~~~~

.. Caution::
    In *pysh* scripts the ``**`` operator has its binding precedence modified
    to match that of the arithmetic operators, thus lower than normal Python
    code. This change is required to ensure proper ergonomics when building
    paths. Check :mod:`pysh.transforms.pathpow` for more details.


**path** ``**`` (**str** | **pattern** | **callable**)

    Similar to ``//`` except that it will try the match *recursively* over the
    directory tree under *path*.

    >>> _ ** '.gitignore'
    ./**/.gitignore
    >>> _ ** '*.jpg'
    ./**/*.jpg
    >>> _ ** re'\w+'
    echo ./**/* | grep '/\w\+$'
    >>> _ ** Path.is_file
    find . -type f



String literals
---------------

While not operators per se, there are two custom *string literals* introduced
by *pysh* which are enabled by default when running scripts.

``_'...'``

    Gets expanded into *path slicing syntax* with a *raw string literal*. See
    :mod:`pysh.transforms.pathstring` for additional details.

    >>> _'images/log.jpg'
      # _[r'images/logo.jpg']
    >>> _'c:\windows'
      # _[r'c:\windows']


``re'...'``

    Generates a *compiled regex pattern* for a *raw string literal* with the
    *verbose* flag set. Check :mod:`pysh.transforms.restring` for details.

    >>> re'\w+'
      # re.compile(r'\w+', re.VERBOSE)


.. Note::
    while these custom *string literals* might be useful when writing a quick
    script, there is no guarantee on how they'll behave on different code editors.
    If the script is to be distributed or maintained by other people a good
    etiquette would be to avoid its use.

.. Hint::
    transformations can be disabled by prefixing a ``-`` to their name when running
    a script: ``pysh -t -pathstring -t -restring ...``.


.. _PEP-532: https://www.python.org/dev/peps/pep-0532/
.. _`Context Manager`: https://docs.python.org/3/reference/datamodel.html#context-managers
