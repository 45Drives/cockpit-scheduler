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
import get_this_task_status_script from '../scripts/get-task-status.py?raw';
//@ts-ignore
import check_timer_script from '../scripts/check-timer.py?raw';
//@ts-ignore
import enable_timer_script from '../scripts/enable-timer.py?raw';
//@ts-ignore
import disable_timer_script from '../scripts/disable-timer.py?raw';
//@ts-ignore
import get_latest_task_execution_script from '../scripts/get-this-latest-task-log-result.py?raw';
//@ts-ignore
import get_task_execution_log_script from '../scripts/get-task-log-results.py?raw';

//['/usr/bin/env', 'python3', '-c', script, ...args ]

export async function executePythonScript(script: string, args: string[]): Promise<any> {
    try {
        const command = ['/usr/bin/env', 'python3', '-c', script, ...args];
        const state = useSpawn(command);

        const output = await state.promise();
        console.log(`output:`, output);
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
        console.log('get execution result output:', output);
        const result = JSON.parse(output.stdout);
        return result;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function getTaskExecutionResults(taskName, timestamp) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_task_execution_log_script, '-u', taskName, '-t', timestamp], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('get task execution results output:', output);
        const result = output.stdout;
        return result;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

/* 
export async function createTaskFiles(serviceTemplate, envFile, timerTemplate, scheduleFile) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', generate_task_files_script, '-st', serviceTemplate, '-e', envFile, '-tt', timerTemplate, '-s', scheduleFile], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('scheduled task creation output:', output);

    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}
export async function createStandaloneTask(serviceTemplate, envFile) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', generate_standalone_task_script, '-st', serviceTemplate, '-e', envFile], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('unscheduled task creation output:', output);

    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function createScheduleForTask(taskName, timerTemplate, scheduleFile) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', generate_schedule_script, '-n', taskName, '-tt', timerTemplate, '-s', scheduleFile], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('schedule creation output:', output);

    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function removeTask(taskName) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', remove_task_script, taskName], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('remove task output:', output);
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function runTask(taskName) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', run_task_script, taskName], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('run task output:', output);

    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function checkTaskTimer(taskName) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', check_timer_script, taskName], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('check task timer output:', output);
        const result = output.stdout;
        return result;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function enableTaskTimer(taskName) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', enable_timer_script, taskName], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('enable task output:', output);
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}

export async function disableTaskTimer(taskName) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', disable_timer_script, taskName], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        console.log('disable task output:', output);
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
}


export async function getTaskStatus(taskName) {
    try {
        const state = useSpawn(['/usr/bin/env', 'python3', '-c', get_this_task_status_script, taskName], { superuser: 'try', stderr: 'out' });

        const output = await state.promise();
        const result = output.stdout;
        // console.log(`${taskName} status:`, result);
        return result;
    } catch (error) {
        console.error(errorString(error));
        return false;
    }
} */

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

export async function checkTaskTimer(taskName) {
    return executePythonScript(check_timer_script, [taskName]);
}

export async function enableTaskTimer(taskName) {
    return executePythonScript(enable_timer_script, [taskName]);
}

export async function disableTaskTimer(taskName) {
    return executePythonScript(disable_timer_script, [taskName]);
}

export async function getTaskStatus(taskName) {
    return executePythonScript(get_this_task_status_script, [taskName]);
}
