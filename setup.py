from setuptools import setup, find_packages

setup(
    name='log-retrieval-server',
    version='0.1.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[],
    entry_points={
        'console_scripts': [
            'log-retrieval-server=log_retrieval_server:main',
        ],
    },
    author='Rachel Teeter',
    description='Minimal log retrieval server for Unix systems',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
)
