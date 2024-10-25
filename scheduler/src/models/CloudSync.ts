import { ParameterNode, StringParameter, BoolParameter, IntParameter, ObjectParameter, } from "./Parameters";
import { providerLogos } from '../utils/providerLogos';

export class CloudSyncProvider {
    name: string;
    type: string;
    parameters: CloudAuthParameterOptions;

    constructor(name: string, type: string, parameters: CloudAuthParameterOptions) {
        this.name = name;
        this.type = type;
        this.parameters = parameters;
    }

    // Function to retrieve standard and advanced parameters separately
    getFormParameters(advanced: boolean = false) {
        return Object.entries(this.parameters.parameters)
            .filter(([_, param]) => param.advanced === advanced)
            .map(([key, param]) => ({ key, ...param }));
    }
}

export const cloudSyncProviders: { [key: string]: CloudSyncProvider } = {
    "dropbox": new CloudSyncProvider("Dropbox", "dropbox", {
        parameters: {
            token: { value: {}, type: 'object', defaultValue: {} },
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" }
        },
        oAuthSupported: true
    }),
    "drive": new CloudSyncProvider("Google Drive", "drive", {
        parameters: {
            token: { value: {}, type: 'object', defaultValue: {} },
            scope: { value: "drive", type: 'select', allowedValues: ["drive", "drive.readonly", "drive.file", "drive.appfolder", "drive.metadata.readonly"], defaultValue: "drive" },
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" },
            root_folder_id: { value: "", type: 'string', defaultValue: "" },
            service_account_file: { value: "", type: 'string', defaultValue: "" }
        },
        oAuthSupported: true
    }),
    "google cloud storage": new CloudSyncProvider("Google Cloud", "google cloud storage", {
        parameters: {
            token: { value: {}, type: 'object', defaultValue: {} },
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" },
            project_number: { value: "", type: 'string', defaultValue: "" },
            service_account_file: { value: "", type: 'string', defaultValue: "" },
            anonymous: { value: false, type: 'bool', defaultValue: false },
            object_acl: { value: "private", type: 'select', allowedValues: ["authenticatedRead", "bucketOwnerFullControl", "bucketOwnerRead", "private", "projectPrivate", "publicRead"], defaultValue: "private" },
            bucket_acl: { value: "private", type: 'select', allowedValues: ["authenticatedRead", "private", "projectPrivate", "publicRead", "publicReadWrite"], defaultValue: "private" }
        },
        oAuthSupported: true
    }),
    "onedrive": new CloudSyncProvider("Microsoft OneDrive", "onedrive", {
        parameters: {
            token: { value: {}, type: 'object', defaultValue: {} },
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" },
            region: { value: "global", type: 'select', allowedValues: ["global", "us", "de", "cn"], defaultValue: "global" }
        },
        oAuthSupported: true
    }),
    "azureblob": new CloudSyncProvider("Microsoft Azure Blob", "azureblob", {
        parameters: {
            account: { value: "", type: 'string', defaultValue: "" },
            service_principal_file: { value: "", type: 'string', defaultValue: "" },
            key: { value: "", type: 'string', defaultValue: "" },
            sas_url: { value: "", type: 'string', defaultValue: "" },
            use_msi: { value: false, type: 'bool', defaultValue: false },
            use_emulator: { value: false, type: 'bool', defaultValue: false }
        }
    }),
    "b2": new CloudSyncProvider("Backblaze B2", "b2", {
        parameters: {
            account: { value: "", type: 'string', defaultValue: "" },
            key: { value: "", type: 'string', defaultValue: "" },
            hard_delete: { value: false, type: 'bool', defaultValue: false }
        }
    }),
    "s3-Wasabi": new CloudSyncProvider("Wasabi", "s3", {
        parameters: {
            provider: { value: "Wasabi", type: 'string', defaultValue: "Wasabi" },
            env_auth: { value: false, type: 'bool', defaultValue: false },
            access_key_id: { value: "", type: 'string', defaultValue: "" },
            secret_access_key: { value: "", type: 'string', defaultValue: "" },
            endpoint: { value: "", type: 'string', defaultValue: "" },
            region: { value: "", type: 'string', allowedValues: ["", "other-v2-signature"], defaultValue: "" },
            location_constraint: { value: "", type: 'string', defaultValue: "" },
            acl: { value: "private", type: 'select', allowedValues: ["private", "public-read", "public-read-write", "authenticated-read", "bucket-owner-read", "bucket-owner-full-control"], defaultValue: "private" }
        },
        provider: 'Wasabi'
    }),
    "s3-AWS": new CloudSyncProvider("Amazon S3", "s3", {
        parameters: {
            provider: { value: "AWS", type: 'string', defaultValue: "AWS" },
            env_auth: { value: false, type: 'bool', defaultValue: false },
            access_key_id: { value: "", type: 'string', defaultValue: "" },
            secret_access_key: { value: "", type: 'string', defaultValue: "" },
            endpoint: { value: "", type: 'string', defaultValue: "" },
            region: { value: "", type: 'string', allowedValues: ["", "other-v2-signature"], defaultValue: "" },
            location_constraint: { value: "", type: 'string', defaultValue: "" },
            acl: { value: "private", type: 'select', allowedValues: ["private", "public-read", "public-read-write", "authenticated-read", "bucket-owner-read", "bucket-owner-full-control"], defaultValue: "private" }
        },
        provider: 'AWS'
    }),

};


interface CloudAuthParameterOptions {
    parameters: {
        [key: string]: CloudSyncParameter;
    };
    provider?: string;
    oAuthSupported?: boolean;
}

interface CloudSyncParameter {
    value: any;
    type: 'string' | 'bool' | 'int' | 'select' | 'size' | 'duration' | 'object';
    advanced?: boolean; // Flag to indicate if this is an advanced option
    allowedValues?: string[] | number[];
    defaultValue?: string | number | boolean | object;
    minValue?: number;
    maxValue?: number;
}

export class CloudAuthParameter extends ParameterNode {
    constructor(label: string, key: string, options: CloudAuthParameterOptions = { parameters: {} }) {
        super(label, key);

        // Function to check if a child parameter with the same key already exists
        const findChild = (key: string) => {
            return this.children.find(child => child.key === key);
        };

        // Dynamically add parameters from options
        Object.entries(options.parameters).forEach(([key, param]) => {
            const { value, type } = param;
            let existingChild = findChild(key);

            if (existingChild) {
                // If the parameter already exists, update its value
                if (existingChild instanceof StringParameter && type === 'string') {
                    existingChild.value = value as string;
                } else if (existingChild instanceof BoolParameter && type === 'bool') {
                    existingChild.value = value as boolean;
                } else if (existingChild instanceof ObjectParameter && type === 'object') {
                    existingChild.value = value;
                }
            } else {
                // If the parameter does not exist, add it as a new child
                if (type === 'string') {
                    this.addChild(new StringParameter(key, key, value));
                } else if (type === 'bool') {
                    this.addChild(new BoolParameter(key, key, value));
                } else if (type === 'object') {
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

// Function to fetch logo and color
export function getProviderLogo(selectedProvider?: CloudSyncProvider, selectedRemote?: CloudSyncRemote): string {
    // Determine the type and parameters based on whether it's a provider or a remote
    const type = selectedProvider ? selectedProvider.type : selectedRemote?.type;
    const provider = selectedProvider
        ? selectedProvider.parameters.provider
        : selectedRemote?.provider.parameters.provider;

    if (type === "s3" && provider) {
        return providerLogos[`${type}-${provider}`]?.logo || "";
    } else if (type) {
        return providerLogos[type]?.logo || "";
    }

    return "";
}

export function getProviderColor(selectedProvider?: CloudSyncProvider, selectedRemote?: CloudSyncRemote): string {
    const type = selectedProvider ? selectedProvider.type : selectedRemote?.type;
    const provider = selectedProvider
        ? selectedProvider.parameters.provider
        : selectedRemote?.provider.parameters.provider;

    if (type === "s3" && provider) {
        return providerLogos[`${type}-${provider}`]?.mainColor;
    } else if (type) {
        return providerLogos[type]?.mainColor;
    }
    return "#000000"; // Default color
}

export function getProviderHoverColor(selectedProvider?: CloudSyncProvider, selectedRemote?: CloudSyncRemote): string {
    const type = selectedProvider ? selectedProvider.type : selectedRemote?.type;
    const provider = selectedProvider
        ? selectedProvider.parameters.provider
        : selectedRemote?.provider.parameters.provider;

    if (type === "s3" && provider) {
        return providerLogos[`${type}-${provider}`]?.hoverColor;
    } else if (type) {
        return providerLogos[type]?.hoverColor;
    }
    return "#000000"; // Default color
}

export function getButtonStyles(hovered: boolean, selectedProvider?: CloudSyncProvider, selectedRemote?: CloudSyncRemote) {
    const mainColor = getProviderColor(selectedProvider, selectedRemote);
    const hoverColor = getProviderHoverColor(selectedProvider, selectedRemote);

    return {
        backgroundColor: hovered ? hoverColor : mainColor,
        transition: 'background-color 0.01s ease',
    };
}