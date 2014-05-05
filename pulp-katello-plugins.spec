# Copyright (c) 2013 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0


%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python_sitearch: %global python_sitearch %(%{__python} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}


Name: pulp-katello-plugins 
Version: 0.2
Release: 1%{?dist}
Summary: Plugins useful for katello interactions with pulp  
Group: Development/Languages
License: GPLv2
URL: https://fedorahosted.org/katello/
Source0: https://fedorahosted.org/releases/p/u/%{name}/%{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
BuildRequires:  python2-devel
BuildRequires:  python-setuptools
BuildRequires:  python-nose
BuildRequires:  rpm-python

Requires: python-pulp-rpm-common
Requires: pulp-server


%description
Provides a collection of platform plugins, client extensions and agent
handlers that provide RPM support.

%prep
%setup -q

%build
%{__python} setup.py build


%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build --root %{buildroot}

#remove file needed for setup.py
#rm -rf %{buildroot}/%{_usr}/lib/pulp/plugins/distributors/__init__.py*

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{python_sitelib}/pulp_katello/
%{python_sitelib}/pulp_katello_plugins*.egg-info
%doc LICENSE
%doc README.md


%changelog
* Mon Jul 22 2013 Justin Sherrill <jsherril@redhat.com> 0.2-1
- fixing rpm spec requires to not depend on specific pulp version
  (jsherril@redhat.com)

* Mon Jul 22 2013 Justin Sherrill <jsherril@redhat.com> 0.1-0.1
- new package built with tito
