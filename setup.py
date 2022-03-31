from setuptools import setup

from pndconf import __version__

description = """Pandoc configuration manager, file watcher and document generator.

Primarily meant for watching and converting markdown files to whatever pandoc can support."""

with open("README.org") as f:
    long_description = f.read()

setup(
    name="pndconf",
    version=__version__,
    description=description,
    long_description=long_description,
    url="https://github.com/akshaybadola/pndconf",
    author="Akshay Badola",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Education",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Topic :: Documentation",
        "Topic :: Internet",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: Content Management System",
        "Topic :: Text Processing :: Markup",
        "Topic :: Text Processing :: Markup :: HTML",
        "Topic :: Text Processing :: Markup :: Markdown",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Natural Language :: English",
    ],
    packages=["pndconf"],
    include_package_data=True,
    package_data={'': ['config_default.ini']},
    keywords='pandoc markdown watcher',
    python_requires=">=3.7, <=4.0",
    install_requires=[
        "watchdog>=2.1.5",
        "common-pyutil>=0.8.0",
        "chardet>=4.0.*",
        "pyyaml==5.4.*",
        "pandoc-eqnos==2.5.*",
        "bibtexparser>=1.2.0",
        "pandocfilters==1.5.*"],
    entry_points={
        'console_scripts': [
            'pndconf = pndconf.__main__:main',
        ],
    }
)
