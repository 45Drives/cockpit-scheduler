// Parameters.ts

export class ParameterNode {
    label: string;
    key: string;
    children: ParameterNode[];

    constructor(label: string, key: string) {
        this.label = label;
        this.key = key;
        this.children = [];
    }

    addChild(child: ParameterNode) {
        this.children.push(child);
    }

    asEnvKeyValues(): string[] {
        return this.children.map(c => c.asEnvKeyValues()) // recursively get child key=value pairs
            .flat()
            .map(kv => `${this.key}_${kv}`); // prefix key with parent key and _
    }

    isValid() {
        // Implementation for validation
    }

    uiComponent() {
        // Implementation for generating UI component
    }
}

export class StringParameter extends ParameterNode {
    value: string;

    constructor(label: string, key: string, value: string) {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value}`]; // Generate key=value pair for StringParameter
    }
}

export class IntParameter extends ParameterNode {
    value: number;

    constructor(label: string, key: string, value: number) {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value.toString()}`]; // Generate key=value pair for IntParameter
    }
}

export class BoolParameter extends ParameterNode {
    value: boolean;

    constructor(label: string, key: string, value: boolean) {
        super(label, key);
        this.value = value;
    }

    asEnvKeyValues(): string[] {
        return [`${this.key}=${this.value ? 'true' : 'false'}`]; // Generate key=value pair for BoolParameter
    }
}


export class SelectionOption {
    value: string | number | boolean;
    label: string;

    constructor(value: string | number | boolean, label: string) {
        this.value = value;
        this.label = label;
    }
}

export class SelectionParameter extends ParameterNode {
    value: string;
    options: SelectionOption[];

    constructor(label: string, key: string, value: string) {
        super(label, key);
        this.value = value;
        this.options = [];
    }

    addOption(option: SelectionOption) {
        this.options.push(option);
    }
}

export class ZfsDatasetParameter extends ParameterNode {
    constructor(label: string, key: string, host: string = "", port: number = 0, pool: string = "", dataset: string = "") {
        super(label, key);
        
        // Add child parameters
        this.addChild(new StringParameter("Host", "host", host));
        this.addChild(new IntParameter("Port", "port", port));
        
        const poolParam = new SelectionParameter("Pool", "pool", pool);
        this.addChild(poolParam);
        
        const datasetParam = new SelectionParameter("Dataset", "dataset", dataset);     
        this.addChild(datasetParam);
    }

    // Method to create ZfsDatasetParameter from a location
    static fromLocation(label: string, key: string, location: LocationType): ZfsDatasetParameter {
        const { host, port, root, path } = location;
        return new ZfsDatasetParameter(label, key, host, port, root, path);
    }

    // Method to convert ZfsDatasetParameter to a location
    toLocation(): LocationType {
        // const label = (this.children[0] as StringParameter).value;
        // const key = (this.children[1] as StringParameter).value;
        const host = (this.children[2] as StringParameter).value;
        const port = (this.children[3] as IntParameter).value;
        const root = (this.children[4] as SelectionParameter).value;
        const path = (this.children[5] as SelectionParameter).value;

        return { host, port, root, path };
    }
}