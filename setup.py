from setuptools import setup, find_packages

setup(
    name='django-vkontakte-comments',
    version=__import__('vkontakte_comments').__version__,
    description='Django implementation for vkontakte API comments',
    long_description=open('README.md').read(),
    author='krupin.dv',
    author_email='krupin.dv19@gmail.com',
    url='https://github.com/Andertaker/django-vkontakte-comments',
    download_url='http://pypi.python.org/pypi/django-vkontakte-comments',
    license='BSD',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,  # because we're including media that Django needs
    install_requires=[
        'django-vkontakte-api>=0.7.4',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
