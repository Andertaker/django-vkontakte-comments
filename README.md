Django Vkontakte Comments
======================

[![PyPI version](https://badge.fury.io/py/django-vkontakte-comments.png)](http://badge.fury.io/py/django-vkontakte-comments) [![Build Status](https://travis-ci.org/Andertaker/django-vkontakte-comments.png?branch=master)](https://travis-ci.org/Andertaker/django-vkontakte-comments) [![Coverage Status](https://coveralls.io/repos/Andertaker/django-vkontakte-comments/badge.png?branch=master)](https://coveralls.io/r/Andertaker/django-vkontakte-comments)

Установка
---------

    pip install django-vkontakte-comments

В `settings.py` необходимо добавить:

    INSTALLED_APPS = (
        ...
        'vkontakte_api',
        'vkontakte_users',
        'vkontakte_places',
        'vkontakte_comments',
    )
