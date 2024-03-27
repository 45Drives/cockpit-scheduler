// Tasks.ts
import { ParameterNode, SelectionParameter, SelectionOption, StringParameter, BoolParameter, IntParameter, ZfsDatasetParameter } from './Parameters';
export class TaskTemplate {
    name: string;
    parameterSchema: ParameterNode;

    constructor(name: string, parameterSchema: ParameterNode) {
        this.name = name;
        this.parameterSchema = parameterSchema;
    }
}


// // Create parameter schema for ZFS replication task
// const parameterSchema = new ParameterNode("ZFS Replication Config", "zfsRepConfig");
// const sourceDatasetParam = new ZfsDatasetParameter("Source Dataset", "sourceDataset");
// const destinationDatasetParam = new ZfsDatasetParameter("Destination Dataset", "destDataset");
// const compressionParam = new BoolParameter("Compression", "compress", false);
// const rawParam = new BoolParameter("Raw", "raw", false);

// parameterSchema.addChild(sourceDatasetParam);
// parameterSchema.addChild(destinationDatasetParam);
// parameterSchema.addChild(compressionParam);

// // Instantiate TaskTemplate for ZFS replication task
// export const zfsReplicationTaskTemplate = new TaskTemplate("ZFS Replication Task", parameterSchema);
