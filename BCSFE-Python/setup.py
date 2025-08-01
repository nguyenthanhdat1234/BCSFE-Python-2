"""Setup for installing the package."""

import setuptools
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Handle version file safely
version = "1.0.0"  # Default version
version_file = "src/BCSFE_Python/files/version.txt"
if os.path.exists(version_file):
    with open(version_file, "r", encoding="utf-8") as fh:
        version = fh.read().strip()

setuptools.setup(
    name="battle-cats-save-editor",
    version=version,
    author="fieryhenry",
    description="A battle cats save file editor",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/fieryhenry/BCSFE-Python",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "colored==1.4.4",
        # "tk",  # Removed - tkinter is built-in
        "python-dateutil",
        "requests",
        "pyyaml",
    ],
    include_package_data=True,
    extras_require={
        "testing": [
            "pytest",
            "pytest-cov",
        ],
    },
    package_data={
        "BCSFE_Python": [
            "py.typed",
            "files/*",  # Include all files in the files directory
            "files/**/*",  # Include subdirectories
        ]
    },
)