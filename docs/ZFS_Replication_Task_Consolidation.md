# Replacing Separate Dataset Tasks with One Recursive Task

## The Idea

Bring every dataset to a new snapshot named `migration-to-recursive`. Once that snapshot has been copied to the backup for every dataset, one recursive task can take over.

Each dataset can start from its own old replicated snapshot. We are not merging snapshots: we are transferring each dataset's changes to the same new snapshot name. Datasets without an old snapshot shared with the backup may still need a full transfer.

Use the UI to manage tasks and the CLI to copy the migration snapshots. Clicking **Run Now** on the old tasks will not do this: it creates different, task-specific snapshots.

## Before You Start

Service must check the customer's dataset paths, available space, ZFS versions, and backup state first. Keep a recoverable backup and a record of the old task settings.

**The root dataset must be included, not just the children.** If the root or an intermediate parent was never replicated, stop and get a plan for it. It may need a full transfer of its own contents. Do not force that transfer into a populated backup parent or destination pool root.

The commands below are for **unencrypted datasets over SSH**. Encrypted datasets or clones need a reviewed transfer plan; do not change an existing raw-send strategy. Use the customer's SSH port and identity options where required.

Run the commands in Bash with the necessary ZFS permissions. They prompt for the customer's actual values. `$ROOT` and similar names store your answers; the `[[ -n ... ]]` checks prevent running with blank answers. No question-mark variable syntax is needed.

## Step 1: Pause the Old Tasks (UI)

Let active transfers finish. Disable the old replication schedules and any snapshot/pruning automation affecting these datasets. **Keep the tasks and snapshots; do not delete them.**

Do not write to the backup or create, rename, or delete datasets during the migration. Source applications can continue writing, but coordinate an application pause when taking the snapshot if application-consistent backups are required.

## Step 2: Find Each Dataset's Starting Snapshot (CLI)

Run this on **each server**, entering its source or backup root as appropriate:

```bash
read -r -p "Dataset root on this server: " ROOT
[[ -n "$ROOT" ]] && zfs list -t snapshot -o name,guid -s creation -r "$ROOT"
```

Make a list of each source dataset, its backup dataset, and its usable old snapshot. Include the root and all parent datasets. The folder structure beneath the source and backup roots must match.

For hundreds of datasets, have a batch script generate this list from both servers instead of entering it by hand. Service must review the list and resolve all flagged problems before taking the migration snapshot in Step 3.

Compare the **GUID** numbers: matching GUIDs prove that two snapshots are the same replicated snapshot. Matching names alone do not. Normally, use the backup's latest snapshot, provided it also exists on the source and the backup has not changed since it.

If there are newer conflicting backup snapshots, backup writes, or unfinished receives, stop and investigate. Protect the selected snapshots from deletion; Service can use temporary ZFS holds if needed.

## Step 3: Take One New Recursive Snapshot (CLI, Source)

Check that `migration-to-recursive` does not already exist anywhere in the selected hierarchy. On the **source server**, run:

```bash
read -r -p "Source dataset root: " ROOT
[[ -n "$ROOT" ]] &&
  zfs snapshot -r "$ROOT@migration-to-recursive" &&
  zfs hold -r service-replication-migration "$ROOT@migration-to-recursive"
```

This takes the new snapshot on the root and all children, and protects it from deletion. Keep a record of these temporary holds for later cleanup.

## Step 4: Copy the Migration Snapshots (CLI, Source)

### Recommended for Hundreds of Datasets: Batch Transfer

Use the [batch script page](ZFS_Replication_Consolidation_Script.dokuwiki.txt) to process the list from Step 2. It includes the complete copyable script and commands to plan, apply, and verify the migration. You should not need to enter commands manually for all 300 datasets. Service must review the plan and test the script on a small representative hierarchy before the full migration.

The script should:

1. Check every source/backup mapping and shared snapshot GUID. Flag missing starting snapshots, root/parent problems, encryption differences, backup changes, and unfinished receives. Do not automatically force a full transfer for exceptions.
2. Estimate the planned transfers and produce a report for Service to approve. Before sending, recheck that the approved snapshots and backup state have not changed.
3. Copy each approved dataset from its own old snapshot to `@migration-to-recursive`. Start with sequential transfers so the servers are not overloaded; no manual entry is needed between datasets.
4. Log each result and stop on errors. On restart, skip a completed transfer only after confirming the migration snapshot's source/backup GUIDs match and the backup state is still acceptable. Stop for review of partially received transfers.
5. Verify the migration snapshots for the entire hierarchy, including the root and parents. Report any incomplete or mismatched dataset before proceeding to Step 6.

ZFS still needs a separate stream for each dataset because the old starting snapshots differ. The script automates those streams; it does not merge snapshots or bypass the root checks.

### Manual Transfer: Testing and Exceptions

Use these commands to test a few datasets or handle approved exceptions. Enter the full old source snapshot name from Step 2, and the full new source snapshot name ending in `@migration-to-recursive`. Both must belong to the same source dataset.

First, estimate the transfer; this does not copy anything:

```bash
read -r -p "Old source snapshot, including @name: " OLD_SNAPSHOT
read -r -p "New source snapshot, ending in @migration-to-recursive: " NEW_SNAPSHOT
[[ -n "$OLD_SNAPSHOT" && -n "$NEW_SNAPSHOT" ]] &&
  zfs send -nPv -i "$OLD_SNAPSHOT" "$NEW_SNAPSHOT"
```

After reviewing the estimate, use the **same Bash session** to copy it:

```bash
read -r -p "Backup SSH destination (user@host): " BACKUP_SSH
read -r -p "Backup dataset path, without @snapshot: " BACKUP_DATASET
set -o pipefail
[[ -n "$OLD_SNAPSHOT" && -n "$NEW_SNAPSHOT" &&
   -n "$BACKUP_SSH" && -n "$BACKUP_DATASET" ]] &&
  zfs send -i "$OLD_SNAPSHOT" "$NEW_SNAPSHOT" |
  ssh "$BACKUP_SSH" zfs receive -u "$BACKUP_DATASET"
```

This sends only changes since the old snapshot. It does not force rollback, and `-u` prevents the receive from mounting the backup filesystem.

Record each successful manual transfer. The batch process or approved exception plan must also cover the root and intermediate parents. If any dataset has no shared old snapshot, it needs a separately approved full transfer instead of this command.

**If a command fails, stop. Do not add `-F` or enable overwrite to bypass the error.** A forced recursive receive can delete backup-only snapshots and datasets.

## Step 5: Check Every Dataset (CLI)

Run the listing command from Step 2 again on both servers. Every included dataset, including the root and parents, must have `@migration-to-recursive` with a matching source/backup GUID. Confirm all transfers finished and the backup has not been modified.

Do not create same-name snapshots manually on the backup: they would have different GUIDs. Keep pruning paused and protect the received migration snapshots until the handover is complete.

## Step 6: Test the New Task (UI)

Create one ZFS replication task with the checked source and backup roots. Enable **Send Recursive**, keep the approved transfer settings, and set the desired retention. Leave its schedule disabled for now.

Keep **Force full resync** and overwrite/rollback permission **off**. Run **Dry Run** and confirm the logs select the migration snapshot as the incremental starting point. Stop if it proposes a full resend or reports a missing starting snapshot.

Then click **Run Now** and verify a successful real transfer and matching new snapshots. Dry Run alone does not prove the backup will accept the transfer.

## Step 7: Switch Schedules and Clean Up

Enable the new schedule only after Step 6 succeeds. Leave the old tasks disabled until the customer accepts the handover. Do not run both sets against the same backup hierarchy.

Plan snapshot cleanup separately: the new task will not automatically prune all old task-owned or manually created migration snapshots. Once a newer shared recursive snapshot is verified, Service can release the recorded migration holds and review which old snapshots can be deleted. Never remove the last usable shared snapshot or holds belonging to another workflow.

If you abandon the migration, check the backup's current snapshot history before re-enabling the old tasks; their old starting snapshots may no longer be the latest ones on the backup.

## References

Check the installed ZFS version's manual when preparing the customer's commands.

- [OpenZFS zfs send manual](https://openzfs.github.io/openzfs-docs/man/master/8/zfs-send.8.html)
- [OpenZFS zfs receive manual](https://openzfs.github.io/openzfs-docs/man/master/8/zfs-receive.8.html)