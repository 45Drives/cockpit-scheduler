import { useSpawn, errorString } from '@45drives/cockpit-helpers';
// @ts-ignore
import get_tasks_script from '../scripts/get-task-instances.py?raw';
// @ts-ignore
import get_datasets_script from '../scripts/get-datasets-in-pool.py?raw';
// @ts-ignore
import get_pools_script from '../scripts/get-pools.py?raw';
// @ts-ignore
import test_ssh_script from '../scripts/test-ssh.py?raw';
//@ts-ignore
import generate_task_files_script from '../scripts/make-and-start-task.py?raw';
//@ts-ignore
import generate_standalone_task_script from '../scripts/make-standalone-task.py?raw';
//@ts-ignore
import generate_schedule_script from '../scripts/make-schedule.py?raw';
//@ts-ignore
import remove_task_script from '../scripts/remove-task-files.py?raw';
//@ts-ignore
import run_task_script from '../scripts/run-task-now.py?raw';
//@ts-ignore
import get_latest_task_execution_script from '../scripts/get-this-latest-task-log-result.py?raw';

export async function executePythonScript(script: string, args: string[]): Promise<any> {
    try {
        const command = ['/usr/bin/env', 'python3', '-c', script, ...args];
        const state = useSpawn(command, { superuser: 'try' });

        const output = await state.promise();
        // console.log(`output:`, output);
        return output.stdout;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

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
                console.log('Pools array:', parsedResult.data);
                return parsedResult.data;
            } else if (parsedResult.error) {
                console.error('Script error:', parsedResult.error);
            } else {
                console.log('Script executed but no pools found.');
            }
            
        } catch (error) {
            // console.error('Error parsing JSON or during script execution:', error);
            return [];
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
                console.log('Datasets array:', parsedResult.data);
                return parsedResult.data;
            } else if (parsedResult.error) {
                console.error('Script error:', parsedResult.error);
            } else {
                console.log('Script executed but no pools found.');
            }
            
        } catch (error) {
            // console.error('Error parsing JSON or during script execution:', error);
            return [];
        }

    } catch (state) {
        console.error(errorString(state));
        return null;
    }
}

export async function testSSH(sshTarget) {
    try {
        console.log(`target: ${sshTarget}`);
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', test_ssh_script, sshTarget], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('testSSH output:', output);

        if (output.stdout.includes('True')) {
			return true;
		} else {
			return false;
		}
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function getLatestTaskExecutionResult(taskName) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_latest_task_execution_script, taskName], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        // console.log('get execution result output:', output);
        const result = JSON.parse(output.stdout);
        return result;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function getTaskExecutionResults(serviceName, untilTime) {
    try {
        let command;
        if (untilTime) {
            command = ['journalctl', '-r', '-u', serviceName, '--until', untilTime, '--no-pager'];
        } else {
            console.log("No until time provided");
            return "No until time available.";
        }

        const state = useSpawn(command, { superuser: 'try' });
        const result = await state.promise();

        return result.stdout.trim();
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}


export async function createTaskFiles(serviceTemplate, envFile, timerTemplate, scheduleFile) {
    return executePythonScript(generate_task_files_script, ['-st', serviceTemplate, '-e', envFile, '-tt', timerTemplate, '-s', scheduleFile]);
}

export async function createStandaloneTask(serviceTemplate, envFile) {
    return executePythonScript(generate_standalone_task_script, ['-st', serviceTemplate, '-e', envFile]);
}

export async function createScheduleForTask(taskName, timerTemplate, scheduleFile) {
    return executePythonScript(generate_schedule_script, ['-n', taskName, '-tt', timerTemplate, '-s', scheduleFile]);
}

export async function removeTask(taskName) {
    return executePythonScript(remove_task_script, [taskName]);
}

export async function runTask(taskName) {
    return executePythonScript(run_task_script, [taskName]);
}

export async function enableTaskTimer(taskName) {
    const timerName = `${taskName}.timer`;
    try {
        // Reload the system daemon
        let command = ['sudo', 'systemctl', 'daemon-reload'];
        let state = useSpawn(command, { superuser: 'try' });
        await state.promise();

        // Enable the timer
        command = ['sudo', 'systemctl', 'enable', timerName];
        state = useSpawn(command, { superuser: 'try' });
        await state.promise();

        // Start the timer
        command = ['sudo', 'systemctl', 'start', timerName];
        state = useSpawn(command, { superuser: 'try' });
        await state.promise();

        console.log(`${timerName} has been enabled and started`);
        return `${timerName} has been enabled and started`;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}


export async function disableTaskTimer(taskName) {
    const timerName = `${taskName}.timer`;
    try {
        // Stop the timer 
        let command = ['sudo', 'systemctl', 'stop', timerName];
        let state = useSpawn(command, { superuser: 'try' });
        await state.promise();

        // Disable the timer
        command = ['sudo', 'systemctl', 'disable', timerName];
        state = useSpawn(command, { superuser: 'try' });
        await state.promise();

        // Reload the system daemon
        command = ['sudo', 'systemctl', 'daemon-reload'];
        state = useSpawn(command, { superuser: 'try' });
        await state.promise();

        console.log(`${timerName} has been stopped and disabled`);
        return `${timerName} has been stopped and disabled`;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}


export async function getTaskStatus(taskName) {
    let result, output;
    try {
        const command = ['systemctl', 'status', `${taskName}.timer`, '--no-pager', '--output=cat'];
        const state = useSpawn(command, { superuser: 'try'});
        result = await state.promise();
        output = result.stdout;

    } catch (error) {
        // console.error(errorString(error));
        // return false;
        return 'Not scheduled';
    }

    try {
        let status = '';
        const activeStatusRegex = /^\s*Active:\s*(\w+\s*\([^)]*\))/m;
        const activeStatusMatch = output.match(activeStatusRegex);

        if (activeStatusMatch) {
            status = activeStatusMatch[1].trim();
        } else {
            status = "No schedule found.";
        }
        // console.log(`Status for ${taskName}`, status);
        return status;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}
