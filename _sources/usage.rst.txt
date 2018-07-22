Usage
=====

.. code::

    pysh --help


.. tip:: Get quick information about any *pysh* symbol with ``pyenv -h <symbol>``


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


Transformations
---------------

Even if *pysh* tries to remain very close to Python, in order to make its
usage ergonomic, some source code transformations are needed before the code
is executed. For the most part this is transparent when using *pysh*, it's
performed under the hood automatically.

The transformation framework however is exposed at the library level and also
to the command line runner. The ``--transform`` option allows to load an arbitrary
*transformation module*, either from the set of standard ones or from a third
party. Multiple transformations are supported, just use additional options
and they'll be applied in the given order.

For instance, we can use the :mod:`pysh.transforms.autoimport` transformation,
which is only enabled for :ref:`Eval mode`, for an arbitrary script just by
using ``--transform autoimport``. That will make code in the script able to use
any module just by referencing its name.

Much more advanced transformations are possible and users are encouraged to
develop their own ones in order to experiment with new syntax and constructs.
There are no plans though to include them in the official *pysh* distribution,
the idea here is to allow free experimentation by the community and use the
best ones as inspiration for driving changes in future versions of *pysh*, not
necessarily as a transformation.

.. note:: Check :mod:`pysh.transforms` for technical details about the implementation.
