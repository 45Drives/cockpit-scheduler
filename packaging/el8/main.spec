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
* Tue Aug 06 2024 Jordan Keough <jkeough@45drives.com> 1.2.1-1
- Improves task creation + execution modifications to exclusively use env file data
  without placeholders + removes reliance of old task template files (removed)
* Mon Aug 05 2024 Jordan Keough <jkeough@45drives.com> 1.2.0-3
- Fixing issue with edit task data not storing
* Mon Aug 05 2024 Jordan Keough <jkeough@45drives.com> 1.2.0-2
- Adds mbuffer as a dependency
* Mon Aug 05 2024 Jordan Keough <jkeough@45drives.com> 1.2.0-1
- Major update, may require tasks to be destroyed + remade. Changes how task files
  are generated + read by system. Fixes major bug with SSH data not saving properly
  for ZFS Replication Tasks, also lays groundwork for CloudSync authentication to
  come in next update. Numerous other QoL updates and small bugfixes.
- Updating version - Fixing bug where SSH data was not storing properly for ZFSReplication
  (Creating/Editing Tasks)
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