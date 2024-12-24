import { ParameterNode, StringParameter, BoolParameter, IntParameter, ObjectParameter, SelectionParameter, SelectionOption, } from "./Parameters";
import { providerLogos } from '../utils/providerLogos';

export class CloudSyncProvider {
    name: string;
    type: string;
    providerParams: CloudAuthParameter;

    constructor(name: string, type: string, providerParams: CloudAuthParameter) {
        this.name = name;
        this.type = type;
        this.providerParams = providerParams;
    }

    getProviderParameters() {
        return Object.entries(this.providerParams.parameters)
            .map(([key, param]) => ({ key, ...param }));
    }
}

export const cloudSyncProviders: { [key: string]: CloudSyncProvider } = {
    "dropbox": new CloudSyncProvider("Dropbox", "dropbox", {
        parameters: {
            token: { value: "", type: 'object', defaultValue: "" },
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" }
        },
        oAuthSupported: true
    }),
    "drive": new CloudSyncProvider("Google Drive", "drive", {
        parameters: {
            token: { value: "", type: 'object', defaultValue: "" },
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
            token: { value: "", type: 'object', defaultValue: "" },
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
    // "onedrive": new CloudSyncProvider("Microsoft OneDrive", "onedrive", {
    //     parameters: {
    //         // token: { value: "", type: 'object', defaultValue: "" },
    //         client_id: { value: "", type: 'string', defaultValue: "" },
    //         client_secret: { value: "", type: 'string', defaultValue: "" },
    //         region: { value: "global", type: 'select', allowedValues: ["global", "us", "de", "cn"], defaultValue: "global" }
    //     },
    //     // oAuthSupported: true
    // }),
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
    }),

};


export interface CloudAuthParameter {
    parameters: {
        [key: string]: CloudSyncParameter;
    };
    oAuthSupported?: boolean;
}

export interface CloudSyncParameter {
    value: any;
    type: 'string' | 'bool' | 'int' | 'select' | 'object';
    allowedValues?: string[];
    defaultValue?: string | number | boolean | object;
}

export class CloudSyncRemote extends ParameterNode implements CloudSyncRemoteType {
    key: string;
    name: string;  // Name of the remote
    type: string;  // Type of the remote
    provider: CloudSyncProvider;  // Cloud provider details
    authParams: CloudAuthParameter;  // Authentication parameters

    constructor(name: string, type: string, authParams: CloudAuthParameter, provider: CloudSyncProvider) {
        super(`Rclone Remote`, `remoteType-${type}`);
        this.key = 'cloud_sync_remote';
        this.name = name;
        this.type = type;
        this.authParams = authParams;
        this.provider = provider;
    }

    getAuthParameter(paramKey: string) {
        return this.authParams.parameters[paramKey]?.value;
    }

    getProviderType() {
        if (this.provider.type == 's3') {
            return `${this.provider.type}-${this.provider.providerParams.parameters.provider.value}`
        } else {
            return this.provider.type;
        }
    }

    getProviderName() {
        return this.provider.name;
    }

    asEnvKeyValues(): string[] {
        // Only store the name of the remote
        return [`${this.key}=${this.name}`];
    }
}


// Functions to fetch logo and color
export function getProviderLogo(selectedProvider?: CloudSyncProvider, selectedRemote?: CloudSyncRemote): string {
    // console.log('logo selectedProvider:', selectedProvider)
    // console.log('logo selectedRemote:', selectedRemote)

    // Determine the type and provider, using optional chaining to prevent undefined errors
    const type = selectedProvider ? selectedProvider.type : selectedRemote?.type;
    const provider = selectedProvider?.providerParams?.parameters?.provider?.value
        || selectedRemote?.provider?.providerParams?.parameters?.provider?.value;
    // console.log('logo type:', type);
    // console.log('logo provider:', provider);
    
    // Construct the key for providerLogos and return the appropriate logo
    if (type === "s3" && provider) {
        return providerLogos[`${type}-${provider}`]?.logo || "";
    } else if (type) {
        return providerLogos[type]?.logo || "";
    }

    return "";
}

export function getProviderColor(selectedProvider?: CloudSyncProvider, selectedRemote?: CloudSyncRemote): string {
    const type = selectedProvider ? selectedProvider.type : selectedRemote?.type;
    const provider = selectedProvider?.providerParams?.parameters?.provider?.value
        || selectedRemote?.provider?.providerParams?.parameters?.provider?.value;

    if (type === "s3" && provider) {
        return providerLogos[`${type}-${provider}`]?.mainColor;
    } else if (type) {
        return providerLogos[type]?.mainColor;
    }
    return "#000000"; // Default color
}

export function getProviderHoverColor(selectedProvider?: CloudSyncProvider, selectedRemote?: CloudSyncRemote): string {
    const type = selectedProvider ? selectedProvider.type : selectedRemote?.type;
    const provider = selectedProvider?.providerParams?.parameters?.provider?.value
        || selectedRemote?.provider?.providerParams?.parameters?.provider?.value;

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

    // console.log(`Hovered: ${hovered}, Main Color: ${mainColor}, Hover Color: ${hoverColor}`);

    return {
        backgroundColor: hovered ? hoverColor : mainColor,
        transition: 'background-color 0.01s ease',
    };
}