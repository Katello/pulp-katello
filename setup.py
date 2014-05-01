#!/usr/bin/python
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

from setuptools import setup, find_packages

setup(
    name='pulp-katello-plugins',
    version='0.2',
    license='GPLv2+',
    packages=find_packages(),
    author='Katello Team',
    author_email='katello-devel@redhat.com',
    entry_points = {
        'pulp.distributors': [
            'distributor = pulp_katello.distributors.yum_clone_distributor.distributor:entry_point',
        ],
    }
)
