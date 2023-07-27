from setuptools import setup, find_packages

setup(
    name="movement_primitives",
    package_dir={'': 'src'},
    packages=find_packages(
        'src', include=('src/',), exclude=('tests',)),
)