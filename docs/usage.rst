Usage
=====

.. code::

    pysh --help


Eval mode
---------

.. code::

    pysh -e <expr>

This mode is useful for one liners, mainly to use on interactive shells. It's
similar to ``python -c`` but with the following twists:

- ``NameError`` will try to automatically import a package before failing.
- last expression is automatically printed to stdout unless it's ``None``.
- when last expression is a boolean True exits with 0 and False with 1.

Given that names are automatically imported it becomes trivial to use Python's
libraries from the shell:

.. code-block:: sh

    # automatically access some library function
    random=$(pysh -e 'random.randint(10, 50)')
    echo "Please do $random push ups"

    # consume from stdin
    seq 10 | pysh -e 'sum(int(x) for x in sys.stdin)'

.. TODO::
    Allow arguments and environment variables interpolation in the code snippet.

