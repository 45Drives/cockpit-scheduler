<template>
    <div class="mt-2">
       <!--  <div v-if="props.param.children.length > 0">
            <div v-for="child in props.param.children">
                <label class="mt-1 block text-sm leading-6 text-default">{{ child.label }}</label>
                <input type="text" v-model="child.value" class="mt-1 block w-full input-textlike bg-default" />
            </div>
        </div>
        <div v-else>
            <label class="mt-1 block text-sm leading-6 text-default">{{ props.param.label }}</label>
            <input type="text" v-model="props.param.value" class="mt-1 block w-full input-textlike bg-default" />
        </div> -->
        <!-- <div>
            <StringParam v-if="props.type == 'string'" />
            <IntParam v-if="props.type == 'int'"/>
            <BoolParam v-if="props.type == 'bool'"/>
            <SelectParam v-if="props.type == 'select'"/> 
        </div>-->

        <!-- <div v-if="props.selectedTemplate">
            <template v-for="param in props.selectedTemplate.parameterSchema" :key="param.key">
                <label :for="param.key">{{ param.label }}</label>
                <input v-if="renderInput(param) === 'text'" type="text" v-model="param.value"/>
                <input v-if="renderInput(param) === 'checkbox'" type="checkbox" v-model="param.value"/>
                <input v-if="renderInput(param) === 'number'" type="number" v-model="param.value"/>
                <select v-if="renderInput(param) === 'selectbox'" v-model="param.value">
                    <option v-for="option in param.options" :value="option.value">{{ option.label }}</option>
                </select>

                <div v-if="param.children">
                    <ParameterInput v-if="param.children" :selectedTemplate="param"/>
                </div>
            </template>
        </div> -->

        <div v-if="selectedTemplate.name == 'ZFS Replication Task'">
            <div name="task-name">
                <label class="mt-1 block text-sm leading-6 text-default">Task Name</label>
                <input type="text" v-model="newTaskName" class="mt-1 block w-full input-textlike bg-default" placeholder="New Task"/> 
                <!-- Limit name input to alphanumeric, special chars? (NO UNDERSCORE) -->
            </div>
            <div name="source-data">
                <legend>Replication Source</legend>
                <div name="source-pool">
                    <label class="mt-1 block text-sm leading-6 text-default">Pool</label>
                    <select class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">

                    </select>
                </div>
                <div name="source-dataset">
                    <select class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">

                    </select>
                </div>
            </div>
          
            <div name="destination-data">
                <legend>Replication Target</legend>
                <div name="destination-host">

                </div>
                <div name="destination-user">

                </div>
                <div name="destination-port">

                </div>
            </div>
            
            <div name="destination-pool">
                <select class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">

                </select>
            </div>
            <div name="destination-dataset">
                <select class="text-default bg-default mt-1 block w-full input-textlike sm:text-sm sm:leading-6">

                </select>
            </div>
        </div>
    </div>
</template>
<script setup lang="ts">
import StringParam from '../parameters/StringParam.vue';
import BoolParam from '../parameters/BoolParam.vue';
import SelectParam from '../parameters/SelectParam.vue';
import IntParam from '../parameters/IntParam.vue';
import { ref, Ref, reactive, computed, onMounted } from 'vue';
import { ZFSReplicationTaskTemplate, TaskTemplate, ParameterNode, ZfsDatasetParameter, SelectionOption, SelectionParameter, IntParameter, StringParameter, BoolParameter, TaskInstance } from '../../models/Classes';

interface ParameterInputProps {
//    parameterSchema: ParameterNode;
    selectedTemplate: TaskTemplateType;
}

const props = defineProps<ParameterInputProps>();

const newTaskName = ref('');

// const sourceData = new ZfsDatasetParameter('Source', 'source');
// sourceData.loadPools()
// console.log(sourceData)
const parameters = ref([]);

const setupParameters = () => {
    if (!props.selectedTemplate) return;
    parameters.value = cloneParameterNode(props.selectedTemplate.parameterSchema);
    console.log(parameters);
}

// const renderInput = (param) => {
//     switch (param.constructor.name) {
//         case 'BoolParameter':
//             return 'checkbox';
//         case 'IntParameter':
//             return 'number';
//         case 'StringParameter':
//             return 'text';
//         case 'SelectParameter':
//             return 'selectbox';
//         default:
//             return 'text';
//     }
// }

function cloneParameterNode(node) {
        let clonedNode;
      
        if (node instanceof StringParameter) {
          clonedNode = new StringParameter(node.label, node.key, node.value);
        } else if (node instanceof IntParameter) {
          clonedNode = new IntParameter(node.label, node.key, node.value);
        } else if (node instanceof BoolParameter) {
          clonedNode = new BoolParameter(node.label, node.key, node.value);
        } else if (node instanceof SelectionParameter) {
          clonedNode = new SelectionParameter(node.label, node.key, node.value, [...node.options]);
        } else if (node instanceof ZfsDatasetParameter) {
            const host = node.getChild('host').value;
            const port = node.getChild('port').value;
            const user = node.getChild('user').value;
            const pool = node.getChild('pool').value;
            const dataset = node.getChild('dataset').value;
            clonedNode = new ZfsDatasetParameter(node.label, node.key, host, port, user, pool, dataset);
        } else {
          clonedNode = new ParameterNode(node.label, node.key);
        }
      
        // Recursively clone children
        node.children.forEach(child => {
          clonedNode.addChild(cloneParameterNode(child));
        });
      
        return clonedNode;
      }

onMounted(() => {
    setupParameters();
});
</script>