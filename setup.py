"""Setup MARBLE."""
import numpy
from Cython.Build import cythonize
from setuptools import Extension
from setuptools import find_packages
from setuptools import setup

setup(
    name="MARBLE",
    version="1.0",
    author="Adam Gosztolai",
    author_email="adam.gosztolai@epfl.ch",
    description="""Package for the data-driven representation of non-linear dynamics
    over manifolds based on a statistical distribution of local phase portrait features.
    Includes specific example on dynamical systems, synthetic- and real neural datasets.""",
    long_description=open("README.md", "r").read(),
    long_description_content_type="text/markdown",
    install_requires=[
        "teaspoon==1.3.1",
        "matplotlib",
        "pandas",
        "numpy",
        "scipy",
        "matplotlib",
        "networkx",
        "seaborn",
        "torch",
        "pympl",
        "tensorboardX",
        "pyyaml",
        "POT",
        "pyEDM",
        "teaspoon",
        "umap-learn",
        "mat73",
        "wget",
    ],
    packages=find_packages(),
    include_package_data=True,
    package_data={"MARBLE.lib": ["ptu_dijkstra_marble.pyx", "ptu_dijkstra_marble.c"]},
    ext_modules=cythonize(
        Extension(
            "ptu_dijkstra_marble", ["MARBLE/lib/ptu_dijkstra_marble.pyx"], include_dirs=[numpy.get_include()]
        )
    ),
)
