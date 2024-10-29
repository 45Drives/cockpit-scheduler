import { ref } from 'vue';
import { BetterCockpitFile, errorString, useSpawn } from '@45drives/cockpit-helpers';
import { CloudSyncProvider, CloudSyncRemote, cloudSyncProviders, CloudAuthParameter, CloudSyncParameter} from "./CloudSync";
import { ParameterNode, StringParameter, SelectionParameter, IntParameter, BoolParameter, ObjectParameter } from './Parameters';
import { createStandaloneTask, createTaskFiles, createScheduleForTask, removeTask, runTask, formatTemplateName } from '../composables/utility';
//@ts-ignore
import get_rclone_remotes_script from '../scripts/get-rclone-remotes.py?raw';
//@ts-ignore
import create_rclone_remote_script from '../scripts/create-rclone-remote.py?raw';

export class RemoteManager implements RemoteManagerType {
    cloudSyncRemotes: CloudSyncRemote[];

    constructor(cloudSyncRemotes: CloudSyncRemote[]) {
        this.cloudSyncRemotes = cloudSyncRemotes;
    }

 
    async getRemotes() {
        this.cloudSyncRemotes.splice(0, this.cloudSyncRemotes.length);  // Clear current remotes
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_rclone_remotes_script], { superuser: 'try' });
            const remotesOutput = (await state.promise()).stdout;

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

                let provider: CloudSyncProvider;

                // Determine the provider based on remote type or specific provider key for 's3'
                if (remote.type === 's3') {
                    const providerKey = `s3-${remote.parameters.provider}`;
                    provider = cloudSyncProviders[providerKey];
                } else {
                    provider = cloudSyncProviders[remote.type];
                }

                if (!provider) {
                    console.error(`Unsupported remote type or provider: ${remote.type}`);
                    return;
                }

                // Create a deep copy of provider parameters for this remote
                const authParams: CloudAuthParameter = JSON.parse(JSON.stringify(provider.parameters));

                // Dynamically update each key/value from remote.parameters
                Object.entries(remote.parameters).forEach(([key, value]) => {
                    const param = authParams.parameters[key];

                    if (param) {
                        // If the parameter exists, update its value
                        if (param.type === 'string' && typeof value === 'string') {
                            param.value = value;
                        } else if (param.type === 'bool' && typeof value === 'boolean') {
                            param.value = value;
                        } else if (param.type === 'int' && typeof value === 'number') {
                            param.value = value;
                        } else if (param.type === 'object' && typeof value === 'object') {
                            param.value = value;
                        }
                    } else {
                        // If the parameter is not predefined, add it dynamically
                        authParams.parameters[key] = { value, type: typeof value } as CloudSyncParameter;
                    }
                });

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



    async createRemote(name: string, type: string, parameters: any): Promise<CloudSyncRemote> {
        let provider: CloudSyncProvider;
        // Handle the case where the type is 's3' and provider is passed
        if (type === 's3') {
           
            provider = cloudSyncProviders[`s3-${parameters.parameters.provider.value}`];

            if (!provider) {
                throw new Error(`Unsupported S3 provider: ${parameters.parameters.provider.value}`);
            }

        } else {
            provider = cloudSyncProviders[type];

            if (!provider) {
                throw new Error(`Unsupported remote type: ${type}`);
            }
        }

        const authParams: CloudAuthParameter = parameters;
        // console.log('authParams', authParams);

        // Create the new CloudSyncRemote with the appropriate provider and authParams
        const remote = new CloudSyncRemote(name, type, authParams, provider);
        // console.log('newRemote:', remote);

        // Convert CloudSyncRemote object to JSON string
        const remoteJsonString = JSON.stringify(remote);
        console.log('remoteJsonString:', remoteJsonString);

        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', create_rclone_remote_script, '--data', remoteJsonString], { superuser: 'try' });
            const newRemoteOutput = (await state.promise()).stdout;

            console.log('newRemoteOutput:', newRemoteOutput);
            this.cloudSyncRemotes.push(remote);

        } catch (error) {
            console.error("Error fetching remotes:", error);
        }

        return remote;
    }


    editRemote(newName: string, newType: string): CloudSyncRemote | undefined {
        //IMPLEMENT PROPERLY
        const remote = this.cloudSyncRemotes.find(r => r.name);
        // if (remote) {
        //     remote.name = newName;
        //     remote.type = newType;
        //     remote.authParams = createCloudAuthParameter(newType); // Simplified to directly set the new params
        // }
        return remote;
    }

    deleteRemote(name: string): boolean {
    //IMPLEMENT PROPERLY
        // const index = this.cloudSyncRemotes.findIndex(r => r.name === name);
        // if (index !== -1) {
        //     this.cloudSyncRemotes.splice(index, 1);
        //     return true;
        // }
        return false;
    }

    authorizeRemote(name: string): boolean {
        // Authorization logic
        return true;
    }
}