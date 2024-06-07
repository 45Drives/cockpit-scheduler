import { getPoolData, getDatasetData, getDisks } from '../composables/utility';

export class ParameterNode implements ParameterNodeType {
    label: string;
    key: string;
    children: ParameterNode[];
    value: any;

    constructor(label: string, key: string) {
        this.label = label;
        this.key = key;
        this.children = [];
    }

    addChild(child: ParameterNode) {
        this.children.push(child);
        return this;
    }

    asEnvKeyValues(): string[] {
        return this.children.map(c => c.asEnvKeyValues()) // recursively get child key=value pairs
            .flat()
            .map(kv => `${this.key}_${kv}`); // prefix key with parent key and _
    }

}

export class StringParameter extends ParameterNode implements StringParameterType {
    value: string;

    constructor(label: string, key: string, value: string = '') {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value}`]; // Generate key=value pair for StringParameter
    }
}

export class IntParameter extends ParameterNode implements IntParameterType {
    value: number;

    constructor(label: string, key: string, value: number = 0) {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value.toString()}`]; // Generate key=value pair for IntParameter
    }
}

export class BoolParameter extends ParameterNode implements BoolParameterType {
    value: boolean;

    constructor(label: string, key: string, value: boolean = false) {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value ? 'true' : 'false'}`]; // Generate key=value pair for BoolParameter
    }
}

export class SelectionOption implements SelectionOptionType {
    value: string | number | boolean;
    label: string;

    constructor(value: string | number | boolean, label: string) {
        this.value = value;
        this.label = label;
    }
}

export class SelectionParameter extends ParameterNode implements SelectionParameterType {
    value: string;
    options: SelectionOption[];

    constructor(label: string, key: string, value: string = '', options: SelectionOption[] = []) {
        super(label, key);
        this.value = value;
        this.options = options;
    }

    addOption(option: SelectionOption) {
        this.options.push(option);
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value}`]; // Implement logic to handle options if needed
    }
}

export class ZfsDatasetParameter extends ParameterNode implements ParameterNodeType {
    constructor(label: string, key: string, host: string = "", port: number = 0, user: string = "", pool: string = "", dataset: string = "") {
        super(label, key);
        
        // Add child parameters
        this.addChild(new StringParameter("Host", "host", host));
        this.addChild(new IntParameter("Port", "port", port));
        this.addChild(new StringParameter("User", "user", user));
        
        // const poolParam = new SelectionParameter("Pool", "pool", pool);
        const poolParam = new SelectionParameter("Pool", "pool", pool);
        
        this.addChild(poolParam);
        
        // const datasetParam = new SelectionParameter("Dataset", "dataset", dataset);
        const datasetParam = new SelectionParameter("Dataset", "dataset", dataset);     
        this.addChild(datasetParam);
    }

    async loadPools() {
        const pools = await getPoolData(this.children['host'], this.children['port'], this.children['user'])
        const poolParam = this.getChild('pool') as SelectionParameter;

        pools.forEach(pool => {
            poolParam.addOption(new SelectionOption(pool, pool));
            // this.loadDatasets(pools[0]);
        });
    }

    async loadDatasets(pool: string) {
        const datasets = await getDatasetData(this.children['host'], this.children['port'], this.children['user'], pool);
        const datasetParam = this.getChild('dataset') as SelectionParameter;
        
        datasets.forEach(dataset => {
            datasetParam.addOption(new SelectionOption(dataset, dataset));
        });
    }

    getChild(key: string): ParameterNode {
        const child = this.children.find(child => child.key === key);
        if (!child) {
            throw new Error(`Child with key ${key} not found`);
        }
        return child;
    }
    
    // Method to create ZfsDatasetParameter from a location
    static fromLocation(label: string, key: string, location: Location): ZfsDatasetParameter {
        const { host, port, user, root, path } = location;
        return new ZfsDatasetParameter(label, key, host, port, user, root, path);
    }

    // Method to convert ZfsDatasetParameter to a location
    toLocation(): Location {
        const label = (this.children[0] as StringParameter).value;
        const key = (this.children[1] as StringParameter).value;
        const host = (this.children[2] as StringParameter).value;
        const port = (this.children[3] as IntParameter).value;
        const user = (this.children[4] as StringParameter).value;
        const root = (this.children[5] as SelectionParameter).value;
        const path = (this.children[6] as SelectionParameter).value;

        return { host, port, user, root, path };
    }
}

export class Location implements LocationType {
    host: string;
    port: number;
    user: string;
    root: string;
    path: string;

    constructor(host: string, port: number, user: string, root: string, path: string) {
        this.host = host;
        this.port = port;
        this.user = user;
        this.root = root;
        this.path = path;
    }
}

export class LocationParameter extends ParameterNode implements ParameterNodeType {
    constructor(label: string, key: string, host: string = "", port: number = 0, user: string = "", root: string = "", path: string = "") {
        super(label, key);

        this.addChild(new StringParameter("Host", "host", host));
        this.addChild(new IntParameter("Port", "port", port));
        this.addChild(new StringParameter("User", "user", user));
        this.addChild(new StringParameter("Root", "root", root));
        this.addChild(new StringParameter("Path", "path", path));
    } 

    // Method to create ZfsDatasetParameter from a location
    static fromLocation(label: string, key: string, location: Location): LocationParameter {
        const { host, port, user, root, path } = location;
        return new LocationParameter(label, key, host, port, user, root, path);
    }

    // Method to convert ZfsDatasetParameter to a location
    toLocation(): Location {
        const label = (this.children[0] as StringParameter).value;
        const key = (this.children[1] as StringParameter).value;
        const host = (this.children[2] as StringParameter).value;
        const port = (this.children[3] as IntParameter).value;
        const user = (this.children[4] as StringParameter).value;
        const root = (this.children[5] as SelectionParameter).value;
        const path = (this.children[6] as SelectionParameter).value;

        return { host, port, user, root, path };
    }
}

// export class ListParameter extends ParameterNode implements ParameterNodeType {
//     constructor(label: string, key: string, values: string[] = []) {
//         super(label, key);
//         this.value = values;
//     }

//     addValue(value: string) {
//         if (!this.value.includes(value)) {
//             this.value.push(value);
//         }
//     }

//     removeValue(value: string) {
//         const index = this.value.indexOf(value);
//         if (index > -1) {
//             this.value.splice(index, 1);
//         }
//     }

//     asEnvKeyValues(): string[] {
//         return [`${this.key}=${this.value.join(',')}`]; // Generate key=value pair
//     }
// }