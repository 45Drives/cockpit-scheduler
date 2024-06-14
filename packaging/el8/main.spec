Name: ::package_name::
Version: ::package_version::
Release: ::package_build_version::%{?dist}
Summary: ::package_description_short::
License: ::package_licence::
URL: ::package_url::
Source0: %{name}-%{version}.tar.gz
BuildArch: ::package_architecture_el::
Requires: ::package_dependencies_el_el8::

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root

%description
::package_title::
::package_description_long::

%prep
%setup -q

%build
make OS_PACKAGE_RELEASE=el8

%install
make DESTDIR=%{buildroot} install

%files
/usr/share/cockpit/scheduler/*
/opt/45drives/houston/scheduler/*

%changelog
* Fri Jun 14 2024 Jordan Keough <jkeough@45drives.com> 1.1.0-1
- Updating Release Version
* Fri Jun 14 2024 Jordan Keough <jkeough@45drives.com> 1.0.3-1
- Adds Rsync, Scrub & SMART Test Tasks Support + General UX/UI improvements
* Tue May 21 2024 Jordan Keough <jkeough@45drives.com> 1.0.2-1
- Building package
* Tue May 21 2024 Jordan Keough <jkeough@45drives.com> 1.0.1-1-2
- Updates to scripts & UI + packaging for focal
* Tue May 21 2024 Jordan Keough <jkeough@45drives.com> 1.0.1-2
- Updates to scripts & UI + packaging for focal
* Fri May 17 2024 Jordan Keough <jkeough@45drives.com> 1.0.0-1
- Build packaging