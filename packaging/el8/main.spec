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
* Wed Feb 05 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-5
- removed scheduler test from makefile to try and rectify deb build issue
* Wed Feb 05 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-4
- Building testing package for Scheduler Phase 3 and 4
* Wed Feb 05 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-3
- Building testing package for Scheduler Phase 3 and 4
* Wed Feb 05 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-2
- Building testing package for Scheduler Phase 3 and 4
* Thu Jan 09 2025 Rachit Hans <rhans@45drives.com> 1.2.7-3
- building package
- release notes
- Added netcat functionality, notes functionality and fixed cutom task
* Thu Jan 09 2025 Rachit Hans <rhans@45drives.com> 1.2.7-2-1
- Building Package
* Mon Jan 06 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-1
- Creating testing package for Cloud-Sync addition
* Thu Jan 02 2025 Jordan Keough <jkeough@45drives.com> 1.2.7-1
- *FIXED VERSION NUMBER* Adds more robust error handling to ZFSRepTask parameters
  and updates EditTask logic to check for changes before saving.
* Thu Jan 02 2025 Jordan Keough <jkeough@45drives.com> 1.2.6-1
- Adds more robust error handling to ZFSRepTask parameters and updates EditTask logic
  to check for changes before saving.
* Fri Dec 20 2024 Rachit Hans <rhans@45drives.com> 1.2.6-1
- Added Custom Task
* Thu Dec 12 2024 Jordan Keough <jkeough@45drives.com> 1.2.5-1
- Fixes issue with task searching/sorting
* Wed Dec 11 2024 Rachit Hans <rhans@45drives.com> 1.2.4-1
- Fixed auto-snapshot recursive bug
* Wed Nov 27 2024 Jordan Keough <jkeough@45drives.com> 1.2.3-1
- Introduces time-based snapshot retention policies
* Mon Nov 04 2024 Jordan Keough <jkeough@45drives.com> 1.2.2-1
- Stable Release
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