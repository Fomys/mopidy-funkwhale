#!/usr/bin/env python
# -*- coding: utf-8 -*-
import codecs
import os
from setuptools import setup

def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()

def get_version():
    tag = os.getenv('CI_COMMIT_TAG', None)
    if tag:
        return tag

    for line in read("mopidy_funkwhale/__init__.py").splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            version = line.split(delim)[1]
            iid = os.getenv('CI_PIPELINE_IID', 0)
            return "{}.dev{}".format(version, iid)
    raise RuntimeError("Unable to find version string.")

setup(
    version=get_version(),
)
