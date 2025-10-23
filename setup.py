"""Setup script for scope_doc_gen package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="scope_doc_gen",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="AI-powered technical scope document generator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/scope_doc_gen",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Documentation",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "scope-gen=scope_doc_gen.main:main",
        ],
    },
)

