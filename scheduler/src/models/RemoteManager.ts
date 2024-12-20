import { ref } from 'vue';
import { BetterCockpitFile, errorString, useSpawn } from '@45drives/cockpit-helpers';
import { CloudSyncProvider, CloudSyncRemote, cloudSyncProviders, CloudAuthParameter, CloudSyncParameter} from "./CloudSync";
import { ParameterNode, StringParameter, SelectionParameter, IntParameter, BoolParameter, ObjectParameter } from './Parameters';
import { createStandaloneTask, createTaskFiles, createScheduleForTask, removeTask, runTask, formatTemplateName } from '../composables/utility';
//@ts-ignore
import get_cloud_sync_remotes_script from '../scripts/get-rclone-remotes.py?raw';
//@ts-ignore
import create_cloud_sync_remote_script from '../scripts/create-rclone-remote.py?raw';
//@ts-ignore
import delete_cloud_sync_remote_script from '../scripts/delete-rclone-remote.py?raw';
//@ts-ignore
import update_cloud_sync_remote_script from '../scripts/update-rclone-remote.py?raw';

export class RemoteManager implements RemoteManagerType {
    cloudSyncRemotes: CloudSyncRemote[];

    constructor(cloudSyncRemotes: CloudSyncRemote[]) {
        this.cloudSyncRemotes = cloudSyncRemotes;
    }

    async getRemotes() {
        this.cloudSyncRemotes.splice(0, this.cloudSyncRemotes.length);  // Clear current remotes
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_cloud_sync_remotes_script], { superuser: 'try' });
            const remotesOutput = (await state.promise()).stdout;

            const remotesData = JSON.parse(remotesOutput);  // Parse the remotes
            console.log('remotesData JSON:', remotesData);

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
    }

    async getRemoteByName(remoteName: string): Promise<CloudSyncRemote | null> {
        // await this.getRemotes();  // Ensure remotes are loaded

        // Find the remote by name
        const remote = this.cloudSyncRemotes.find(remote => remote.name === remoteName);

        if (remote) {
            console.log(`Found remote: ${remote.name}`);
            return remote;
        } else {
            console.error(`Remote with name "${remoteName}" not found`);
            return null;
        }
    }

    async createRemote(name: string, type: string, parameters: any): Promise<CloudSyncRemote> {
        let provider: CloudSyncProvider;
        // Handle the case where the type is 's3' and provider is passed
        if (type === 's3') {
            console.log('parameters:', parameters)
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
        console.log('authParams', authParams);

        // Create the new CloudSyncRemote with the appropriate provider and authParams
        const remote = new CloudSyncRemote(name, type, authParams, provider);
        console.log('newRemote:', remote);

        // Convert CloudSyncRemote object to JSON string
        const remoteJsonString = JSON.stringify(remote);
        // console.log('remoteJsonString:', remoteJsonString);

        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', create_cloud_sync_remote_script, '--data', remoteJsonString], { superuser: 'try' });
            const newRemoteOutput = (await state.promise()).stdout;

            console.log('newRemoteOutput:', newRemoteOutput);
            this.cloudSyncRemotes.push(remote);

        } catch (error) {
            console.error("Error fetching remotes:", error);
        }

        return remote;
    }


    async editRemote(oldName: string, newName: string, newType: string, newParams: any) {
        let provider;
        console.log(`oldName: ${oldName}, newName: ${newName}, newType: ${newType}`);
        console.log('newParams:', newParams);
        // Handle the case where the type is 's3' and provider is passed
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
        console.log('newly edited remote:', remote);
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', update_cloud_sync_remote_script, 
                '--old_name', oldName, '--data', remoteJson
            ], { superuser: 'try' });

            const editRemoteOutput = (await state.promise()).stdout;
            console.log('editRemoteOutput:', editRemoteOutput);

            // Update the local list of remotes with the new data
            const index = this.cloudSyncRemotes.findIndex(remote => remote.name === oldName);
            if (index !== -1) {
                this.cloudSyncRemotes.splice(index, 1, remote);  // Replace the old remote with the updated one
            } else {
                console.warn(`Remote with name '${oldName}' not found in cloudSyncRemotes list`);
                this.cloudSyncRemotes.push(remote);  // Add the new remote if old one was not found
            }
        } catch (error) {
            console.error("Error editing remote:", error);
        }

        return remote;
    }

    async deleteRemote(remoteName) {
        // Remove the remote from the list
        const index = this.cloudSyncRemotes.findIndex(r => r.name === remoteName);
        if (index !== -1) {
            this.cloudSyncRemotes.splice(index, 1);
        } else {
            console.error("Remote not found in the array:", remoteName);
            return false;
        }

        // Run the Python script to delete the remote from the rclone config
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', delete_cloud_sync_remote_script, remoteName], { superuser: 'try' });
            const deleteOutput = (await state.promise()).stdout;

            console.log("Delete script output:", deleteOutput);
            return true;
        } catch (error) {
            console.error("Error deleting remote:", error);
            return false;
        }
    }

}