"""Phase-oriented ZFS replication workflow."""

import datetime
import getpass
import os
import re
import shlex
import subprocess
import sys
import time
import traceback

from .config import as_bool, clamp_mbuffer, get_dest_ports, join_zfs_path
from .constants import MBUFFER_BLOCK_SIZE
from .context import notifier
from .logging_utils import dbg, dbg_env, dbg_kv, safe_print
from .models import ReplicationRun
from .notifications import send_houston_notification
from .planner import build_zfs_send_args
from .process import _apply_tcp_tuning
from .retention import destroy_snapshots_with_progress, prune_snapshots_by_retention
from .schedules import load_schedule_json, match_current_tier
from .snapshots import (
    create_snapshot_local,
    create_snapshot_remote,
    dataset_of_snapshot,
    filter_dataset_snapshots,
    get_local_snapshots,
    get_remote_snapshots,
    get_written_since_snapshot,
    snapshot_exists_on_destination,
    snapshot_suffix,
    tag_received_snapshots,
)
from .state import (
    _clear_one_shot_flags,
    _clear_pending_full_send,
    _read_pending_full_send,
    _write_pending_full_send,
    clear_receive_resume_token,
    get_receive_resume_token,
)
from .ssh import SSH_BASE_OPTS, _SSH_CIPHER
from .transfers import (
    resume_receive_pull,
    resume_receive_push,
    send_snapshot_pull,
    send_snapshot_push,
)


def _initialize_run(ctx: ReplicationRun):
    notifier.notify('STATUS=Starting ZFS replication task…')
    notifier.notify('READY=1')
    if not os.environ.get('HOME'):
        import pwd
        try:
            os.environ['HOME'] = pwd.getpwuid(os.geteuid()).pw_dir
        except KeyError:
            os.environ['HOME'] = '/root'
    dbg('=== task start ===')
    dbg_kv('identity', {'euid': os.geteuid(), 'user': getpass.getuser(), 'cwd': os.getcwd(), 'home': os.environ.get('HOME', ''), 'shell': os.environ.get('SHELL', '')})
    dbg_env()
    _apply_tcp_tuning()
    notifier.notify('STATUS=Planning replication…')
    ctx.taskName = os.environ.get('taskName', '')
    if ctx.taskName:
        _lastrun_path = f'/etc/systemd/system/houston_scheduler_ZfsReplicationTask_{ctx.taskName}.lastrun'
        try:
            os.remove(_lastrun_path)
        except FileNotFoundError:
            pass
        except Exception as _e:
            dbg(f'WARNING: could not remove old lastrun file: {_e}')
    ctx.direction = (os.environ.get('zfsRepConfig_direction', 'push') or 'push').strip().lower()
    if ctx.direction not in ('push', 'pull'):
        ctx.direction = 'push'
    ctx.isRecursiveSnap = as_bool(os.environ.get('zfsRepConfig_sendOptions_recursive_flag'))
    ctx.useCustomName = as_bool(os.environ.get('zfsRepConfig_sendOptions_customName_flag'))
    ctx.customName = os.environ.get('zfsRepConfig_sendOptions_customName', '') if ctx.useCustomName else ''
    ctx.isRaw = as_bool(os.environ.get('zfsRepConfig_sendOptions_raw_flag'))
    ctx.isCompressed = as_bool(os.environ.get('zfsRepConfig_sendOptions_compressed_flag'))
    _include_int_env = os.environ.get('zfsRepConfig_sendOptions_includeIntermediateSnapshots', '').strip().lower()
    if _include_int_env in ('0', 'false', 'no', 'off'):
        ctx.includeIntermediateSnapshots = False
    elif _include_int_env in ('1', 'true', 'yes', 'on'):
        ctx.includeIntermediateSnapshots = True
    else:
        ctx.includeIntermediateSnapshots = None
    ctx.transferMethod = (os.environ.get('zfsRepConfig_sendOptions_transferMethod', '') or '').strip().lower()
    (ctx.sshPort, ctx.dataPort) = get_dest_ports(ctx.transferMethod)
    ctx.allowOverwrite = as_bool(os.environ.get('zfsRepConfig_sendOptions_allowOverwrite'), default=False)
    ctx.useExistingDest = as_bool(os.environ.get('zfsRepConfig_sendOptions_useExistingDest'), default=False)
    ctx.forceFullSend = as_bool(os.environ.get('zfsRepConfig_sendOptions_forceFullSend'), default=False)
    ctx.dryRun = as_bool(os.environ.get('zfsRepConfig_sendOptions_dryRun'), default=False)
    ctx.resumeOnly = as_bool(os.environ.get('zfsRepConfig_sendOptions_resumeOnly'), default=False)
    ctx.resumeFailAllowOverwrite = as_bool(os.environ.get('zfsRepConfig_sendOptions_resumeFailAllowOverwrite'), default=False)
    if ctx.taskName and (ctx.forceFullSend or ctx.dryRun or ctx.resumeOnly):
        _clear_one_shot_flags(ctx.taskName)
    try:
        ctx.resumeStallTimeout = int(os.environ.get('zfsRepConfig_sendOptions_resumeStallTimeout', '3600'))
    except (ValueError, TypeError):
        ctx.resumeStallTimeout = 3600
    if ctx.resumeStallTimeout <= 0:
        ctx.resumeStallTimeout = 0
    ctx.remoteUser = os.environ.get('zfsRepConfig_destDataset_user', 'root')
    ctx.remoteHost = os.environ.get('zfsRepConfig_destDataset_host', '')
    ctx.mBufferSize = os.environ.get('zfsRepConfig_sendOptions_mbufferSize', '1')
    ctx.mBufferUnit = os.environ.get('zfsRepConfig_sendOptions_mbufferUnit', 'G')
    (ctx.mBufferSize, ctx.mBufferUnit) = clamp_mbuffer(ctx.mBufferSize, ctx.mBufferUnit)
    ctx.sourceRetentionTime = os.environ.get('zfsRepConfig_snapshotRetention_source_retentionTime', 0)
    ctx.sourceRetentionUnit = os.environ.get('zfsRepConfig_snapshotRetention_source_retentionUnit', '')
    ctx.destinationRetentionTime = os.environ.get('zfsRepConfig_snapshotRetention_destination_retentionTime', 0)
    ctx.destinationRetentionUnit = os.environ.get('zfsRepConfig_snapshotRetention_destination_retentionUnit', '')
    ctx.tier_idx = None
    schedule_json_path = os.environ.get('scheduleJsonPath', '')
    if not schedule_json_path and ctx.taskName:
        derived_path = f'/etc/systemd/system/houston_scheduler_ZfsReplicationTask_{ctx.taskName}.json'
        if os.path.isfile(derived_path):
            schedule_json_path = derived_path
            dbg(f'scheduleJsonPath not in env; using derived path: {derived_path}')
    ctx.schedule_data = load_schedule_json(schedule_json_path)
    schedule_data = ctx.schedule_data
    if schedule_data and isinstance(schedule_data.get('intervals'), list):
        intervals = schedule_data['intervals']
        if len(intervals) > 1:
            now = datetime.datetime.now()
            ctx.tier_idx = match_current_tier(intervals, now)
            dbg(f'Multi-tier: matched tier {ctx.tier_idx} of {len(intervals)}')
        has_per_interval_retention = any((isinstance(iv.get('retention'), dict) for iv in intervals))
        if has_per_interval_retention:
            interval_to_use = intervals[ctx.tier_idx] if ctx.tier_idx is not None else intervals[0]
            iv_ret = interval_to_use.get('retention', {}) or {}
            src_ret = iv_ret.get('source', {}) or {}
            if src_ret.get('retentionTime', 0) > 0:
                ctx.sourceRetentionTime = src_ret['retentionTime']
                ctx.sourceRetentionUnit = src_ret.get('retentionUnit', ctx.sourceRetentionUnit)
            dst_ret = iv_ret.get('destination', {}) or {}
            if dst_ret.get('retentionTime', 0) > 0:
                ctx.destinationRetentionTime = dst_ret['retentionTime']
                ctx.destinationRetentionUnit = dst_ret.get('retentionUnit', ctx.destinationRetentionUnit)
            dbg_kv('tier_retention', {'tier_idx': ctx.tier_idx, 'sourceRetentionTime': ctx.sourceRetentionTime, 'sourceRetentionUnit': ctx.sourceRetentionUnit, 'destinationRetentionTime': ctx.destinationRetentionTime, 'destinationRetentionUnit': ctx.destinationRetentionUnit})
    manual_marker = f'/run/houston-scheduler-manual/houston_scheduler_ZfsReplicationTask_{ctx.taskName}'
    is_manual_run = os.path.isfile(manual_marker)
    if is_manual_run:
        try:
            os.remove(manual_marker)
        except OSError:
            pass
        dbg('Manual run detected — skipping tier tag')
        ctx.tier_idx = None
    srcPool = os.environ.get('zfsRepConfig_sourceDataset_pool', '')
    srcDs = os.environ.get('zfsRepConfig_sourceDataset_dataset', '')
    dstPool = os.environ.get('zfsRepConfig_destDataset_pool', '')
    dstDs = os.environ.get('zfsRepConfig_destDataset_dataset', '')
    ctx.sourceFilesystem = join_zfs_path(srcPool, srcDs)
    ctx.destFilesystem = join_zfs_path(dstPool, dstDs)
    dbg_kv('config', {'direction': ctx.direction, 'transferMethod': ctx.transferMethod, 'sshPort': ctx.sshPort, 'dataPort': ctx.dataPort, 'remoteUser': ctx.remoteUser, 'remoteHost': ctx.remoteHost, 'sourceFilesystem': ctx.sourceFilesystem, 'destFilesystem': ctx.destFilesystem, 'recursive': ctx.isRecursiveSnap, 'compressed': ctx.isCompressed, 'raw': ctx.isRaw, 'includeIntermediates': ctx.includeIntermediateSnapshots, 'allowOverwrite': ctx.allowOverwrite, 'useExistingDest': ctx.useExistingDest, 'mbuffer': f'{ctx.mBufferSize}{ctx.mBufferUnit}', 'mbuffer_block': MBUFFER_BLOCK_SIZE, 'ssh_cipher': _SSH_CIPHER or '(system default)'})
    if not ctx.sourceFilesystem:
        raise RuntimeError('Source dataset is empty (zfsRepConfig_sourceDataset_pool/dataset).')
    if not ctx.destFilesystem:
        raise RuntimeError('Destination dataset is empty (zfsRepConfig_destDataset_pool/dataset).')


def _load_snapshot_inventory(ctx: ReplicationRun):
    if ctx.direction == 'pull':
        if not ctx.remoteHost:
            raise RuntimeError('Pull replication requires Host to be set (remote source).')
        remote_source_fs = ctx.sourceFilesystem
        local_target_fs = ctx.destFilesystem
        if ctx.transferMethod == 'local' or not ctx.transferMethod:
            ctx.transferMethod = 'ssh'
        if ctx.resumeOnly:
            print(f'Checking for resume token on {local_target_fs}…')
            notifier.notify(f'STATUS=Checking for resume token on {local_target_fs}…')
            _resume_token = get_receive_resume_token(local_target_fs)
            if not _resume_token:
                print('RESUME ONLY mode: no resume token found. Nothing to resume.')
                print('The previous transfer either completed successfully or was never started.')
                sys.exit(0)
            print(f'Resume token found on {local_target_fs}. Resuming transfer…')
            notifier.notify(f'STATUS=Resume token found. Resuming transfer to {local_target_fs}…')
            (ok, err) = resume_receive_pull(_resume_token, local_target_fs, remoteHost=ctx.remoteHost, remoteSshPort=ctx.sshPort, remoteUser=ctx.remoteUser, mBufferSize=ctx.mBufferSize, mBufferUnit=ctx.mBufferUnit, forceOverwrite=ctx.allowOverwrite, stall_timeout=ctx.resumeStallTimeout, transferMethod=ctx.transferMethod, recvDataPort=ctx.dataPort)
            if ok:
                print('Resume transfer completed successfully.')
                notifier.notify('STATUS=Resume transfer completed. 100% complete')
                sys.exit(0)
            else:
                print(f'Resume transfer failed: {err}')
                notifier.notify(f'STATUS=Resume transfer failed: {err}')
                sys.exit(1)
        dbg(f"EUID={os.geteuid()} USER={getpass.getuser()} HOME={os.environ.get('HOME')}")
        dbg(f'remoteUser={ctx.remoteUser} remoteHost={ctx.remoteHost} sshPort={ctx.sshPort}')
        p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-vv', f'{ctx.remoteUser}@{ctx.remoteHost}', 'true'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        dbg('ssh -vv output:\n' + p.stdout)
        dbg(f'ssh returncode={p.returncode}')
        print(f'Fetching remote source snapshots from {ctx.remoteUser}@{ctx.remoteHost}:{remote_source_fs}…')
        notifier.notify(f'STATUS=Fetching remote source snapshots from {ctx.remoteUser}@{ctx.remoteHost}:{remote_source_fs}…')
        ctx.sourceSnapshots = get_remote_snapshots(ctx.remoteUser, ctx.remoteHost, ctx.sshPort, remote_source_fs) or []
        ctx.sourceSnapshots.sort(key=lambda x: x.order_key)
        print(f'Fetching local destination snapshots for {local_target_fs}…')
        notifier.notify(f'STATUS=Fetching local destination snapshots for {local_target_fs}…')
        ctx.destinationSnapshots = get_local_snapshots(local_target_fs)
        dbg(f"sourceSnapshots count={(len(ctx.sourceSnapshots) if ctx.sourceSnapshots is not None else 'None')}")
        dbg(f"destSnapshots state={('None' if ctx.destinationSnapshots is None else len(ctx.destinationSnapshots))}")
        if ctx.sourceSnapshots:
            dbg(f'sourceSnapshots newest={ctx.sourceSnapshots[-1].name} oldest={ctx.sourceSnapshots[0].name}')
        if ctx.destinationSnapshots:
            dbg(f'destSnapshots newest={ctx.destinationSnapshots[-1].name} oldest={ctx.destinationSnapshots[0].name}')
    else:
        local_source_fs = ctx.sourceFilesystem
        target_fs = ctx.destFilesystem
        if ctx.transferMethod == 'ssh' and (not ctx.remoteHost):
            ctx.transferMethod = 'local'
        if ctx.resumeOnly:
            if ctx.remoteHost:
                print(f'Checking for resume token on {ctx.remoteUser}@{ctx.remoteHost}:{target_fs}…')
                notifier.notify(f'STATUS=Checking for resume token on {ctx.remoteUser}@{ctx.remoteHost}:{target_fs}…')
                _resume_token = get_receive_resume_token(target_fs, ctx.remoteUser, ctx.remoteHost, ctx.sshPort)
            else:
                print(f'Checking for resume token on {target_fs}…')
                notifier.notify(f'STATUS=Checking for resume token on {target_fs}…')
                _resume_token = get_receive_resume_token(target_fs)
            if not _resume_token:
                print('RESUME ONLY mode: no resume token found. Nothing to resume.')
                print('The previous transfer either completed successfully or was never started.')
                sys.exit(0)
            print(f'Resume token found on {target_fs}. Resuming transfer…')
            notifier.notify(f'STATUS=Resume token found. Resuming transfer to {target_fs}…')
            (ok, err) = resume_receive_push(_resume_token, target_fs, recvHost=ctx.remoteHost or '', recvSshPort=ctx.sshPort, recvHostUser=ctx.remoteUser, mBufferSize=ctx.mBufferSize, mBufferUnit=ctx.mBufferUnit, transferMethod=ctx.transferMethod, recvDataPort=ctx.dataPort, forceOverwrite=ctx.allowOverwrite, stall_timeout=ctx.resumeStallTimeout)
            if ok:
                print('Resume transfer completed successfully.')
                notifier.notify('STATUS=Resume transfer completed. 100% complete')
                sys.exit(0)
            else:
                print(f'Resume transfer failed: {err}')
                notifier.notify(f'STATUS=Resume transfer failed: {err}')
                sys.exit(1)
        if ctx.remoteHost:
            dbg(f"EUID={os.geteuid()} USER={getpass.getuser()} HOME={os.environ.get('HOME')}")
            dbg(f'remoteUser={ctx.remoteUser} remoteHost={ctx.remoteHost} sshPort={ctx.sshPort}')
            p = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-vv', f'{ctx.remoteUser}@{ctx.remoteHost}', 'true'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            dbg('ssh -vv output:\n' + p.stdout)
            dbg(f'ssh returncode={p.returncode}')
        print(f'Fetching local source snapshots for {local_source_fs}…')
        notifier.notify(f'STATUS=Fetching local source snapshots for {local_source_fs}…')
        ctx.sourceSnapshots = get_local_snapshots(local_source_fs) or []
        ctx.sourceSnapshots.sort(key=lambda x: x.order_key)
        if ctx.remoteHost and ctx.remoteUser:
            print(f'Fetching remote destination snapshots from {ctx.remoteUser}@{ctx.remoteHost}:{target_fs}…')
            notifier.notify(f'STATUS=Fetching remote destination snapshots from {ctx.remoteUser}@{ctx.remoteHost}:{target_fs}…')
            ctx.destinationSnapshots = get_remote_snapshots(ctx.remoteUser, ctx.remoteHost, ctx.sshPort, target_fs)
        else:
            print(f'Fetching local destination snapshots for {target_fs}…')
            notifier.notify(f'STATUS=Fetching local destination snapshots for {target_fs}…')
            ctx.destinationSnapshots = get_local_snapshots(target_fs)
    ctx.forceOverwrite = False
    ctx.incrementalSnapName = ''


def _recover_pending_full_send(ctx: ReplicationRun):
    ctx.pending_state = _read_pending_full_send(ctx.taskName)
    if ctx.pending_state:
        pending_snap = ctx.pending_state.get('snapshot', '')
        pending_dest = ctx.pending_state.get('destFilesystem', '')
        pending_src = ctx.pending_state.get('sourceFilesystem', '')
        pending_dir = ctx.pending_state.get('direction', '')
        print(f"Pending full send detected: {pending_snap} → {pending_dest} (started {ctx.pending_state.get('startedAt', '?')})")
        dbg(f'Pending full send state: {ctx.pending_state}')
        config_matches = pending_dest == ctx.destFilesystem and pending_src == ctx.sourceFilesystem and (pending_dir == ctx.direction)
        if not config_matches:
            print(f'Pending full send state does not match current task config (state: {pending_src}→{pending_dest} {pending_dir}, config: {ctx.sourceFilesystem}→{ctx.destFilesystem} {ctx.direction}). Discarding stale state.')
            _clear_pending_full_send(ctx.taskName)
            ctx.pending_state = None
        elif not pending_snap:
            print('Pending full send state has no snapshot name. Discarding.')
            _clear_pending_full_send(ctx.taskName)
            ctx.pending_state = None
    if ctx.pending_state:
        pending_suffix = snapshot_suffix(pending_snap)
        if ctx.direction == 'pull':
            (exists, _) = snapshot_exists_on_destination(pending_dest, pending_suffix, remote_user=None, remote_host=None, remote_port=ctx.sshPort)
        else:
            (exists, _) = snapshot_exists_on_destination(pending_dest, pending_suffix, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
        if exists:
            print(f'Pending full send snapshot {pending_snap} found on destination — full send completed.')
            _clear_pending_full_send(ctx.taskName)
            ctx.pending_state = None
        else:
            print(f'Pending full send snapshot NOT found on destination — full send still incomplete.')
            if ctx.direction == 'pull':
                _token = get_receive_resume_token(ctx.destFilesystem)
            else:
                _token = get_receive_resume_token(ctx.destFilesystem, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
            if _token:
                msg = f'Resume token found for pending full send to {ctx.destFilesystem}. Resuming…'
                notifier.notify(f'STATUS={msg}')
                print(msg)
                if ctx.direction == 'pull':
                    (ok, err) = resume_receive_pull(resume_token=_token, localRecvFs=ctx.destFilesystem, remoteHost=ctx.remoteHost, remoteSshPort=ctx.sshPort, remoteUser=ctx.remoteUser, mBufferSize=str(ctx.mBufferSize), mBufferUnit=ctx.mBufferUnit, forceOverwrite=True, stall_timeout=ctx.resumeStallTimeout, transferMethod=ctx.transferMethod, recvDataPort=ctx.dataPort)
                else:
                    (ok, err) = resume_receive_push(resume_token=_token, recvName=ctx.destFilesystem, recvHost=ctx.remoteHost, recvSshPort=ctx.sshPort, recvHostUser=ctx.remoteUser, mBufferSize=str(ctx.mBufferSize), mBufferUnit=ctx.mBufferUnit, transferMethod=ctx.transferMethod if ctx.transferMethod else 'ssh', recvDataPort=ctx.dataPort, forceOverwrite=True, stall_timeout=ctx.resumeStallTimeout)
                if ok:
                    if ctx.direction == 'pull':
                        (exists2, _) = snapshot_exists_on_destination(pending_dest, pending_suffix, remote_user=None, remote_host=None, remote_port=ctx.sshPort)
                    else:
                        (exists2, _) = snapshot_exists_on_destination(pending_dest, pending_suffix, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
                    if exists2:
                        print(f'Resume completed and snapshot {pending_snap} verified on destination.')
                        _clear_pending_full_send(ctx.taskName)
                        ctx.pending_state = None
                    else:
                        print(f'Resume completed but snapshot still missing — resume token was stale/partial.')
                        print('Will redo full send with the original snapshot.')
                        if ctx.direction == 'pull':
                            clear_receive_resume_token(ctx.destFilesystem)
                        else:
                            clear_receive_resume_token(ctx.destFilesystem, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
                else:
                    print(f'Resume failed: {err}. Will redo full send.')
                    if ctx.direction == 'pull':
                        clear_receive_resume_token(ctx.destFilesystem)
                    else:
                        clear_receive_resume_token(ctx.destFilesystem, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
            else:
                print('No resume token found. Will redo full send with the original snapshot.')
            if ctx.pending_state:
                if ctx.direction == 'pull':
                    src_snaps = get_remote_snapshots(ctx.remoteUser, ctx.remoteHost, ctx.sshPort, pending_src) or []
                else:
                    src_snaps = get_local_snapshots(pending_src) or []
                src_snap_names = {s.name for s in src_snaps}
                if pending_snap in src_snap_names:
                    print(f'Original source snapshot {pending_snap} still exists. Resending full…')
                    notifier.notify(f'STATUS=Resending full: {pending_snap} → {ctx.destFilesystem}…')
                    if ctx.direction == 'pull':
                        dest_snaps_now = get_local_snapshots(ctx.destFilesystem)
                    elif ctx.remoteHost:
                        dest_snaps_now = get_remote_snapshots(ctx.remoteUser, ctx.remoteHost, ctx.sshPort, ctx.destFilesystem)
                    else:
                        dest_snaps_now = get_local_snapshots(ctx.destFilesystem)
                    if dest_snaps_now:
                        if ctx.direction == 'pull' or not ctx.remoteHost:
                            destroy_snapshots_with_progress(dest_snaps_now, ctx.destFilesystem, reason='for full resend')
                        else:
                            destroy_snapshots_with_progress(dest_snaps_now, ctx.destFilesystem, remote_user=ctx.remoteUser, remote_host=ctx.remoteHost, ssh_port=ctx.sshPort, reason='for full resend')
                    if ctx.direction == 'pull':
                        send_snapshot_pull(remoteSnapName=pending_snap, localRecvFs=ctx.destFilesystem, remoteBaseSnapName='', compressed=ctx.isCompressed, raw=ctx.isRaw, remoteHost=ctx.remoteHost, remoteSshPort=ctx.sshPort, remoteUser=ctx.remoteUser, mBufferSize=str(ctx.mBufferSize), mBufferUnit=ctx.mBufferUnit, forceOverwrite=True, recursive=ctx.isRecursiveSnap, transferMethod=ctx.transferMethod, recvDataPort=ctx.dataPort, include_intermediates=ctx.includeIntermediateSnapshots)
                    else:
                        send_snapshot_push(pending_snap, ctx.destFilesystem, '', ctx.isCompressed, ctx.isRaw, ctx.remoteHost, ctx.sshPort, ctx.remoteUser, str(ctx.mBufferSize), ctx.mBufferUnit, True, ctx.transferMethod, recursive=ctx.isRecursiveSnap, recvDataPort=ctx.dataPort, include_intermediates=ctx.includeIntermediateSnapshots)
                    _clear_pending_full_send(ctx.taskName)
                    notifier.notify('STATUS=ZFS replication task completed (full resend). 100% complete')
                    try:
                        lastrun_path = f'/etc/systemd/system/houston_scheduler_ZfsReplicationTask_{ctx.taskName}.lastrun'
                        with open(lastrun_path, 'w') as f:
                            f.write(str(int(time.time())))
                    except Exception as e:
                        dbg(f'WARNING: failed to write lastrun file: {e}')
                    return True
                else:
                    print(f'Original source snapshot {pending_snap} no longer exists.')
                    print('Cannot resume the interrupted full send. Clearing state and starting fresh.')
                    _clear_pending_full_send(ctx.taskName)
                    ctx.pending_state = None
    return False


def _resume_interrupted_receive(ctx: ReplicationRun):
    if not ctx.pending_state and ctx.direction == 'pull':
        resume_token = get_receive_resume_token(ctx.destFilesystem)
        if resume_token:
            msg = f'Found resume token on destination {ctx.destFilesystem}. Attempting to resume receive.'
            notifier.notify(f'STATUS={msg}')
            print(msg)
            send_houston_notification({'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'event': 'zfs_replication_resume_token', 'subject': 'ZFS Replication Resume Token Found', 'email_message': f'{msg} Token: {resume_token}', 'fileSystem': ctx.destFilesystem, 'snapShot': '', 'replicationDestination': ctx.destFilesystem, 'severity': 'warning', 'errors': resume_token})
            (ok, err) = resume_receive_pull(resume_token=resume_token, localRecvFs=ctx.destFilesystem, remoteHost=ctx.remoteHost, remoteSshPort=ctx.sshPort, remoteUser=ctx.remoteUser, mBufferSize=str(ctx.mBufferSize), mBufferUnit=ctx.mBufferUnit, forceOverwrite=ctx.allowOverwrite, stall_timeout=ctx.resumeStallTimeout, transferMethod=ctx.transferMethod, recvDataPort=ctx.dataPort)
            if ok:
                return True
            err_lower = (err or '').lower()
            needs_overwrite = 'destination exists' in err_lower or 'must specify -f' in err_lower
            if needs_overwrite and (not ctx.allowOverwrite):
                hard_msg = f'Resume failed for {ctx.destFilesystem}: destination requires rollback (-F) but Allow Overwrite is not enabled. Enable Allow Overwrite or manually clear the destination state.'
                notifier.notify(f'STATUS={hard_msg}')
                print(hard_msg)
                sys.exit(2)
            if ctx.resumeFailAllowOverwrite or needs_overwrite:
                msg = f'Resume attempt failed for {ctx.destFilesystem}; clearing resume token and continuing with normal replication.'
                notifier.notify(f'STATUS={msg}')
                print(msg)
                (cleared, clear_err) = clear_receive_resume_token(ctx.destFilesystem)
                if not cleared:
                    fail_msg = f'Failed to clear resume token for {ctx.destFilesystem}: {clear_err}'
                    notifier.notify(f'STATUS={fail_msg}')
                    print(fail_msg)
                    sys.exit(2)
                if needs_overwrite:
                    ctx.forceOverwrite = True
            elif 'modified since' in err_lower or 'has been modified' in err_lower:
                hard_msg = 'Resume failed because destination was modified since the most recent snapshot. Refusing to continue with normal replication.'
                notifier.notify(f'STATUS={hard_msg}')
                print(hard_msg)
                sys.exit(2)
            warn_msg = f'Resume attempt failed for {ctx.destFilesystem}. Continuing with normal replication.'
            notifier.notify(f'STATUS={warn_msg}')
            print(warn_msg)
            send_houston_notification({'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'event': 'zfs_replication_resume_failed', 'subject': 'ZFS Replication Resume Failed', 'email_message': f'{warn_msg} Token: {resume_token}. Error: {err}', 'fileSystem': ctx.destFilesystem, 'snapShot': '', 'replicationDestination': ctx.destFilesystem, 'severity': 'warning', 'errors': f'{resume_token} | {err}'})
    elif not ctx.pending_state:
        resume_token = get_receive_resume_token(ctx.destFilesystem, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
        if resume_token:
            msg = f'Found resume token on destination {ctx.destFilesystem}. Attempting to resume receive.'
            notifier.notify(f'STATUS={msg}')
            print(msg)
            send_houston_notification({'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'event': 'zfs_replication_resume_token', 'subject': 'ZFS Replication Resume Token Found', 'email_message': f'{msg} Token: {resume_token}', 'fileSystem': ctx.destFilesystem, 'snapShot': '', 'replicationDestination': ctx.destFilesystem, 'severity': 'warning', 'errors': resume_token})
            (ok, err) = resume_receive_push(resume_token=resume_token, recvName=ctx.destFilesystem, recvHost=ctx.remoteHost, recvSshPort=ctx.sshPort, recvHostUser=ctx.remoteUser, mBufferSize=str(ctx.mBufferSize), mBufferUnit=ctx.mBufferUnit, transferMethod=ctx.transferMethod if ctx.transferMethod else 'ssh', recvDataPort=ctx.dataPort, forceOverwrite=ctx.allowOverwrite, stall_timeout=ctx.resumeStallTimeout)
            if ok:
                return True
            err_lower = (err or '').lower()
            needs_overwrite = 'destination exists' in err_lower or 'must specify -f' in err_lower
            if needs_overwrite and (not ctx.allowOverwrite):
                hard_msg = f'Resume failed for {ctx.destFilesystem}: destination requires rollback (-F) but Allow Overwrite is not enabled. Enable Allow Overwrite or manually clear the destination state.'
                notifier.notify(f'STATUS={hard_msg}')
                print(hard_msg)
                sys.exit(2)
            if ctx.resumeFailAllowOverwrite or needs_overwrite:
                msg = f'Resume attempt failed for {ctx.destFilesystem}; clearing resume token and continuing with normal replication.'
                notifier.notify(f'STATUS={msg}')
                print(msg)
                (cleared, clear_err) = clear_receive_resume_token(ctx.destFilesystem, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
                if not cleared:
                    fail_msg = f'Failed to clear resume token for {ctx.destFilesystem}: {clear_err}'
                    notifier.notify(f'STATUS={fail_msg}')
                    print(fail_msg)
                    sys.exit(2)
                if needs_overwrite:
                    ctx.forceOverwrite = True
            elif 'modified since' in err_lower or 'has been modified' in err_lower:
                hard_msg = 'Resume failed because destination was modified since the most recent snapshot. Refusing to continue with normal replication.'
                notifier.notify(f'STATUS={hard_msg}')
                print(hard_msg)
                sys.exit(2)
            warn_msg = f'Resume attempt failed for {ctx.destFilesystem}. Continuing with normal replication.'
            notifier.notify(f'STATUS={warn_msg}')
            print(warn_msg)
            send_houston_notification({'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'event': 'zfs_replication_resume_failed', 'subject': 'ZFS Replication Resume Failed', 'email_message': f'{warn_msg} Token: {resume_token}. Error: {err}', 'fileSystem': ctx.destFilesystem, 'snapShot': '', 'replicationDestination': ctx.destFilesystem, 'severity': 'warning', 'errors': f'{resume_token} | {err}'})
    if ctx.resumeOnly:
        print('RESUME ONLY mode: resume was attempted but did not complete successfully.')
        print('Run a normal replication (Run Now) to continue, or try Resume Transfer again.')
        sys.exit(1)
    return False


def _announce_dry_run(ctx: ReplicationRun):
    if ctx.dryRun:
        print('\n=== DRY RUN MODE ===')
        print('No snapshots will be created and no data will be transferred.\n')


def _plan_send(ctx: ReplicationRun):
    if ctx.destinationSnapshots is None:
        print('Destination dataset does not exist. Will create it via full receive (no -F).')
        ctx.forceOverwrite = False
    elif not ctx.destinationSnapshots:
        print('Destination exists but has no snapshots.')
        if ctx.useExistingDest and ctx.allowOverwrite:
            print('Using existing destination with overwrite: full send with -F into existing dataset.')
            ctx.forceOverwrite = True
        elif ctx.useExistingDest:
            print('Destination dataset already exists and has no snapshots.\nZFS requires -F for a full send into an existing dataset.\nEnable Allow Overwrite to permit rollback, or point to a new/empty destination.')
            sys.exit(2)
        else:
            print('Treating destination as new dataset path. Full send (no -F).')
            ctx.forceOverwrite = False
    elif ctx.forceFullSend:
        print('FORCE FULL SEND enabled: ignoring common snapshots and performing full send.')
        ctx.forceOverwrite = True
        ctx.incrementalSnapName = ''
    else:
        if ctx.isRecursiveSnap:
            src_root_snaps = filter_dataset_snapshots(ctx.sourceSnapshots, ctx.sourceFilesystem)
            dst_root_snaps = filter_dataset_snapshots(ctx.destinationSnapshots, ctx.destFilesystem)
        else:
            src_root_snaps = ctx.sourceSnapshots
            dst_root_snaps = ctx.destinationSnapshots
        src_guids = {s.guid for s in src_root_snaps}
        common_candidates = [d for d in dst_root_snaps if d.guid in src_guids]
        if not common_candidates:
            print('No common snapshots found on the destination (root dataset).')
            if ctx.allowOverwrite:
                print('ALLOW OVERWRITE enabled: proceeding with full send and -F (will roll back dest).')
                ctx.forceOverwrite = True
                ctx.incrementalSnapName = ''
            else:
                print('Refusing to overwrite destination without a common base. Enable allowOverwrite or choose a new destination.')
                sys.exit(2)
        else:
            common_candidates.sort(key=lambda s: s.creation_epoch, reverse=True)
            mostRecentCommonSnap = common_candidates[0]
            src_guid_to_name = {s.guid: s.name for s in src_root_snaps}
            ctx.incrementalSnapName = src_guid_to_name[mostRecentCommonSnap.guid]
            print(f'Most recent common snapshot: {ctx.incrementalSnapName}')
            dest_check_snaps = dst_root_snaps if ctx.isRecursiveSnap else ctx.destinationSnapshots
            dest_check_snaps_sorted = sorted(dest_check_snaps, key=lambda s: s.creation_epoch)
            common_idx = -1
            for (i, d) in enumerate(dest_check_snaps_sorted):
                if d.guid == mostRecentCommonSnap.guid:
                    common_idx = i
                    break
            destAhead = False
            if common_idx >= 0:
                for d in dest_check_snaps_sorted[common_idx + 1:]:
                    if d.guid not in src_guids:
                        destAhead = True
                        break
            if destAhead and (not ctx.allowOverwrite):
                print('Destination has newer snapshots than the common base. Enable Allow Overwrite (-F) or choose a different destination.')
                sys.exit(2)
            if destAhead and ctx.allowOverwrite:
                print('Destination is ahead; Allow Overwrite enabled: will roll back with -F.')
                ctx.forceOverwrite = True
            if not destAhead and ctx.allowOverwrite:
                if ctx.direction == 'pull':
                    dest_root_snaps = filter_dataset_snapshots(ctx.destinationSnapshots, ctx.destFilesystem)
                    written_remote = None
                    if dest_root_snaps:
                        dest_root_snaps.sort(key=lambda s: s.order_key)
                        dest_latest = dest_root_snaps[-1]
                        written_remote = get_written_since_snapshot(ctx.destFilesystem, dest_latest.name)
                else:
                    dest_root_snaps = filter_dataset_snapshots(ctx.destinationSnapshots, ctx.destFilesystem)
                    written_remote = None
                    if dest_root_snaps:
                        dest_root_snaps.sort(key=lambda s: s.order_key)
                        dest_latest = dest_root_snaps[-1]
                        written_remote = get_written_since_snapshot(ctx.destFilesystem, dest_latest.name, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
                if written_remote is None:
                    print('Note: Could not determine written@SNAP; proceeding without forcing -F based on that.')
                elif written_remote > 0:
                    print('Destination modified since latest snapshot; Allow Overwrite enabled: will receive with -F (rollback).')
                    ctx.forceOverwrite = True


def _report_dry_run(ctx: ReplicationRun):
    if ctx.dryRun:
        print('\n--- Dry Run Summary ---')
        print(f'  Direction:        {ctx.direction}')
        print(f'  Source:           {ctx.sourceFilesystem}')
        print(f'  Destination:      {ctx.destFilesystem}')
        print(f"  Transfer method:  {ctx.transferMethod or 'local'}")
        print(f'  Recursive:        {ctx.isRecursiveSnap}')
        print(f'  Compressed:       {ctx.isCompressed}')
        print(f'  Raw:              {ctx.isRaw}')
        print(f'  Force overwrite:  {ctx.forceOverwrite}')
        print(f'  Source snapshots: {(len(ctx.sourceSnapshots) if ctx.sourceSnapshots else 0)}')
        print(f'  Dest snapshots:   {(len(ctx.destinationSnapshots) if ctx.destinationSnapshots else 0)}')
        if ctx.incrementalSnapName:
            print(f'  Incremental from: {ctx.incrementalSnapName}')
            print(f'  Mode:             Incremental send')
        else:
            print(f'  Mode:             Full send (no common base)')
        if ctx.direction == 'pull':
            token = get_receive_resume_token(ctx.destFilesystem)
        else:
            token = get_receive_resume_token(ctx.destFilesystem, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
        if token:
            print(f'  Resume token:     YES (interrupted transfer can be resumed)')
        else:
            print(f'  Resume token:     None')
        if ctx.sourceSnapshots:
            if ctx.isRecursiveSnap:
                dry_run_snaps = filter_dataset_snapshots(ctx.sourceSnapshots, ctx.sourceFilesystem)
            else:
                dry_run_snaps = list(ctx.sourceSnapshots)
            dry_run_snaps.sort(key=lambda s: s.creation_epoch)
            if not dry_run_snaps:
                print('\n  No snapshots found on root dataset — cannot preview send command.')
                print('\n--- End Dry Run (no changes made) ---')
                sys.exit(0)
            latest_src = dry_run_snaps[-1].name
            if ctx.incrementalSnapName and latest_src == ctx.incrementalSnapName:
                print(f'\n  Latest source snapshot: {latest_src}')
                print(f'  Already up to date — the most recent source snapshot is the common base.')
                print(f'  No new snapshots to transfer.')
                print('\n--- End Dry Run (no changes made) ---')
                sys.exit(0)
            send_cmd = build_zfs_send_args(latest_src, ctx.incrementalSnapName, recursive=ctx.isRecursiveSnap, compressed=ctx.isCompressed, raw=ctx.isRaw, include_intermediates=ctx.includeIntermediateSnapshots)
            verbose_cmd = list(send_cmd)
            verbose_cmd.insert(2, '-nvP')
            print(f'\n  Latest source snapshot: {latest_src}')
            print(f"  Send command: {' '.join((shlex.quote(str(a)) for a in verbose_cmd))}")
            print(f'\n--- zfs send -nvP output ---', flush=True)
            if ctx.direction == 'pull':
                ssh_cmd = ['ssh'] + SSH_BASE_OPTS
                if str(ctx.sshPort) != '22':
                    ssh_cmd += ['-p', str(ctx.sshPort)]
                ssh_cmd.append(f'{ctx.remoteUser}@{ctx.remoteHost}')
                ssh_cmd.append(' '.join((shlex.quote(str(a)) for a in verbose_cmd)))
                run_cmd = ssh_cmd
            else:
                run_cmd = verbose_cmd
            total = 0
            returncode = -1
            try:
                proc = subprocess.Popen(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                proc_stdout = proc.stdout
                if proc_stdout is None:
                    raise RuntimeError("zfs send preview stdout pipe was not created")
                for line in proc_stdout:
                    line = line.rstrip('\n')
                    print(f'  {line}', flush=True)
                    stripped = line.strip()
                    if 'size' in stripped.lower():
                        m = re.search('\\bsize\\b\\s*=?\\s*(\\d+)', stripped, re.IGNORECASE)
                        if m:
                            total = int(m.group(1))
                    elif stripped.startswith('full') or stripped.startswith('incremental'):
                        parts = stripped.split('\t')
                        if parts:
                            try:
                                total += int(parts[-1])
                            except (ValueError, IndexError):
                                pass
                proc.wait(timeout=120)
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                print('\n  WARNING: zfs send -nvP timed out after 120s')
            if returncode != 0:
                print(f'\n  WARNING: zfs send -nvP exited with code {returncode}')
            if total > 0:
                if total >= 1073741824:
                    size_str = f'{total / 1073741824:.2f} GiB'
                elif total >= 1048576:
                    size_str = f'{total / 1048576:.2f} MiB'
                else:
                    size_str = f'{total} bytes'
                print(f'\n  Total estimated size: {size_str} ({total} bytes)')
        else:
            print('  WARNING: No source snapshots found — nothing to send.')
        print('\n--- End Dry Run (no changes made) ---')
        sys.exit(0)


def _create_and_transfer_snapshot(ctx: ReplicationRun):
    notifier.notify('STATUS=Creating source snapshot…')
    if ctx.direction == 'pull':
        ctx.newSnap = create_snapshot_remote(ctx.sourceFilesystem, ctx.isRecursiveSnap, ctx.taskName, ctx.customName, ctx.remoteUser, ctx.remoteHost, ctx.sshPort, tier_idx=ctx.tier_idx)
        (exists, dest_snap_name) = snapshot_exists_on_destination(ctx.destFilesystem, snapshot_suffix(ctx.newSnap), remote_user=None, remote_host=None, remote_port=ctx.sshPort)
        if exists:
            msg = f'Destination already has snapshot {dest_snap_name}. This typically means a prior receive completed or a timestamp reused. Refusing to overwrite an existing snapshot name.'
            notifier.notify(f'STATUS={msg}')
            print(msg)
            sys.exit(2)
        notifier.notify('STATUS=Pulling snapshot from remote source to local target…')
        if ctx.forceFullSend and (not ctx.incrementalSnapName) and ctx.destinationSnapshots:
            destroy_snapshots_with_progress(ctx.destinationSnapshots, ctx.destFilesystem)
        if not ctx.incrementalSnapName:
            _write_pending_full_send(ctx.taskName, ctx.newSnap, ctx.destFilesystem, ctx.direction, ctx.sourceFilesystem)
        send_snapshot_pull(remoteSnapName=ctx.newSnap, localRecvFs=ctx.destFilesystem, remoteBaseSnapName=ctx.incrementalSnapName, compressed=ctx.isCompressed, raw=ctx.isRaw, remoteHost=ctx.remoteHost, remoteSshPort=ctx.sshPort, remoteUser=ctx.remoteUser, mBufferSize=str(ctx.mBufferSize), mBufferUnit=ctx.mBufferUnit, forceOverwrite=ctx.forceOverwrite, recursive=ctx.isRecursiveSnap, transferMethod=ctx.transferMethod, recvDataPort=ctx.dataPort, include_intermediates=ctx.includeIntermediateSnapshots)
    else:
        ctx.newSnap = create_snapshot_local(ctx.sourceFilesystem, ctx.isRecursiveSnap, ctx.taskName, ctx.customName, tier_idx=ctx.tier_idx)
        (exists, dest_snap_name) = snapshot_exists_on_destination(ctx.destFilesystem, snapshot_suffix(ctx.newSnap), remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
        if exists:
            msg = f'Destination already has snapshot {dest_snap_name}. This typically means a prior receive completed or a timestamp reused. Refusing to overwrite an existing snapshot name.'
            notifier.notify(f'STATUS={msg}')
            print(msg)
            sys.exit(2)
        notifier.notify('STATUS=Sending snapshot to destination…')
        dbg(f"baseSnap={ctx.incrementalSnapName} baseDs={(dataset_of_snapshot(ctx.incrementalSnapName) if ctx.incrementalSnapName else '')} newSnap={ctx.newSnap} newDs={dataset_of_snapshot(ctx.newSnap)} recursive={ctx.isRecursiveSnap}")
        if ctx.forceFullSend and (not ctx.incrementalSnapName) and ctx.destinationSnapshots:
            if ctx.remoteHost and ctx.remoteUser:
                destroy_snapshots_with_progress(ctx.destinationSnapshots, ctx.destFilesystem, remote_user=ctx.remoteUser, remote_host=ctx.remoteHost, ssh_port=ctx.sshPort)
            else:
                destroy_snapshots_with_progress(ctx.destinationSnapshots, ctx.destFilesystem)
        if not ctx.incrementalSnapName:
            _write_pending_full_send(ctx.taskName, ctx.newSnap, ctx.destFilesystem, ctx.direction, ctx.sourceFilesystem)
        send_snapshot_push(ctx.newSnap, ctx.destFilesystem, ctx.incrementalSnapName, ctx.isCompressed, ctx.isRaw, ctx.remoteHost, ctx.sshPort, ctx.remoteUser, str(ctx.mBufferSize), ctx.mBufferUnit, ctx.forceOverwrite, ctx.transferMethod, recursive=ctx.isRecursiveSnap, recvDataPort=ctx.dataPort, include_intermediates=ctx.includeIntermediateSnapshots)
    safe_print('Snapshot transfer completed; applying snapshot tags and retention policy.')
    dbg('snapshot transfer completed; starting post-transfer processing')


def _tag_received_snapshot(ctx: ReplicationRun):
    snap_suf = snapshot_suffix(ctx.newSnap)
    if ctx.direction == 'pull':
        tag_received_snapshots(ctx.destFilesystem, snap_suf, ctx.taskName, tier_idx=ctx.tier_idx)
    else:
        tag_received_snapshots(ctx.destFilesystem, snap_suf, ctx.taskName, tier_idx=ctx.tier_idx, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost if ctx.remoteHost else None, remote_port=ctx.sshPort)
    notifier.notify('STATUS=Pruning old snapshots on source/destination…')
    ctx.current_pct = 0


def _apply_retention(ctx: ReplicationRun):
    if ctx.direction == 'pull':
        ctx.current_pct = prune_snapshots_by_retention(ctx.sourceFilesystem, ctx.taskName, ctx.sourceRetentionTime, ctx.sourceRetentionUnit, ctx.newSnap, ctx.remoteUser, ctx.remoteHost, ctx.sshPort, ctx.transferMethod, progress_base=ctx.current_pct, progress_span=50, tier_idx=ctx.tier_idx, custom_name=ctx.customName)
        ctx.current_pct = prune_snapshots_by_retention(ctx.destFilesystem, ctx.taskName, ctx.destinationRetentionTime, ctx.destinationRetentionUnit, ctx.newSnap, progress_base=ctx.current_pct, progress_span=50, tier_idx=ctx.tier_idx, custom_name=ctx.customName)
    else:
        ctx.current_pct = prune_snapshots_by_retention(ctx.sourceFilesystem, ctx.taskName, ctx.sourceRetentionTime, ctx.sourceRetentionUnit, ctx.newSnap, progress_base=ctx.current_pct, progress_span=50, tier_idx=ctx.tier_idx, custom_name=ctx.customName)
        ctx.current_pct = prune_snapshots_by_retention(ctx.destFilesystem, ctx.taskName, ctx.destinationRetentionTime, ctx.destinationRetentionUnit, ctx.newSnap, ctx.remoteUser if ctx.remoteHost else None, ctx.remoteHost if ctx.remoteHost else None, ctx.sshPort, ctx.transferMethod, progress_base=ctx.current_pct, progress_span=50, tier_idx=ctx.tier_idx, custom_name=ctx.customName)
    final_pct = min(100, int(ctx.current_pct))
    schedule_intervals = ctx.schedule_data.get('intervals') if ctx.schedule_data else None
    if ctx.tier_idx is not None and isinstance(schedule_intervals, list):
        _unit_secs = {'minutes': 60, 'hours': 3600, 'days': 86400, 'weeks': 604800, 'months': 2592000, 'years': 31536000}
        max_src_secs = 0
        max_src_time = 0
        max_src_unit = ''
        max_dst_secs = 0
        max_dst_time = 0
        max_dst_unit = ''
        for iv in schedule_intervals:
            iv_ret = iv.get('retention') or {}
            sr = iv_ret.get('source') or {}
            dr = iv_ret.get('destination') or {}
            st = sr.get('retentionTime', 0) or 0
            su = sr.get('retentionUnit', '')
            dt_val = dr.get('retentionTime', 0) or 0
            du = dr.get('retentionUnit', '')
            s_secs = int(st) * _unit_secs.get(su, 0)
            d_secs = int(dt_val) * _unit_secs.get(du, 0)
            if s_secs > max_src_secs:
                max_src_secs = s_secs
                max_src_time = st
                max_src_unit = su
            if d_secs > max_dst_secs:
                max_dst_secs = d_secs
                max_dst_time = dt_val
                max_dst_unit = du
        if max_src_secs > 0:
            if ctx.direction == 'pull':
                prune_snapshots_by_retention(ctx.sourceFilesystem, ctx.taskName, max_src_time, max_src_unit, ctx.newSnap, ctx.remoteUser, ctx.remoteHost, ctx.sshPort, ctx.transferMethod, progress_base=0, progress_span=0, tier_idx=None, custom_name=ctx.customName)
            else:
                prune_snapshots_by_retention(ctx.sourceFilesystem, ctx.taskName, max_src_time, max_src_unit, ctx.newSnap, progress_base=0, progress_span=0, tier_idx=None, custom_name=ctx.customName)
        if max_dst_secs > 0:
            if ctx.direction == 'pull':
                prune_snapshots_by_retention(ctx.destFilesystem, ctx.taskName, max_dst_time, max_dst_unit, ctx.newSnap, progress_base=0, progress_span=0, tier_idx=None, custom_name=ctx.customName)
            else:
                prune_snapshots_by_retention(ctx.destFilesystem, ctx.taskName, max_dst_time, max_dst_unit, ctx.newSnap, ctx.remoteUser if ctx.remoteHost else None, ctx.remoteHost if ctx.remoteHost else None, ctx.sshPort, ctx.transferMethod, progress_base=0, progress_span=0, tier_idx=None, custom_name=ctx.customName)
    notifier.notify('STATUS=ZFS replication task completed. 100% complete')
    _clear_pending_full_send(ctx.taskName)
    try:
        lastrun_path = f'/etc/systemd/system/houston_scheduler_ZfsReplicationTask_{ctx.taskName}.lastrun'
        with open(lastrun_path, 'w') as f:
            f.write(str(int(time.time())))
    except Exception as e:
        dbg(f'WARNING: failed to write lastrun file: {e}')
    safe_print(f'ZFS replication task completed successfully: {ctx.sourceFilesystem} -> {ctx.destFilesystem}')
    dbg('=== task completed successfully ===')


def run_replication(ctx: ReplicationRun):
    _initialize_run(ctx)
    _load_snapshot_inventory(ctx)
    if _recover_pending_full_send(ctx):
        return
    if _resume_interrupted_receive(ctx):
        return
    _announce_dry_run(ctx)
    _plan_send(ctx)
    _report_dry_run(ctx)
    _create_and_transfer_snapshot(ctx)
    _tag_received_snapshot(ctx)
    _apply_retention(ctx)


def handle_failure(ctx: ReplicationRun, error):
    srcPool = os.environ.get('zfsRepConfig_sourceDataset_pool', '')
    srcDs = os.environ.get('zfsRepConfig_sourceDataset_dataset', '')
    dstPool = os.environ.get('zfsRepConfig_destDataset_pool', '')
    dstDs = os.environ.get('zfsRepConfig_destDataset_dataset', '')
    ctx.sourceFilesystem = join_zfs_path(srcPool, srcDs)
    receivingFilesystem = join_zfs_path(dstPool, dstDs)
    try:
        resume_token = get_receive_resume_token(receivingFilesystem, remote_user=ctx.remoteUser if ctx.remoteHost else None, remote_host=ctx.remoteHost or None, remote_port=ctx.sshPort)
        print(f"receive_resume_token for {receivingFilesystem}: {resume_token or '-'}")
    except Exception:
        print(f'receive_resume_token for {receivingFilesystem}: <error fetching token>')
    tb = traceback.format_exc()
    safe_print(tb)
    notifier.notify('STATUS=ZFS replication task failed.')
    email_error_message = f'ZFS replication failed while sending snapshot {ctx.newSnap} from {ctx.sourceFilesystem} to {receivingFilesystem}Error: {str(error)}'
    send_houston_notification({'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'event': 'zfs_replication_failed', 'subject': 'ZFS Replication Failed', 'email_message': email_error_message, 'fileSystem': ctx.sourceFilesystem, 'snapShot': ctx.newSnap, 'replicationDestination': receivingFilesystem, 'severity': 'warning', 'errors': str(error)})
    print(f'Exception: {error}')
    sys.exit(1)
