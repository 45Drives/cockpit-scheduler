import { server, unwrap, Command } from '@45drives/houston-common-lib';
import { CloudSyncProvider, CloudSyncRemote, cloudSyncProviders, CloudAuthParameter} from "./CloudSync";
//@ts-ignore
import get_cloud_sync_remotes_script from '../scripts/get-rclone-remotes.py?raw';
//@ts-ignore
import create_cloud_sync_remote_script from '../scripts/create-rclone-remote.py?raw';
//@ts-ignore
import delete_cloud_sync_remote_script from '../scripts/delete-rclone-remote.py?raw';
//@ts-ignore
import update_cloud_sync_remote_script from '../scripts/update-rclone-remote.py?raw';

const textDecoder = new TextDecoder('utf-8');

async function runCommand(
    argv: string[],
    opts: { superuser?: 'try' | 'require' } = { superuser: 'try' }
): Promise<{ stdout: string; stderr: string; exitStatus: number }> {
    const proc = await unwrap(
        server.execute(new Command(argv, opts))
    );

    const rawStdout: any = proc.stdout;
    const rawStderr: any = proc.stderr;

    const stdout =
        rawStdout instanceof Uint8Array
            ? textDecoder.decode(rawStdout)
            : String(rawStdout ?? '');

    const stderr =
        rawStderr instanceof Uint8Array
            ? textDecoder.decode(rawStderr)
            : String(rawStderr ?? '');

    return { stdout, stderr, exitStatus: proc.exitStatus };
}

export class RemoteManager implements RemoteManagerType {
    cloudSyncRemotes: CloudSyncRemote[];

    constructor(cloudSyncRemotes: CloudSyncRemote[]) {
        this.cloudSyncRemotes = cloudSyncRemotes;
    }

    async getRemotes() {
        this.cloudSyncRemotes.splice(0, this.cloudSyncRemotes.length);  // Clear current remotes
        try {
            this.cloudSyncRemotes.splice(0, this.cloudSyncRemotes.length);
            try {
                const cockpitUser = await (window as any).cockpit.user();
                const username: string = cockpitUser?.name;

                const args = ['/usr/bin/env', 'python3', '-c', get_cloud_sync_remotes_script];
                if (username) { args.push('--user', username); }

                const { stdout: remotesOutput } = await runCommand(args, { superuser: 'try' });

                const remotesData = JSON.parse(remotesOutput);  // Parse the remotes

                if (!Array.isArray(remotesData)) {
                    console.error("Unexpected remotes data format:", remotesData);
                    return;
                }

                remotesData.forEach(remote => {
                    if (!remote || !remote.type || !remote.parameters) {
                        console.error("Malformed remote object:", remote);
                        return;
                    }

                    let provider = cloudSyncProviders[remote.type];

                    // Handle 's3' provider type, which has specific subtypes
                    if (remote.type === 's3' && remote.parameters.provider) {
                        const providerKey = `s3-${remote.parameters.provider}`;
                        provider = cloudSyncProviders[providerKey];
                    }

                    if (!provider) {
                        console.error(`Unsupported remote type or provider: ${remote.type}`);
                        return;
                    }

                    // Deep copy providerParams to authParams
                    const authParams = JSON.parse(JSON.stringify(provider.providerParams));

                    // Update authParams with actual values from remote.parameters
                    for (const [key, value] of Object.entries(remote.parameters)) {
                        // Check if the parameter exists in the provider-defined parameters
                        const param = authParams.parameters[key];

                        if (param) {
                            // Update the value based on the type
                            param.value = value;
                        } else {
                            // Add dynamically if not predefined in provider
                            authParams.parameters[key] = { value, type: typeof value };
                        }
                    }

                    // Create a new CloudSyncRemote instance for each remote
                    const newRemote = new CloudSyncRemote(
                        remote.name,
                        remote.type,
                        authParams,
                        provider
                    );

                    // Add the new remote to the list of cloud sync remotes
                    this.cloudSyncRemotes.push(newRemote);
                });
            } catch (error) {
                console.error("Error fetching remotes:", error);
            }
        } catch (e) {
            console.error("Error fetching remotes:", e);
        }
    }

    async getRemoteByName(remoteName: string): Promise<CloudSyncRemote | null> {
        const remote = this.cloudSyncRemotes.find(remote => remote.name === remoteName);

        if (remote) {
            return remote;
        } else {
            console.error(`Remote with name "${remoteName}" not found`);
            return null;
        }
    }

    async createRemote(name: string, type: string, parameters: any): Promise<CloudSyncRemote> {
        let provider: CloudSyncProvider;
        if (type === 's3') {
            provider = cloudSyncProviders[`s3-${parameters.provider}`];

            if (!provider) {
                throw new Error(`Unsupported S3 provider: ${parameters.provider}`);
            }

        } else {
            provider = cloudSyncProviders[type];

            if (!provider) {
                throw new Error(`Unsupported remote type: ${type}`);
            }
        }

        const authParams: CloudAuthParameter = parameters;

        const remote = new CloudSyncRemote(name, type, authParams, provider);
        const remoteJsonString = JSON.stringify(remote);

        const cockpitUser = await (window as any).cockpit.user();
        const username: string = cockpitUser?.name;

        const args = ['/usr/bin/env', 'python3', '-c', create_cloud_sync_remote_script,
            '--data', remoteJsonString];
        if (username) { args.push('--user', username); }

        await runCommand(args, { superuser: 'try' });

        this.cloudSyncRemotes.push(remote);
        return remote;
    }


    async editRemote(oldName: string, newName: string, newType: string, newParams: any) {
        let provider;

        if (newType === 's3') {
            provider = cloudSyncProviders[`s3-${newParams.parameters.provider.value}`];

            if (!provider) {
                throw new Error(`Unsupported S3 provider: ${newParams.parameters.provider.value}`);
            }
        } else {
            provider = cloudSyncProviders[newType];

            if (!provider) {
                throw new Error(`Unsupported remote type: ${newType}`);
            }
        }

        const authParams = newParams.parameters;
        const remote = new CloudSyncRemote(newName, newType, authParams, provider);
        const remoteJson = JSON.stringify(remote);

        const cockpitUser = await (window as any).cockpit.user();
        const username: string = cockpitUser?.name;

        const args = ['/usr/bin/env', 'python3', '-c', update_cloud_sync_remote_script,
            '--old_name', oldName, '--data', remoteJson];
        if (username) { args.push('--user', username); }

        await runCommand(args, { superuser: 'try' });

        const i = this.cloudSyncRemotes.findIndex(r => r.name === oldName);
        if (i !== -1) this.cloudSyncRemotes.splice(i, 1, remote);
        else this.cloudSyncRemotes.push(remote);
        return remote;
    }

    async deleteRemote(remoteName: string) {
        // Remove the remote from the list
        const i = this.cloudSyncRemotes.findIndex(r => r.name === remoteName);
        if (i !== -1) this.cloudSyncRemotes.splice(i, 1);

        const cockpitUser = await (window as any).cockpit.user();
        const username: string = cockpitUser?.name;

        const args = ['/usr/bin/env', 'python3', '-c', delete_cloud_sync_remote_script, remoteName];
        if (username) { args.push('--user', username); }

        await runCommand(args, { superuser: 'try' });

        return true;
    }

}