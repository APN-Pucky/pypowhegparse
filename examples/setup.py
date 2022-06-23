import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements = [
    "smpl",
    "requests",
    "numpy",
    "pandas",
    "uncertainties",
    "tqdm",
    "scipy",
    "validators",
    "pytopdrawer",
]


setuptools.setup(
    name="pypowhegparse",
    setup_requires=['setuptools-git-versioning'],
    author="APN",
    author_email="APN-Pucky@no-reply.github.com",
    description="auto solve simple ctfs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/APN-Pucky/pypowhegparse",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    install_requires=requirements,
    version_config={
        "template": "{tag}",
        "dev_template": "{tag}.{ccount}",
        "dirty_template": "{tag}.{ccount}+dirty",
        "starting_version": "0.0.0",
        "version_callback": None,
        "version_file": None,
        "count_commits_from_version_file": False
    },
    scripts=['pypowhegparse/pypowhegparse'],
    python_requires='>=3.6',
)
