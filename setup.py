from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize

setup(
    name="Delatex",
    version="0.3.1",
    packages=find_packages(),
    ext_modules=cythonize('latex/*.py')
)
