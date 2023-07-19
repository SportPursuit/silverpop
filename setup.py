import os
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='silverpop',
    version='1.0.4',
    description='Silverpop API wrapper.',
    author='Thomas Welfley',
    author_email='thomas@yola.com',
    url='https://github.com/yola/silverpop',
    packages=['silverpop', ],
    install_requires=[
        'requests>=2.11.1',
        # 'elementtree==1.2.7-20070827-preview',
        # 'testify==0.1.12',
    ],
    license='GPL',
)
