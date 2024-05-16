import { getPoolData, getDatasetData } from '../composables/utility';

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
}