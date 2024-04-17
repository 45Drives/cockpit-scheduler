import { useSpawn, errorString } from '@45drives/cockpit-helpers';
// @ts-ignore
import get_tasks_script from '../scripts/get-task-instances.py?raw';
// @ts-ignore
import get_datasets_script from '../scripts/get-datasets-in-pool.py?raw';
// @ts-ignore
import get_pools_script from '../scripts/get-pools.py?raw';

//['/usr/bin/env', 'python3', '-c', script, ...args ]

export async function getTaskData() {
    try {
        const state = useSpawn(['/usr/bin/env','python3', '-c', get_tasks_script], {superuser: 'try'});
        const tasksOutput = (await state.promise()).stdout;
        // console.log('Raw tasksOutput:', tasksOutput);
        const tasksData = JSON.parse(tasksOutput);
        return tasksData;
    } catch (state) {
        console.error(errorString(state));
        return null;
    }
}


export async function getPoolData(host?, port?, user?) {
    try {
        const cmd = ['/usr/bin/env', 'python3', '-c', get_pools_script]
        if (host) {
            cmd.push('--host');
            cmd.push(host);
        }
        if (port) {
            cmd.push('--port');
            cmd.push(port);
        }
        if (user) {
            cmd.push('--user');
            cmd.push(user);
        }
        const state = useSpawn(cmd, {superuser: 'try'});

        try {
            const result = (await state.promise()).stdout; // This contains the JSON string
            // console.log('raw script output (pools):', result);
            const parsedResult = JSON.parse(result); // Parse the JSON string into an object
            if (parsedResult.success) {
                // console.log('Pools array:', parsedResult.data);
                return parsedResult.data;
            } else if (parsedResult.error) {
                console.error('Script error:', parsedResult.error);
            } else {
                console.log('Script executed but no pools found.');
            }
            
        } catch (error) {
            console.error('Error parsing JSON or during script execution:', error);
        }
       
        
    } catch (state) {
        console.error(errorString(state));
        return null;
    }
}


export async function getDatasetData(pool, host?, port?, user?) {
    try {
        const cmd = ['/usr/bin/env', 'python3', '-c', get_datasets_script]

        cmd.push('--pool');
        cmd.push(pool);

        if (host) {
            cmd.push('--host');
            cmd.push(host);
        }
        if (port) {
            cmd.push('--port');
            cmd.push(port);
        }
        if (user) {
            cmd.push('--user');
            cmd.push(user);
        }
       
        const state = useSpawn(cmd, {superuser: 'try'});

        try {
            const result = (await state.promise()).stdout; // This contains the JSON string
            // console.log('raw script output (pools):', result);
            const parsedResult = JSON.parse(result); // Parse the JSON string into an object
            if (parsedResult.success) {
                // console.log('Pools array:', parsedResult.data);
                return parsedResult.data;
            } else if (parsedResult.error) {
                console.error('Script error:', parsedResult.error);
            } else {
                console.log('Script executed but no pools found.');
            }
            
        } catch (error) {
            console.error('Error parsing JSON or during script execution:', error);
        }

    } catch (state) {
        console.error(errorString(state));
        return null;
    }
}