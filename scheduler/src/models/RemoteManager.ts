import { ref } from 'vue';
import { BetterCockpitFile, errorString, useSpawn } from '@45drives/cockpit-helpers';
import { CloudSyncProvider, CloudSyncRemote, createCloudAuthParameter, cloudSyncProviders, CloudAuthParameter} from "./CloudSync";
import { ParameterNode, StringParameter, SelectionParameter, IntParameter, BoolParameter, ObjectParameter } from './Parameters';
import { createStandaloneTask, createTaskFiles, createScheduleForTask, removeTask, runTask, formatTemplateName } from '../composables/utility';
//@ts-ignore
import get_rclone_remotes_script from '../scripts/get-rclone-remotes.py?raw';


export class RemoteManager implements RemoteManagerType {
    cloudSyncRemotes: CloudSyncRemote[];

    constructor(cloudSyncRemotes: CloudSyncRemote[]) {
        this.cloudSyncRemotes = cloudSyncRemotes;
    }

    /* async getRemotes() {
        this.cloudSyncRemotes.splice(0, this.cloudSyncRemotes.length);
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_rclone_remotes_script], { superuser: 'try' });
            const remotesOutput = (await state.promise()).stdout;
            console.log('Raw remotesOutput:', remotesOutput);
            const remotesData = JSON.parse(remotesOutput);

            remotesData.forEach(remote => {
                // Create a new CloudSyncRemote instance for each remote
                const newRemote = new CloudSyncRemote(
                    remote.name,            // Remote name
                    remote.type,            // Remote type (e.g., drive, s3, dropbox)
                    remote.parameters       // Remote parameters (e.g., token, account, key, etc.)
                );

                // Add the new remote to the list of cloud sync remotes
                this.cloudSyncRemotes.push(newRemote);
            });

        } catch (state) {
            console.error(errorString(state));
            return null;
        }
    } */


  /*   async getRemotes() {
        this.cloudSyncRemotes.splice(0, this.cloudSyncRemotes.length);
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_rclone_remotes_script], { superuser: 'try' });
            const remotesOutput = (await state.promise()).stdout;
            console.log('Raw remotesOutput:', remotesOutput);
            const remotesData = JSON.parse(remotesOutput);

            remotesData.forEach(remote => {
                // Parse the authParams using the createCloudAuthParameter function
                // This assumes that remote.type has a corresponding provider in cloudSyncProviders
                const authParams = createCloudAuthParameter(remote.type);

                // Map the authParams from JSON to their respective ParameterNode subclasses
                Object.entries(remote.authParams).forEach(([key, value]) => {
                    if (authParams.hasOwnProperty(key)) {
                        let param = authParams[key]; // Get the existing parameter node
                        if (param instanceof ObjectParameter && typeof value === 'object') {
                            Object.entries(value!).forEach(([childKey, childValue]) => {
                                param.addChild(new StringParameter(childKey, childKey, childValue));
                            });
                        } else {
                            // For simple types, directly set the value
                            param.value = value; // This is illustrative; actual implementation may vary based on your classes
                        }
                    }
                });

                // Create a new CloudSyncRemote instance for each remote
                const newRemote = new CloudSyncRemote(
                    remote.name,            // Remote name
                    remote.type,            // Remote type (e.g., drive, s3, dropbox)
                    authParams              // Remote parameters structured as ParameterNodes
                );

                // Add the new remote to the list of cloud sync remotes
                this.cloudSyncRemotes.push(newRemote);
            });

        } catch (state) {
            console.error(errorString(state));
            return null;
        }
    }
 */

    async getRemotes() {
        this.cloudSyncRemotes.splice(0, this.cloudSyncRemotes.length);  // Clear current remotes
        try {
            const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_rclone_remotes_script], { superuser: 'try' });
            const remotesOutput = (await state.promise()).stdout;
            console.log('Raw remotesOutput:', remotesOutput);

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

                let authParams;
                let provider: CloudSyncProvider;

                // Handle S3 remotes by checking the provider
                if (remote.type === 's3') {
                    const providerKey = `s3-${remote.parameters.provider}`;  // Default to AWS if provider is not specified
                    provider = cloudSyncProviders[providerKey];

                    if (!provider) {
                        console.error(`Unsupported S3 provider: ${remote.parameters.provider}`);
                        return;
                    }

                    // Create auth parameters for S3
                    authParams = createCloudAuthParameter(remote.type, remote.parameters.provider);
                } else {
                    provider = cloudSyncProviders[remote.type];

                    if (!provider) {
                        console.error(`Unsupported remote type: ${remote.type}`);
                        return;
                    }

                    // Create auth parameters for other providers
                    authParams = createCloudAuthParameter(remote.type);
                }

                // Dynamically assign each key/value from remote.parameters into authParams
                Object.entries(remote.parameters).forEach(([key, value]) => {
                    let existingChild = authParams.children.find(child => child.key === key);

                    if (existingChild) {
                        // If a parameter with the same key exists, update its value
                        if (existingChild instanceof StringParameter && typeof value === 'string') {
                            existingChild.value = value as string;
                        } else if (existingChild instanceof BoolParameter && typeof value === 'boolean') {
                            existingChild.value = value as boolean;
                        } else if (existingChild instanceof ObjectParameter && typeof value === 'object') {
                            existingChild.value = value as object;
                        }
                    } else {
                        // Dynamically add new parameters not predefined
                        if (typeof value === 'string') {
                            authParams.addChild(new StringParameter(key, key, value));
                        } else if (typeof value === 'boolean') {
                            authParams.addChild(new BoolParameter(key, key, value));
                        } else if (typeof value === 'object') {
                            authParams.addChild(new ObjectParameter(key, key, value!));
                        }
                    }
                });

                // Create a new CloudSyncRemote instance for each remote
                const newRemote = new CloudSyncRemote(
                    remote.name,            // Remote name
                    remote.type,            // Remote type (e.g., drive, s3, dropbox)
                    authParams,             // Remote parameters structured as ParameterNodes
                    provider                // CloudSyncProvider object containing provider info
                );

                // Add the new remote to the list of cloud sync remotes
                this.cloudSyncRemotes.push(newRemote);
            });

        } catch (error) {
            console.error("Error fetching remotes:", error);
            return null;
        }
    }


    createRemote(name: string, type: string, providerKey?: string): CloudSyncRemote {
        let authParams: CloudAuthParameter;
        let provider: CloudSyncProvider;

        // Handle the case where the type is 's3' and provider is passed
        if (type === 's3') {
            if (!providerKey) {
                throw new Error('Provider key is required for S3 remote');
            }

            provider = cloudSyncProviders[`s3-${providerKey}`];

            if (!provider) {
                throw new Error(`Unsupported S3 provider: ${providerKey}`);
            }

            // Create auth parameters for S3 provider
            authParams = createCloudAuthParameter(type, providerKey);
        } else {
            provider = cloudSyncProviders[type];

            if (!provider) {
                throw new Error(`Unsupported remote type: ${type}`);
            }

            // Create auth parameters for other providers
            authParams = createCloudAuthParameter(type);
        }

        // Create the new CloudSyncRemote with the appropriate provider and authParams
        const remote = new CloudSyncRemote(name, type, authParams, provider);

        // Add the new remote to the list
        this.cloudSyncRemotes.push(remote);

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