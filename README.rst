mbq.atomiq: database-backed queues
==================================

.. image:: https://img.shields.io/pypi/v/mbq.atomiq.svg
    :target: https://pypi.python.org/pypi/mbq.atomiq

.. image:: https://img.shields.io/pypi/l/mbq.atomiq.svg
    :target: https://pypi.python.org/pypi/mbq.atomiq

.. image:: https://img.shields.io/pypi/pyversions/mbq.atomiq.svg
    :target: https://pypi.python.org/pypi/mbq.atomiq

.. image:: https://img.shields.io/travis/managedbyq/mbq.atomiq/master.svg
    :target: https://travis-ci.org/managedbyq/mbq.atomiq

Installation
------------

.. code-block:: bash

    $ pip install mbq.atomiq


Getting started
---------------

1. Add `mbq.atomiq` to `INSTALLED_APPS` in your django application's settings

2. Add `ATOMIQ` specific settings to that same settings file. Those are used for metrics.

.. code-block:: python

    ATOMIQ = {
        'env': CURRENT_ENV,
        'service': YOUR_SERICE_NAME,
    }

3. Set up consumers for each queue type that your app needs. `mbq.atomiq` provides a handy management command for that:

.. code-block:: bash

    python -m manage atomic_run_consumer --queue sns

    python -m manage atomic_run_consumer --queue sqs

    python -m manage atomic_run_consumer --queue celery

Note that atomiq will use the celery task ``name`` attribute to import and call the task. By default, celery sets the task name to be the ``path.to.task.module.task_function_name``. Overriding the name of a task will cause atomiq to break, so plz don't do this.

To make sure we're not holding on to successfully executed or deleted tasks we also have a clean up management command, that by default will clean up all processed tasks that are older than 30 days. That default can be overriden.

.. code-block:: bash

    python -m manage atomic_cleanup_old_tasks

    or

    python -m manage atomic_cleanup_old_tasks --days N

    or

    python -m manage atomic_cleanup_old_tasks --minutes N

4. Use it!

.. code-block:: python

    import mbq.atomiq

    mbq.atomiq.sns_publish(topic_arn, message)

    mbq.atomiq.sqs_publish(queue_url, message)

    mbq.atomiq.celery_publish(celery_task, *task_args, **task_kwargs)

Monitoring
----------
<https://app.datadoghq.com/dash/895710/atomiq>


Testing
-------
Tests are automatically in ``Travis CI https://travis-ci.org/managedbyq/mbq.atomiq`` but you can also run tests locally using ``docker-compose``.
We now use `tox` for local testing across multiple python environments. Before this use ``pyenv`` to install the following python interpreters: cpython{2.7, 3.5, 3.6} and pypy3

.. code-block:: bash

    $ docker-compose up py36-pg|py36-mysql|py37-pg|py37-mysql

Testing in Other Services
-------------------------
When using atomiq in other services, we don't want to mock out atomiq's publish functions. This is because atomiq includes functionality to check that all usages are wrapped in a transaction, and can account for transactions added by Django in test cases. To allow you to test that the tasks you expect have been added the queue, we expose a `test_utils` module.


Shipping a New Release
----------------------
1. Bump the version in ``__version__.py``
2. Go to ``Releases`` in GitHub and "Draft a New Release"
3. After creating a new release, Travis CI will pick up the new release and ship it to PyPi
