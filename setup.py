import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()


setuptools.setup(
    name="fastparser",
    version="0.1",
    author="Erik Meijer",
    author_email="erik@thewildweb.nl",
    description="A HTML Parser with some handy Utilities",
    long_description=long_description,
    url="https://github.com/Thewildweb/fastparser",
    packages=setuptools.find_packages(),
    classifiers={
        "Programming Language :: Python :: 3.8",
        "Development Status :: 3 - Alpha",
        "Operating System :: POSIX :: Linux",
    },
    python_requires=">=3.6",
)
