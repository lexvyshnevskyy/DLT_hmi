from setuptools import setup, find_packages
from glob import glob

package_name = 'hmi'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=[
        'setuptools',
        'psutil>=6.1.1',
        'pyserial>=3.5',
    ],
    zip_safe=False,
    maintainer='Oleksii Vyshnevskyi',
    maintainer_email='lex.vyshnevskyy@gmail.com',
    description='ROS 2 HMI serial bridge migrated from ROS 1.',
    license='Proprietary',
    entry_points={
        'console_scripts': [
            'run = hmi_rs232.run:main',
        ],
    },
)
