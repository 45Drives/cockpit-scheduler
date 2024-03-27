
// Define dummy data for parameter nodes
const dummyParameterSchema: ParameterNode = {
    label: 'ZFS Replication Config',
    key: 'zfs_replication_config',
    children: [
      new StringParameter('Source Host', 'source_host'),
      new IntParameter('Source Port', 'source_port'),
      new StringParameter('Destination Host', 'dest_host'),
      new IntParameter('Destination Port', 'dest_port'),
      new BoolParameter('Compression', 'compress'),
      new ZfsDatasetParameter('Dataset'),
      // Add more parameters as needed
    ]
  };
  
  // Define dummy data for task templates
  const dummyTaskTemplates: TaskTemplate[] = [
    {
      name: 'ZFS Replication Task',
      parameterSchema: dummyParameterSchema,
    },
    // Add more task templates as needed
  ];
  
  // Define dummy data for task instances
  const dummyTaskInstances: TaskInstance[] = [
    // You can generate instances based on the templates
    {
      name: 'ZFS Replication Task 1',
      template: dummyTaskTemplates[0], // Assuming the first template is ZFS Replication Task
      parameters: { 
        source_host: 'example.com',
        source_port: 22,
        dest_host: 'backup.example.com',
        dest_port: 22,
        compress: true,
        // Add more parameters based on the template
      },
      schedule: { enabled: true, intervals: [{ value: 1, unit: 'days' }] },
    },
    // Add more task instances as needed
  ];
  
  // Export the dummy data
  export { dummyTaskTemplates, dummyTaskInstances };
  