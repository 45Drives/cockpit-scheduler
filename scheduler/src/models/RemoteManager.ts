import { CloudSyncRemote, createCloudAuthParameter} from "./CloudSync";

export class RemoteManager {
    cloudSyncRemotes: CloudSyncRemote[];

    constructor() {
        this.cloudSyncRemotes = [];
    }

    getRemotes(): CloudSyncRemote[] {
        return this.cloudSyncRemotes;
    }

    createRemote(label: string, key: string, type: string): CloudSyncRemote {
        const authParams = createCloudAuthParameter(type);
        const remote = new CloudSyncRemote(label, key, type, authParams);
        this.cloudSyncRemotes.push(remote);
        return remote;
    }

    editRemote(key: string, newLabel: string, newType: string): CloudSyncRemote | undefined {
        const remote = this.cloudSyncRemotes.find(r => r.key === key);
        if (remote) {
            remote.label = newLabel;
            const typeParam = remote.children.find(c => c.key === 'type');
            if (typeParam) {
                typeParam.value = newType;
            }

            const newAuthParam = createCloudAuthParameter(newType);
            remote.children = remote.children.map(c => c.key === 'auth' ? newAuthParam : c);
        }
        return remote;
    }

    deleteRemote(key: string): boolean {
        const index = this.cloudSyncRemotes.findIndex(r => r.key === key);
        if (index !== -1) {
            this.cloudSyncRemotes.splice(index, 1);
            return true;
        }
        return false;
    }

    authorizeRemote(key: string): boolean {
        // Implement authorization logic
        const remote = this.cloudSyncRemotes.find(r => r.key === key);
        if (remote) {
            // Perform authorization
            return true;
        }
        return false;
    }
}