"""Optional accelerator; pure Python remains available without a C compiler."""
from setuptools import Extension, setup

setup(ext_modules=[Extension("quarkcompress._qcore_native",
                             sources=["native/qcore_native.c"], optional=True)])
