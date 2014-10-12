#!/usr/bin/env python

from setuptools import setup
from tidetool.__init__ import __version__ as VERSION

setup(name="tidetools",
    license = "Apache 2.0",
    version=VERSION,
    description="Process water level data and tides.",
    long_description=open("README.md", "r").read(),
    maintainer="Ben Smith",
    author="Ben Smith",
    author_email="perlcapt _at_ gmail.com",
    url="https://bitbucket.org/perlcapt/tidetools-2014",
    keywords="science ocean tide water marine",
    classifiers=[
        "Development Status :: 4 - Beta",
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Scientific/Engineering :: GIS',
    ],
    install_requires=["setuptools"],
    packages=['tidetools'],
    package_dir={'tidetools':'tidetools'},
    #entry_points={'console_scripts': ['tool = tidetools.file:main',]},
)
