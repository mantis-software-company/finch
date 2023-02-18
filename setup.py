import setuptools

setuptools.setup(
    name="finch",
    version="1.0.0a1",
    description="Open source and cross-platform GUI client for Amazon S3 and compatible storage platforms",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/mantis-software-company/finch",
    author="Furkan Kalkan",
    author_email="furkankalkan@mantis.com.tr",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Topic :: Internet",
        "Topic :: Software Development",
        "Topic :: Utilities",
        "Intended Audience :: Developers",
        "Operating System :: MacOS",
        "Operating System :: POSIX",
        "Operating System :: Microsoft",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8"
    ],
    python_requires=">3.8.*, <4",
    packages=["finch"],
    include_package_data=True,
    install_requires=[
        "PyQt5==5.15.9", "boto3==1.26.68", "keyring==23.13.1", "python-slugify==8.0.0"
    ],
    entry_points={"console_scripts": ["finch=finch.__main__:main"]},
)
