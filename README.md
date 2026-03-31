# cockpit-scheduler

`cockpit-scheduler` is a Cockpit module for creating, scheduling, and managing recurring server tasks from a web UI.

At a high level, the module lets operators automate:

- ZFS replication
- Automated ZFS snapshots
- Rsync jobs
- ZFS scrubs
- SMART self-tests
- Cloud Sync transfers with `rclone`
- Custom script or command execution

The Cockpit frontend stores task definitions, generates systemd services and timers, and uses backend scripts under `/opt/45drives/houston/scheduler/` to perform the actual work.

For end-user screens, task-by-task configuration details, scheduling behavior, retention rules, and Cloud Sync remote management, see the full [Task Scheduler User Guide](docs/Task_Scheduler_User_Guide.md).

## Repository Layout

- `scheduler/`
  Cockpit frontend application built with Vue/Vite.
- `houston-common/`
  Shared 45Drives UI/common code, included as a git submodule.
- `system_files/`
  Backend scripts, systemd templates, and packaged config assets that get installed onto the target system.
- `packaging/`
  RPM/DEB packaging assets used by the package pipeline.
- `docs/`
  User-facing documentation, including the full user guide.

## Supported Packaging Targets

The repository metadata currently defines package builds for:

- Ubuntu Focal
- Ubuntu Jammy
- Debian Bookworm
- Rocky Linux 8
- Rocky Linux 9

Those package targets are described in [manifest.json](manifest.json) and the distro packaging files under [packaging](packaging).

## Runtime Dependencies

The module expects these runtime dependencies on the target system:

- `cockpit`
- `python3`
- `rsync`
- `findutils`
- `smartmontools`
- `mbuffer`
- `rclone >= 1.59`
- `netcat`

Depending on which task types you actually use, you may also need:

- ZFS userspace tools for snapshot, scrub, and replication workflows
- SSH connectivity for remote replication or rsync jobs
- Valid cloud provider credentials or OAuth client information for Cloud Sync remotes

## Build Prerequisites

To build from source locally, you should have:

- `git`
- `make`
- `node` and `yarn`
- `jq`
- `moreutils` for `sponge`

Notes:

- The build expects the `houston-common` submodule to be present.
- `bootstrap.sh` creates a local Yarn configuration and sets Yarn to use `node-modules` linking.
- The repo root declares `yarn@4.7.0`, but `bootstrap.sh` refreshes the local Yarn setup during the first build.

## Building From Source

### 1. Clone the repository

Clone with submodules:

```bash
git clone --recurse-submodules https://github.com/45Drives/cockpit-scheduler.git
cd cockpit-scheduler
```

If you already cloned it without submodules:

```bash
git submodule update --init --recursive
```

### 2. Build the project

The recommended build entry point is:

```bash
make
```

What `make` does in this repository:

- bootstraps Yarn locally if `.yarnrc.yml` is missing
- initializes the `houston-common` submodule if needed
- builds the shared `houston-common` packages
- installs frontend dependencies for `scheduler/`
- builds the Cockpit plugin into `scheduler/dist/`

Useful build variants:

```bash
make DEBUG=1
make clean
make clean-all
```

Notes:

- `DEBUG=1` disables minification in the frontend build.
- `clean` removes built outputs.
- `clean-all` also removes generated Yarn state and `node_modules`.

## Installing From Source

There are three main install paths supported by the Makefile.

### System Install

Install into the live filesystem:

```bash
sudo make install
```

If you also want Cockpit restarted automatically:

```bash
sudo make install RESTART_COCKPIT=1
```

Without `RESTART_COCKPIT=1`, restart Cockpit manually after install:

```bash
sudo systemctl restart cockpit.socket
```

This install path places files into:

- `/usr/share/cockpit/scheduler/`
  Cockpit plugin assets
- `/opt/45drives/houston/scheduler/`
  backend task scripts and systemd template files
- `/etc/45drives/houston/scheduler/`
  scheduler-related config assets

### Local Test Install

Install the Cockpit frontend into your user-local Cockpit plugin directory with a `-test` suffix:

```bash
make install-local
```

Optional:

```bash
make install-local RESTART_COCKPIT=1
```

This installs the plugin frontend into:

- `~/.local/share/cockpit/scheduler-test/`

The Makefile also attempts a best-effort copy of `system_files/` into `/`, but those copy errors are intentionally ignored for local test installs.

In practice, that means:

- `make install-local` is ideal for frontend/UI testing
- task execution features may still depend on the backend files already existing under `/opt/45drives/houston/scheduler/` and `/etc/45drives/houston/scheduler/`
- on a clean machine, use `sudo make install` if you need the full stack installed

### Remote Test Install

Install to another machine over SSH for testing:

```bash
make install-remote REMOTE_TEST_HOST=server.example.com REMOTE_TEST_USER=root
```

Optional:

```bash
make install-remote REMOTE_TEST_HOST=server.example.com REMOTE_TEST_USER=root RESTART_COCKPIT=1
```

The remote test install copies:

- frontend assets to the remote user's `~/.local/share/cockpit/scheduler-test/`
- `system_files/` into the remote filesystem root

For the backend portion to land successfully on the remote host, the remote user must have permission to write those target paths.

### Staged Install Root

If you need to stage files into a build root instead of installing directly into `/`, use `DESTDIR`:

```bash
make DESTDIR=/tmp/cockpit-scheduler-root install
```

This is the same pattern used by the RPM/DEB packaging flow.

## Cloud Sync OAuth Note for Source Installs

This is the main difference between a direct source install and a packaged install.

Packaged installs generate:

- `/etc/45drives/houston/scheduler/cloud-sync-client-creds.json`

Source installs via `make install` copy only the template:

- `/etc/45drives/houston/scheduler/cloud-sync-client-creds-template.json`

The Cloud Sync remote scripts look for the real JSON file at:

- `/etc/45drives/houston/scheduler/cloud-sync-client-creds.json`

If that file is missing, the module still works, but packaged default OAuth `client_id` and `client_secret` values will not be auto-filled for supported providers. Users can still provide their own client credentials directly in the UI.

The template file looks like this:

```json
{
  "drive": {
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET"
  },
  "google cloud storage": {
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET"
  },
  "dropbox": {
    "client_id": "YOUR_DROPBOX_CLIENT_ID",
    "client_secret": "YOUR_DROPBOX_CLIENT_SECRET"
  }
}
```

If you want source installs to behave like packaged installs for built-in OAuth defaults, create `/etc/45drives/houston/scheduler/cloud-sync-client-creds.json` yourself and lock it down appropriately, for example:

```bash
sudo install -d -m 755 /etc/45drives/houston/scheduler
sudo cp /etc/45drives/houston/scheduler/cloud-sync-client-creds-template.json \
  /etc/45drives/houston/scheduler/cloud-sync-client-creds.json
sudo chmod 600 /etc/45drives/houston/scheduler/cloud-sync-client-creds.json
```

Then replace the placeholder values with the real credentials you want the module to use.

## Packaging

For a generic distributable archive containing built artifacts and installed system files:

```bash
make package-generic
```

That produces versioned `.zip` and `.tar.gz` archives from the current tree.

Distribution-specific packaging assets live under [packaging](packaging), and the spec/rules files show how CI performs staged installs and package assembly for supported operating systems.

## Development Notes

Helpful Make targets:

```bash
make
make install
make install-local
make install-remote REMOTE_TEST_HOST=server.example.com REMOTE_TEST_USER=root
make clean
make help
```

Important implementation detail:

- task execution scripts and timer/service templates are expected under `/opt/45drives/houston/scheduler/`
- the Cockpit UI is expected under `/usr/share/cockpit/scheduler/`

So if you install by some method other than the provided Makefile or package pipeline, keep those paths aligned with what the code expects.

## User Documentation

For operator-facing documentation and screenshots, see:

- [Task Scheduler User Guide](docs/Task_Scheduler_User_Guide.md)

That guide covers:

- the dashboard
- creating, editing, scheduling, and removing tasks
- detailed configuration for every task type
- Cloud Sync remotes, OAuth behavior, and troubleshooting
