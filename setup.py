from setuptools import setup, find_packages
import os 


with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

with open(os.path.realpath('./VERSION')) as f:
    version = f.readline()

setup(
    name = 'easydi',         
    packages = ['easydi'],   
    version = version,      
    license='gpl-2.0',        
    description = 'Lazy dependency injection',   
    author = 'Wiryono Lauw',                   
    author_email = 'wiryonolau@gmail.com',      
    url = 'https://github.com/wiryonolau/python-easydi',  
    install_requires=install_requires,
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
