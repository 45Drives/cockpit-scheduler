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

    // Function to retrieve standard and advanced parameters separately
    getFormParameters(advanced: boolean = false) {
        return Object.entries(this.parameters.parameters)
            .filter(([_, param]) => param.advanced === advanced)
            .map(([key, param]) => ({ key, ...param }));
    }
}

/* export const cloudSyncProviders: { [key: string]: CloudSyncProvider } = {
    //'s3', 'b2', 'dropbox', 'drive', 'google cloud storage', 'azureblob', 'onedrive'

    "s3-AWS": new CloudSyncProvider("Amazon S3", "s3", { provider: "AWS", access_key_id: "", secret_access_key: "", region: "", endpoint: "" }),
    "s3-Wasabi": new CloudSyncProvider("Wasabi", "s3", { provider: "Wasabi", access_key_id: "", secret_access_key: "", region: "", endpoint: "" }),
    "b2": new CloudSyncProvider("Backblaze B2", "b2", { account: "", key: "", hard_delete: false }),
    "dropbox": new CloudSyncProvider("Dropbox", "dropbox", { account: "", token: {} }),
    "drive": new CloudSyncProvider("Google Drive", "drive", { account: "", token: {}, scope: "" }),
    "onedrive": new CloudSyncProvider("Microsoft Onedrive", "onedrive", { client_id: "", client_secret: "", region: "", token: {} }),
    "google cloud storage": new CloudSyncProvider("Google Cloud", "google cloud storage", { client_id: "", client_secret: "", token: {}, scope: "" }),
    "azureblob": new CloudSyncProvider("Azure Blob", "azure-blob", { account: "", key: ""}),
}; */

export const cloudSyncProviders: { [key: string]: CloudSyncProvider } = {
    "dropbox": new CloudSyncProvider("Dropbox", "dropbox", {
        parameters: {
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" },
            token: { value: {}, type: 'object', advanced: true, defaultValue: "" },
            auth_url: { value: "", type: 'string', advanced: true, defaultValue: "" },
            token_url: { value: "", type: 'string', advanced: true, defaultValue: "" },
            chunk_size: { value: "48Mi", type: 'string', advanced: true, defaultValue: '48Mi' },
            impersonate: { value: "", type: 'string', advanced: true },
            shared_files: { value: false, type: 'bool', advanced: true, defaultValue: false },
            shared_folders: { value: false, type: 'bool', advanced: true, defaultValue: false },
            batch_mode: { value: "off", type: 'string', advanced: true, allowedValues: ['off', 'sync', 'async'], defaultValue: "off" },
            batch_size: { value: 0, type: 'int', advanced: true, defaultValue: 0 },
            batch_timeout: { value: "10m", type: 'string', advanced: true, defaultValue: '10m' },
            batch_commit_timeout: { value: "10m", type: 'string', advanced: true, defaultValue: '10m' },
            encoding: { value: "Slash,BackSlash,Del,RightSpace,InvalidUtf8,Dot", type: 'string', advanced: true, defaultValue: "Slash,BackSlash,Del,RightSpace,InvalidUtf8,Dot" }
        }
    }),
    "drive": new CloudSyncProvider("Google Drive", "drive", {
        parameters: {
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" },
            scope: { value: "drive", type: 'string', allowedValues: ["drive", "drive.readonly", "drive.file", "drive.appfolder", "drive.metadata.readonly"], defaultValue: "drive" },
            root_folder_id: { value: "", type: 'string', defaultValue: "" },
            service_account_file: { value: "", type: 'string', defaultValue: "" },
            token: { value: {}, type: 'object', advanced: true, defaultValue: "" },
            auth_url: { value: "", type: 'string', advanced: true, defaultValue: "" },
            token_url: { value: "", type: 'string', advanced: true, defaultValue: "" },
            auth_owner_only: { value: false, type: 'bool', advanced: true, defaultValue: false },
            use_trash: { value: true, type: 'bool', advanced: true, defaultValue: true },
            skip_gdocs: { value: false, type: 'bool', advanced: true, defaultValue: false },
            skip_checksum_gphotos: { value: false, type: 'bool', advanced: true, defaultValue: false },
            shared_with_me: { value: false, type: 'bool', advanced: true, defaultValue: false },
            trashed_only: { value: false, type: 'bool', advanced: true, defaultValue: false },
            starred_only: { value: false, type: 'bool', advanced: true, defaultValue: false },
            export_formats: { value: "docx,xlsx,pptx,svg", type: 'string', advanced: true, defaultValue: "docx,xlsx,pptx,svg" },
            import_formats: { value: "", type: 'string', advanced: true, defaultValue: "" },
            allow_import_name_change: { value: false, type: 'bool', advanced: true, defaultValue: false },
            list_chunk: { value: 1000, type: 'int', advanced: true, defaultValue: 1000, allowedValues: [0, 100, 500, 1000] },
            impersonate: { value: "", type: 'string', advanced: true },
            upload_cutoff: { value: "8Mi", type: 'string', advanced: true, defaultValue: "8Mi" },
            chunk_size: { value: "8Mi", type: 'string', advanced: true, defaultValue: "8Mi" },
            acknowledge_abuse: { value: false, type: 'bool', advanced: true, defaultValue: false },
            keep_revision_forever: { value: false, type: 'bool', advanced: true, defaultValue: false },
            v2_download_min_size: { value: "", type: 'string', advanced: true },
            pacer_min_sleep: { value: "100ms", type: 'string', advanced: true, defaultValue: "100ms" },
            pacer_burst: { value: 100, type: 'int', advanced: true, defaultValue: 100 },
            server_side_across_configs: { value: false, type: 'bool', advanced: true, defaultValue: false },
            disable_http2: { value: true, type: 'bool', advanced: true, defaultValue: true },
            stop_on_upload_limit: { value: false, type: 'bool', advanced: true, defaultValue: false },
            stop_on_download_limit: { value: false, type: 'bool', advanced: true, defaultValue: false },
            skip_shortcuts: { value: false, type: 'bool', advanced: true, defaultValue: false },
            encoding: { value: "InvalidUtf8", type: 'string', advanced: true, defaultValue: "InvalidUtf8" }
        }
    }),
    "google cloud storage": new CloudSyncProvider("Google Cloud", "google cloud storage", {
        parameters: {
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" },
            project_number: { value: "", type: 'string', defaultValue: "" },
            service_account_file: { value: "", type: 'string', defaultValue: "" },
            anonymous: { value: false, type: 'bool', defaultValue: false },
            object_acl: { value: "", type: 'string', allowedValues: ["authenticatedRead", "bucketOwnerFullControl", "bucketOwnerRead", "private", "projectPrivate", "publicRead"], defaultValue: "" },
            bucket_acl: { value: "", type: 'string', allowedValues: ["authenticatedRead", "private", "projectPrivate", "publicRead", "publicReadWrite"], defaultValue: "" },
            bucket_policy_only: { value: false, type: 'bool', advanced: true, defaultValue: false },
            location: { value: "", type: 'string', allowedValues: ["", "asia", "eu", "us", "asia-east1", "asia-east2", "asia-northeast1", "asia-south1", "asia-southeast1", "australia-southeast1", "europe-north1", "europe-west1", "europe-west2", "europe-west3", "europe-west4", "us-central1", "us-east1", "us-east4", "us-west1", "us-west2"], defaultValue: "" },
            storage_class: { value: "", type: 'string', allowedValues: ["", "MULTI_REGIONAL", "REGIONAL", "NEARLINE", "COLDLINE", "ARCHIVE", "DURABLE_REDUCED_AVAILABILITY"], defaultValue: "" },
            token: { value: {}, type: 'object', advanced: true, defaultValue: "" },
            auth_url: { value: "", type: 'string', advanced: true, defaultValue: "" },
            token_url: { value: "", type: 'string', advanced: true, defaultValue: "" },
            encoding: { value: "Slash,CrLf,InvalidUtf8,Dot", type: 'string', advanced: true, defaultValue: "Slash,CrLf,InvalidUtf8,Dot" }
        }
    }),
    "onedrive": new CloudSyncProvider("Microsoft OneDrive", "onedrive", {
        parameters: {
            client_id: { value: "", type: 'string', defaultValue: "" },
            client_secret: { value: "", type: 'string', defaultValue: "" },
            region: { value: "global", type: 'string', allowedValues: ["global", "us", "de", "cn"], defaultValue: "global" },
            token: { value: {}, type: 'object', advanced: true, defaultValue: "" },
            auth_url: { value: "", type: 'string', advanced: true, defaultValue: "" },
            token_url: { value: "", type: 'string', advanced: true, defaultValue: "" },
            chunk_size: { value: "10Mi", type: 'string', advanced: true, defaultValue: "10Mi" },
            drive_id: { value: "", type: 'string', advanced: true, defaultValue: "" },
            drive_type: { value: "personal", type: 'string', advanced: true, allowedValues: ["personal", "business", "documentLibrary"], defaultValue: "personal" },
            expose_onenote_fields: { value: false, type: 'bool', advanced: true, defaultValue: false },
            server_side_across_configs: { value: false, type: 'bool', advanced: true, defaultValue: false },
            list_chunk: { value: 1000, type: 'int', advanced: true, defaultValue: 1000 },
            no_versions: { value: false, type: 'bool', advanced: true, defaultValue: false },
            link_scope: { value: "anonymous", type: 'string', advanced: true, allowedValues: ["anonymous", "organization"], defaultValue: "anonymous" },
            link_type: { value: "view", type: 'string', advanced: true, allowedValues: ["view", "edit", "embed"], defaultValue: "view" },
            link_password: { value: "", type: 'string', advanced: true, defaultValue: "" },
            encoding: { value: "Slash,LtGt,DoubleQuote,Colon,Question,Asterisk,Pipe,BackSlash,Del,Ctl,LeftSpace,LeftTilde,RightSpace,RightPeriod,InvalidUtf8,Dot", type: 'string', advanced: true, defaultValue: "Slash,LtGt,DoubleQuote,Colon,Question,Asterisk,Pipe,BackSlash,Del,Ctl,LeftSpace,LeftTilde,RightSpace,RightPeriod,InvalidUtf8,Dot" }
        }
    }),
    "azureblob": new CloudSyncProvider("Microsoft Azure Blob", "azureblob", {
        parameters: {
            account: { value: "", type: 'string', defaultValue: "" },
            service_principal_file: { value: "", type: 'string', defaultValue: "" },
            key: { value: "", type: 'string', defaultValue: "" },
            sas_url: { value: "", type: 'string', defaultValue: "" },
            use_msi: { value: false, type: 'bool', defaultValue: false },
            use_emulator: { value: false, type: 'bool', defaultValue: false },
            msi_object_id: { value: "", type: 'string', advanced: true },
            msi_client_id: { value: "", type: 'string', advanced: true },
            msi_mi_res_id: { value: "", type: 'string', advanced: true },
            endpoint: { value: "", type: 'string', advanced: true },
            upload_cutoff: { value: "", type: 'string', advanced: true },
            chunk_size: { value: "4Mi", type: 'string', advanced: true, defaultValue: "4Mi" },
            list_chunk: { value: 5000, type: 'int', advanced: true, defaultValue: 5000 },
            access_tier: { value: "", type: 'string', advanced: true },
            archive_tier_delete: { value: false, type: 'bool', advanced: true, defaultValue: false },
            disable_checksum: { value: false, type: 'bool', advanced: true, defaultValue: false },
            memory_flush_pool_time: { value: "1m", type: 'string', advanced: true, defaultValue: "1m" },
            memory_pool_use_mmap: { value: false, type: 'bool', advanced: true, defaultValue: false },
            encoding: { value: "Slash,BackSlash,Del,Ctl,RightPeriod,InvalidUtf8", type: 'string', advanced: true, defaultValue: "Slash,BackSlash,Del,Ctl,RightPeriod,InvalidUtf8" },
            public_access: { value: "", type: 'string', advanced: true, allowedValues: ["", "blob", "container"], defaultValue: "" },
            no_head_object: { value: false, type: 'bool', advanced: true, defaultValue: false }
        }
    }),
    "b2": new CloudSyncProvider("Backblaze B2", "b2", {
        parameters: {
            account: { value: "", type: 'string', defaultValue: "" },
            key: { value: "", type: 'string', defaultValue: "" },
            hard_delete: { value: false, type: 'bool', defaultValue: false },
            endpoint: { value: "", type: 'string', advanced: true },
            versions: { value: false, type: 'bool', advanced: true, defaultValue: false },
            upload_cutoff: { value: "200Mi", type: 'string', advanced: true, defaultValue: "200Mi" },
            copy_cutoff: { value: "4Gi", type: 'string', advanced: true, defaultValue: "4Gi" },
            chunk_size: { value: "96Mi", type: 'string', advanced: true, defaultValue: "96Mi" },
            disable_checksum: { value: false, type: 'bool', advanced: true, defaultValue: false },
            download_url: { value: "", type: 'string', advanced: true },
            download_auth_duration: { value: "1w", type: 'string', advanced: true, defaultValue: "1w" },
            memory_flush_pool_time: { value: "1m", type: 'string', advanced: true, defaultValue: "1m" },
            memory_pool_use_mmap: { value: false, type: 'bool', advanced: true, defaultValue: false },
            encoding: { value: "Slash,BackSlash,Del,Ctl,InvalidUtf8,Dot", type: 'string', advanced: true, defaultValue: "Slash,BackSlash,Del,Ctl,InvalidUtf8,Dot" }
        }
    }),

    "s3-Wasabi": new CloudSyncProvider("Wasabi", "s3", {
        parameters: {
            provider: { value: "Wasabi", type: 'string', defaultValue: "Wasabi" },
            env_auth: { value: false, type: 'bool', defaultValue: false },
            access_key_id: { value: "", type: 'string', defaultValue: "" },
            secret_access_key: { value: "", type: 'string', defaultValue: "" },
            region: { value: "", type: 'string', allowedValues: ["", "other-v2-signature"], defaultValue: "" },
            endpoint: { value: "", type: 'string', defaultValue: "" },
            location_constraint: { value: "", type: 'string', defaultValue: "" },
            acl: { value: "private", type: 'string', allowedValues: ["private", "public-read", "public-read-write", "authenticated-read", "bucket-owner-read", "bucket-owner-full-control"], defaultValue: "private" },
            bucket_acl: { value: "private", type: 'string', advanced: true, allowedValues: ["private", "public-read", "public-read-write", "authenticated-read"], defaultValue: "private" },
            upload_cutoff: { value: "200Mi", type: 'string', advanced: true, defaultValue: "200Mi" },
            chunk_size: { value: "5Mi", type: 'string', advanced: true, defaultValue: "5Mi" },
            max_upload_parts: { value: 10000, type: 'int', advanced: true, defaultValue: 10000 },
            copy_cutoff: { value: "4.656Gi", type: 'string', advanced: true, defaultValue: "4.656Gi" },
            disable_checksum: { value: false, type: 'bool', advanced: true, defaultValue: false },
            shared_credentials_file: { value: "", type: 'string', advanced: true },
            profile: { value: "", type: 'string', advanced: true },
            session_token: { value: "", type: 'string', advanced: true },
            upload_concurrency: { value: 4, type: 'int', advanced: true, defaultValue: 4 },
            force_path_style: { value: true, type: 'bool', advanced: true, defaultValue: true },
            v2_auth: { value: false, type: 'bool', advanced: true, defaultValue: false },
            list_chunk: { value: 1000, type: 'int', advanced: true, defaultValue: 1000 },
            no_check_bucket: { value: false, type: 'bool', advanced: true, defaultValue: false },
            no_head: { value: false, type: 'bool', advanced: true, defaultValue: false },
            no_head_object: { value: false, type: 'bool', advanced: true, defaultValue: false },
            encoding: { value: "Slash,InvalidUtf8,Dot", type: 'string', advanced: true, defaultValue: "Slash,InvalidUtf8,Dot" },
            memory_flush_pool_time: { value: "1m", type: 'string', advanced: true, defaultValue: "1m" },
            memory_pool_use_mmap: { value: false, type: 'bool', advanced: true, defaultValue: false },
            disable_http2: { value: false, type: 'bool', advanced: true, defaultValue: false },
            download_url: { value: "", type: 'string', advanced: true, defaultValue: "" }
        },
        provider: 'Wasabi'
    }),
    "s3-AWS": new CloudSyncProvider("Amazon S3", "s3", {
        parameters: {
            provider: { value: "AWS", type: 'string', defaultValue: "AWS" },
            env_auth: { value: false, type: 'bool', defaultValue: false },
            access_key_id: { value: "", type: 'string', defaultValue: "" },
            secret_access_key: { value: "", type: 'string', defaultValue: "" },
            region: { value: "", type: 'string', allowedValues: ["", "other-v2-signature"], defaultValue: "" },
            endpoint: { value: "", type: 'string', defaultValue: "" },
            location_constraint: { value: "", type: 'string', defaultValue: "" },
            acl: { value: "private", type: 'string', allowedValues: ["private", "public-read", "public-read-write", "authenticated-read", "bucket-owner-read", "bucket-owner-full-control"], defaultValue: "private" },
            server_side_encryption: { value: "", type: 'string', advanced: true },
            sse_kms_key_id: { value: "", type: 'string', advanced: true },
            storage_class: { value: "", type: 'string', advanced: true },
            bucket_acl: { value: "private", type: 'string', advanced: true, allowedValues: ["private", "public-read", "public-read-write", "authenticated-read"], defaultValue: "private" },
            upload_cutoff: { value: "200Mi", type: 'string', advanced: true, defaultValue: "200Mi" },
            chunk_size: { value: "5Mi", type: 'string', advanced: true, defaultValue: "5Mi" },
            max_upload_parts: { value: 10000, type: 'int', advanced: true, defaultValue: 10000 },
            copy_cutoff: { value: "4.656Gi", type: 'string', advanced: true, defaultValue: "4.656Gi" },
            disable_checksum: { value: false, type: 'bool', advanced: true, defaultValue: false },
            shared_credentials_file: { value: "", type: 'string', advanced: true },
            profile: { value: "", type: 'string', advanced: true },
            session_token: { value: "", type: 'string', advanced: true },
            upload_concurrency: { value: 4, type: 'int', advanced: true, defaultValue: 4 },
            force_path_style: { value: true, type: 'bool', advanced: true, defaultValue: true },
            v2_auth: { value: false, type: 'bool', advanced: true, defaultValue: false },
            use_accelerate_endpoint: { value: false, type: 'bool', advanced: true, defaultValue: false },
            leave_parts_on_error: { value: false, type: 'bool', advanced: true, defaultValue: false },
            list_chunk: { value: 1000, type: 'int', advanced: true, defaultValue: 1000 },
            no_check_bucket: { value: false, type: 'bool', advanced: true, defaultValue: false },
            no_head: { value: false, type: 'bool', advanced: true, defaultValue: false },
            no_head_object: { value: false, type: 'bool', advanced: true, defaultValue: false },
            encoding: { value: "Slash,InvalidUtf8,Dot", type: 'string', advanced: true, defaultValue: "Slash,InvalidUtf8,Dot" },
            memory_flush_pool_time: { value: "1m", type: 'string', advanced: true, defaultValue: "1m" },
            memory_pool_use_mmap: { value: false, type: 'bool', advanced: true, defaultValue: false },
            disable_http2: { value: false, type: 'bool', advanced: true, defaultValue: false },
            download_url: { value: "", type: 'string', advanced: true, defaultValue: "" }
        },
        provider: 'AWS'
    }),

};


interface CloudAuthParameterOptions {
    parameters: {
        [key: string]: {
            value: any;
            type: 'string' | 'bool' | 'int' | 'object';
            // type: 'string' | 'bool' | 'int' | 'select' | 'size' | 'duration' | 'object';
            advanced?: boolean; // Flag to indicate if this is an advanced option
            allowedValues?: string[] | number[];
            defaultValue?: string | number | boolean | object;
            // minValue?: number;
            // maxValue?: number;
        };
    },
    provider?: string
}


export class CloudAuthParameter extends ParameterNode implements ParameterNodeType {
    constructor(label: string, key: string, options: CloudAuthParameterOptions = { parameters: {}}) {
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