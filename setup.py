"""
Setup script for FadCat - Advanced Android logcat viewer
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="fadcat",
    version="1.0.0",
    description="Advanced Android logcat viewer with fuzzy search and real-time highlighting",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="FadSecLab",
    url="https://github.com/anonfaded/FadCat",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "PyQt6>=6.9.0",
        "rapidfuzz>=3.9.0",
        "colorama>=0.4.6",
    ],
    include_package_data=True,
    package_data={
        "src": [
            "icons/*.png",
            "icons/*.svg",
        ],
    },
    entry_points={
        "console_scripts": [
            "fadcat=fadcat_cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Debuggers",
    ],
)
