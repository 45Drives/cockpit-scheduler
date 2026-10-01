# Migrating Dataset Replication Tasks to One Recursive Task

## Purpose

Use this guide when a customer has separate snapshot/replication tasks for many datasets and wants one recursive task covering the pool's dataset hierarchy.

The goal is to reuse the data already replicated, rather than send every dataset in full again. This is a manual migration using the Cockpit UI for task management and CLI for establishing the common snapshot baseline. It is not currently an automatic scheduler operation.

This guide is a procedure and command-template reference, not an unattended script. Service must verify the customer's actual paths, destination layout, OpenZFS versions, encryption settings, and snapshot history before transferring anything. Run commands with the required ZFS privileges on the indicated server.

## How It Works

Existing snapshots cannot be merged into one snapshot. Instead, create a new recursive snapshot on the source and transfer each dataset to that snapshot using its own existing incremental baseline.

The starting snapshot can differ for every dataset. The finishing snapshot suffix must be the same across the selected root and descendants.

| Dataset | Starting point | Finishing point |
| --- | --- | --- |
| First dataset | Its own latest usable shared snapshot | Its new migration snapshot |
| Second dataset | Its own latest usable shared snapshot | Its new migration snapshot |
| Remaining datasets | Their respective usable shared snapshots | Their new migration snapshots |
| Root and intermediate parents | Shared baseline, or separately approved full seed | Their new migration snapshots |

Once the root and all included datasets have the matching migration snapshots on both servers, the new recursive task can use that baseline for subsequent incremental replication.

Matching names alone are insufficient. Each source snapshot and its corresponding received destination snapshot must have the same GUID. Independently creating a snapshot with the same name on the destination does not create a shared baseline.

Datasets without a usable shared baseline may still need full transfers. Recursive dataset replication does not copy the pool's vdev topology or replace destination pool configuration.

## Before Starting

Confirm the migration includes exactly the intended datasets. Selecting a pool root recursively also includes descendants that may not have been covered by the old tasks.

Record the source-to-destination mapping and the latest usable shared snapshot for every dataset, including intermediate parent datasets and the root. The relative hierarchy beneath the proposed source and destination roots must match. Flattened destinations or independently renamed datasets need a separate layout plan.

Keep a recoverable backup and record existing task settings, snapshot inventories, and destination-only data. Review free space, clones and their origins, pending receives, and encryption compatibility. Clones or mixed raw/non-raw replication histories require specialist review before using these templates.

Do not enable Force full resync or destination overwrite/rollback permission to get past a migration error. A forced recursive receive can destroy destination-only snapshots and datasets.

## Step 1: Finish and Pause the Existing Tasks (UI)

Let active replication transfers finish, then disable the schedules for the old dataset replication tasks. Disable related snapshot/pruning tasks and any external automation that could remove the required snapshots or change the backup during migration.

Keep the task definitions and their snapshots. Disabling tasks is not the same as deleting them. Prevent writes to destination backup datasets throughout the migration.

Source applications can continue writing after the migration snapshot is taken; those later changes will be transferred by subsequent replication. If application-consistent backups are required, coordinate quiescing applications while taking the migration snapshot. Avoid dataset creation, deletion, and renaming until the handover is complete.

## Step 2: Inventory Snapshots and Check the Root (CLI)

On each server, set `ROOT` to that server's actual replication root, then list snapshots:

```bash
zfs list -H -p -t snapshot -o name,guid,creation -s creation -r "${ROOT:?Set ROOT to the actual replication root}"
```

Compare corresponding datasets using GUIDs. Normally, the selected shared baseline should be the destination dataset's latest snapshot, and the destination should not have been modified since it. Newer destination snapshots or writes must be investigated rather than automatically rolled back.

The root needs a replicated baseline too. If the old tasks replicated only children, the root may never have been replicated. The same applies to intermediate parent datasets created independently on the backup.

If a root or parent has no shared baseline, it may need a separate **nonrecursive full send of its own contents**, not of its descendants. However, receiving this into an existing populated parent or a destination pool root is not a generic safe operation. Service must approve a layout-specific method before continuing. Do not destroy the parent, overwrite the pool root, or assume a locally created destination snapshot will substitute for a received snapshot.

Protect the chosen source and destination baseline snapshots from pruning. Temporary ZFS holds can protect snapshots, but must be recorded for later release. For a reviewed individual baseline on the server holding it:

```bash
zfs hold service-replication-migration "${BASE_SNAPSHOT:?Set BASE_SNAPSHOT to the reviewed baseline snapshot}"
```

## Step 3: Create the Common Migration Snapshot (CLI, Source)

Set `SRC_ROOT` to the approved source root and `MIGRATION` to a unique snapshot suffix that does not already exist anywhere in the selected hierarchy. Then create and protect the recursive snapshot:

```bash
zfs snapshot -r "${SRC_ROOT:?Set SRC_ROOT}@${MIGRATION:?Set a unique migration suffix}"
zfs hold -r service-replication-migration "${SRC_ROOT}@${MIGRATION}"
```

This creates a new snapshot with the same suffix on the root and each descendant. It does not merge or rename the previous snapshots. This is an ordinary recursive snapshot, not a `zpool checkpoint`.

## Step 4: Transfer Each Dataset to the Migration Snapshot (CLI)

Use the reviewed mapping table to process each dataset. Record success or failure per dataset; do not assume all transfers succeeded because the last command succeeded. For hundreds of datasets, any automation should use the verified mapping table, stop on failures, and be reviewed before execution.

For each transfer, the following variables must contain the customer's actual values:

| Variable | Meaning |
| --- | --- |
| `SRC_DATASET` | The exact source dataset for this individual transfer |
| `DST_DATASET` | Its exact mapped destination dataset |
| `BASE_SNAPSHOT` | The full source snapshot name whose GUID matches the destination baseline |
| `MIGRATION` | The common migration snapshot suffix from Step 3 |
| `BACKUP_SSH` | The actual SSH destination accepted by `ssh`, including the user if needed |

First estimate the individual incremental send on the source:

```bash
zfs send -nPv -i "${BASE_SNAPSHOT:?Set BASE_SNAPSHOT}" "${SRC_DATASET:?Set SRC_DATASET}@${MIGRATION:?Set MIGRATION}"
```

For **unencrypted datasets**, the basic remote transfer pattern, run on the source, is:

```bash
set -o pipefail
zfs send -i "${BASE_SNAPSHOT:?Set BASE_SNAPSHOT}" "${SRC_DATASET:?Set SRC_DATASET}@${MIGRATION:?Set MIGRATION}" |
  ssh "${BACKUP_SSH:?Set BACKUP_SSH}" zfs receive -u "${DST_DATASET:?Set DST_DATASET}"
```

The `-u` option prevents the received filesystem from being mounted by the receive operation. It does not permit overwriting conflicting destination data. Supply the customer's established SSH options if a nondefault port or identity is required.

These commands intentionally send one dataset at a time, without `-R`, and do not force rollback. For encrypted datasets, use the reviewed send flags consistent with the existing replication history; for an established raw chain, that normally includes `-w`. Do not change encryption strategy during this migration.

Repeat for the children, intermediate parents, and root using their approved transfer methods. A dataset with no usable baseline requires a separately approved full seed; the incremental template does not apply to it.

If a receive fails, stop and investigate that dataset. Do not add `-F`, delete snapshots, or continue to the new recursive task with an incomplete hierarchy.

The existing UI tasks cannot perform this step simply by clicking Run Now: normal runs create and send fresh task-specific snapshots, rather than the exact shared migration snapshots.

## Step 5: Verify the Entire Baseline (CLI)

Repeat the snapshot inventories on both servers. For the selected root and every included descendant, verify that the migration suffix exists and that the source and corresponding destination GUIDs match.

Verify the dataset mapping, check that all receives completed, and resolve any pending receive state, missing parents, destination modifications, or newer conflicting destination snapshots. Protect the received migration snapshots while verification and handover are in progress.

Do not proceed merely because the migration snapshot appears on the root. Every included dataset must be checked.

## Step 6: Create and Test the Recursive Task (UI)

Create a ZFS replication task using the approved source and destination roots. Enable **Send Recursive**, preserve the approved encryption/transfer settings, and configure the desired source and destination retention. Keep the new schedule disabled initially.

Leave **Force full resync (next run only)** and destination overwrite/rollback permission off. Run **Dry Run** and inspect the logs. The planner should select the shared migration snapshot as an incremental base, not propose a full resend or report a missing baseline.

A successful Dry Run does not prove the destination will accept the real stream. Use **Run Now**, check the resulting logs and snapshots, and confirm the first recursive replication finishes successfully. Source changes made after the migration snapshot will be included in this new run.

## Step 7: Hand Over Scheduling and Retention (UI and CLI)

After verifying the real recursive run, enable the new schedule. Leave the old tasks disabled until the customer accepts the handover; do not run both sets of tasks against the same hierarchy during this transition.

Plan cleanup separately. The new task's retention does not automatically take ownership of snapshots tagged for the old tasks, and manually created migration snapshots are not automatically guaranteed to fall under its retention policy. Review both source and destination histories against the customer's backup requirements before deleting anything.

Once a newer verified shared recursive baseline is available and the migration snapshots are no longer needed, release only the temporary holds recorded for this migration. For an individual held snapshot, on the server holding it:

```bash
zfs release service-replication-migration "${HELD_SNAPSHOT:?Set HELD_SNAPSHOT to a recorded held snapshot}"
```

Release recursively applied holds on the recorded migration hierarchy as appropriate. Releasing a hold does not delete a snapshot. Do not release holds belonging to other workflows or remove the last usable shared baseline.

## When to Stop and Escalate

Stop if the destination layout does not match, the root or parent needs an unsafe overwrite, snapshot GUIDs disagree, encrypted replication modes are incompatible, clones require special handling, or a transfer would discard backup-only data. Unexpected full-send estimates or incomplete receives also require review before proceeding.

Keep the old task definitions and required snapshots while resolving the issue. If abandoning a partially completed migration, reassess the common snapshots and destination state before re-enabling old tasks; their previous baselines may no longer be the latest destination snapshots.

## Customer Explanation

We can usually preserve the data already replicated by bringing each dataset forward to one common migration snapshot. Each dataset uses its own existing snapshot as the starting point, so only its changes need to be transferred where a valid baseline exists. Once the root and all datasets share the new baseline with the backup, one recursive task can take over. Any dataset without a usable baseline may still need a full transfer, and the root layout must be checked before starting.

## References

These links describe current OpenZFS behavior. Check the installed version's manual before applying version-dependent options.

- [OpenZFS zfs send manual](https://openzfs.github.io/openzfs-docs/man/master/8/zfs-send.8.html)
- [OpenZFS zfs receive manual](https://openzfs.github.io/openzfs-docs/man/master/8/zfs-receive.8.html)