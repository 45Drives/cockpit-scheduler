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
    "backblaze-b2": new CloudSyncProvider("Backblaze B2", "b2", { account: "", key: "", hard_delete: false }),
    "dropbox": new CloudSyncProvider("Dropbox", "dropbox", { account: "", token: {} }),
    "google-drive": new CloudSyncProvider("Google Drive", "drive", { account: "", token: {}, scope: "" }),
    "amazon-s3": new CloudSyncProvider("Amazon S3", "s3", { provider: "aws", access_key_id: "", secret_access_key: "", region: "", endpoint: "" }),
    "azure-blob": new CloudSyncProvider("Azure Blob", "azure-blob", { provider: "azure" , account: "", key: ""}),
    "wasabi": new CloudSyncProvider("Wasabi", "wasabi", { provider: "aws", access_key_id: "", secret_access_key: "", region: "", endpoint: "" }),
    
    // "aws": new CloudSyncProvider("Amazon Web Services", "aws", { account: "", key: "", access_key_id: "", secret_access_key: "", region: "", endpoint: "" }),
    // "gcp": new CloudSyncProvider("Google Cloud Platform", "gcp", { account: "", key: "", token: {}, scope: "" }),
    // "azure": new CloudSyncProvider("Microsoft Azure", "azure", { account: "", key: "", provider: "" }),
};

interface CloudAuthParameterOptions {
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

}

export class CloudAuthParameter extends ParameterNode implements ParameterNodeType {
    constructor(label: string, key: string, options: CloudAuthParameterOptions = {}) {
        super(label, key);

        if (options.account !== undefined) {
            this.addChild(new StringParameter("Account", "account", options.account));
        }

        if (options.key !== undefined) {
            this.addChild(new StringParameter("Key", "key", options.key));
        }

        if (options.hard_delete !== undefined) {
            this.addChild(new BoolParameter("Hard Delete", "hard_delete", options.hard_delete));
        }

        if (options.token !== undefined) {
            this.addChild(new ObjectParameter("Token", "token", options.token));
        }

        if (options.scope !== undefined) {
            this.addChild(new StringParameter("Scope", "scope", options.scope));
        }

        if (options.provider !== undefined) {
            this.addChild(new StringParameter("Provider", "provider", options.provider));
        }

        if (options.access_key_id !== undefined) {
            this.addChild(new StringParameter("Access Key ID", "access_key_id", options.access_key_id));
        }

        if (options.secret_access_key !== undefined) {
            this.addChild(new StringParameter("Secret Access Key", "secret_access_key", options.secret_access_key));
        }

        if (options.region !== undefined) {
            this.addChild(new StringParameter("Region", "region", options.region));
        }

        if (options.endpoint !== undefined) {
            this.addChild(new StringParameter("Endpoint", "endpoint", options.endpoint));
        }
    }
}

export function createCloudAuthParameter(type: string): CloudAuthParameter {
    const provider = cloudSyncProviders[type];
    if (!provider) {
        throw new Error(`Unsupported remote type: ${type}`);
    }
    return new CloudAuthParameter("Auth", "auth", provider.parameters);
}

export class CloudSyncRemote extends ParameterNode {
    constructor(label: string, key: string, type: string, authParams: CloudAuthParameter) {
        super(label, key);
        this.addChild(new StringParameter("Type", "type", type));
        this.addChild(authParams);
    }
}