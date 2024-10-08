import { ParameterNode, StringParameter, BoolParameter, IntParameter, ObjectParameter, } from "./Parameters";

export class CloudSyncProvider {
    name: string;
    type: string;
    parameters: CloudAuthParameterOptions;

    constructor(name: string, type: string, parameters: CloudAuthParameterOptions) {
        this.name = name;
        this.type = type;
        this.parameters = parameters;
    }
}

export const cloudSyncProviders: { [key: string]: CloudSyncProvider } = {
    //'s3', 'b2', 'dropbox', 'drive', 'google cloud storage', 'azureblob', 'onedrive'


    "s3-AWS": new CloudSyncProvider("Amazon S3", "s3", { provider: "AWS", access_key_id: "", secret_access_key: "", region: "", endpoint: "" }),
    "s3-Wasabi": new CloudSyncProvider("Wasabi", "s3", { provider: "Wasabi", access_key_id: "", secret_access_key: "", region: "", endpoint: "" }),
    "b2": new CloudSyncProvider("Backblaze B2", "b2", { account: "", key: "", hard_delete: false }),
    "dropbox": new CloudSyncProvider("Dropbox", "dropbox", { account: "", token: {} }),
    "drive": new CloudSyncProvider("Google Drive", "drive", { account: "", token: {}, scope: "" }),
    "onedrive": new CloudSyncProvider("Microsoft Onedrive", "onedrive", { client_id: "", client_secret: "", region: "", token: {} }),
    "google cloud storage": new CloudSyncProvider("Google Cloud", "google cloud storage", { client_id: "", client_secret: "", token: {}, scope: "" }),
    "azureblob": new CloudSyncProvider("Azure Blob", "azure-blob", { provider: "azure" , account: "", key: ""}),
};

interface CloudAuthParameterOptions {
    client_id?: string;
    client_secret?: string;
    chunk_size?: string;
    service_account_file?: string;
    use_trash?: boolean;
    account?: string;
    key?: string;
    hard_delete?: boolean;
    token?: {};
    scope?: string;
    provider?: string;
    access_key_id?: string;
    secret_access_key?: string;
    region?: string;
    endpoint?: string;
    customParameters?: { [key: string]: any };  // <- New addition to allow arbitrary parameters
}


export class CloudAuthParameter extends ParameterNode implements ParameterNodeType {
    constructor(label: string, key: string, options: CloudAuthParameterOptions = {}) {
        super(label, key);

        // Function to check if a child parameter with the same key already exists
        const findChild = (key: string) => {
            return this.children.find(child => child.key === key);
        };

        // Dynamically add parameters from options
        Object.entries(options).forEach(([key, value]) => {
            let existingChild = findChild(key);

            if (existingChild) {
                // If the parameter already exists, update its value
                if (existingChild instanceof StringParameter) {
                    existingChild.value = value as string;
                } else if (existingChild instanceof BoolParameter) {
                    existingChild.value = value as boolean;
                } else if (existingChild instanceof ObjectParameter) {
                    existingChild.value = value;
                }
            } else {
                // If the parameter does not exist, add it as a new child
                if (typeof value === 'string') {
                    this.addChild(new StringParameter(key, key, value));
                } else if (typeof value === 'boolean') {
                    this.addChild(new BoolParameter(key, key, value));
                } else if (typeof value === 'object') {
                    this.addChild(new ObjectParameter(key, key, value));
                }
            }
        });
    }
}


export function createCloudAuthParameter(type: string, s3_provider?: string): CloudAuthParameter {
    if (type === 's3') {
        // Ensure s3_provider is defined and use it to look up the correct provider in cloudSyncProviders
        const providerKey = `s3-${s3_provider}`;
        const provider = cloudSyncProviders[providerKey];

        if (!provider) {
            throw new Error(`Unsupported S3 provider: ${s3_provider}`);
        }
        return new CloudAuthParameter("Auth", "auth", provider.parameters);
    } else {
        const provider = cloudSyncProviders[type];
        if (!provider) {
            throw new Error(`Unsupported remote type: ${type}`);
        }
        return new CloudAuthParameter("Auth", "auth", provider.parameters);
    }
}


export class CloudSyncRemote extends ParameterNode implements CloudSyncRemoteType {
    name: string;
    type: string;
    provider: CloudSyncProvider;
    authParams: CloudAuthParameter;

    constructor(name: string, type: string, authParams: CloudAuthParameter, provider: CloudSyncProvider) {
        super(`RemoteName-${name}`, `remoteType-${type}`);
        this.name = name;
        this.type = type;
        this.authParams = authParams;
        this.provider = provider;
    }
}