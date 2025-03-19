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
* Wed Mar 19 2025 Jordan Keough <jkeough@45drives.com> 1.3.4-1
- Re-adds Cloud providers Storj and iDriveE2 with Rclone update due to now self-hosting
  latest rclone version on our repos
* Wed Mar 19 2025 Jordan Keough <jkeough@45drives.com> 1.3.3-1
- Rolls back update with Storj and iDrive addition due to an issue with dependency
  upgrade for Rclone
* Tue Mar 18 2025 Jordan Keough <jkeough@45drives.com> 1.3.2-4
- fixes final? changelog issue from merge
* Tue Mar 18 2025 Jordan Keough <jkeough@45drives.com> 1.3.2-3
- fixes changelog issue from merge
* Tue Mar 18 2025 Jordan Keough <jkeough@45drives.com> 1.3.2-2
- fixes yarn lock issue
* Tue Mar 18 2025 Jordan Keough <jkeough@45drives.com> 1.3.2-1
- Adds Storj and iDrive e2 as cloud providers for Cloud Sync Tasks
* Thu Mar 06 2025 Jordan Keough <jkeough@45drives.com> 1.3.1-1
- Fixes an issue in replication script when checking remote snapshots
* Thu Mar 06 2025 Jordan Keough <jkeough@45drives.com> 1.3.0-1
- Introduces Cloud Sync Tasks, Custom Tasks, and adding Notes to tasks. Also adds
  Netcat as an alternative to SSH when using ZFS Replication, as well as numerous
  other QoL and UI updates.
* Thu Feb 27 2025 Jordan Keough <jkeough@45drives.com> 1.2.10-6
- update build
* Thu Feb 27 2025 Jordan Keough <jkeough@45drives.com> 1.2.10-5
- building
* Thu Feb 27 2025 Jordan Keough <jkeough@45drives.com> 1.2.10-4
- attempting to build
* Thu Feb 27 2025 Jordan Keough <jkeough@45drives.com> 1.2.10-3
- Re-running build, rpm built before but deb did not
* Thu Feb 27 2025 Jordan Keough <jkeough@45drives.com> 1.2.10-2
- Fixes netcat/ssh port issue
* Thu Feb 27 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-10
- now that slack servers are back up should be able to build without api call failing
  action
* Wed Feb 26 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-9
- building again with testing makefile changes
* Wed Feb 26 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-8
- building again
* Wed Feb 26 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-7
- Updates package to include zfsreptask destdataset fix
* Mon Feb 24 2025 Jordan Keough <jkeough@45drives.com> 1.2.10-1
- Fixes netcat issues found in service testing
* Thu Feb 13 2025 Jordan Keough <jkeough@45drives.com> 1.2.9-1
- Adds Ceph as an option in S3 rclone providers
* Wed Feb 12 2025 Jordan Keough <jkeough@45drives.com> 1.2.8-6
- Updating testing package to fix zfs replication issues
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