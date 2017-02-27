import os, sys
try:
    from setuptools import setup, find_packages
except ImportError:
    print("cloudatcost_ansible_module needs setuptools in order to build. "
          "Install it using your package manager (usually python-setuptools) "
          "or via pip (pip install setuptools).")
    sys.exit(1)

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.adoc')) as f:
    long_desc = f.read()

setup(
    name="cloudatcost-ansible-module",
    version="0.2.1",
    author="Patrick Toal",
    author_email="sage905@takeflight.ca",
    description=("An Ansible module for managing servers at CloudAtCost  - "
                 "http://cloudatcost.com"),
    license="MIT",
    keywords="ansible module cloud at cost api",
    url="https://github.com/sage905/cloudatcost-ansible-module",
    download_url="https://github.com/sage905/cloudatcost-ansible-module/tarball/master",
    packages=find_packages(exclude=('tests',)),
    long_description=long_desc,
    scripts=['cac_inv.py'],
    classifiers=[
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 2.6",
        "License :: OSI Approved :: MIT License",
    ],
    install_requires=[
        'requests',
        'ansible',
        'cacpy',
        'setuptools',
        'requests'
    ],
    setup_requires=['pytest-runner'],
    tests_require=['pytest',],
)
