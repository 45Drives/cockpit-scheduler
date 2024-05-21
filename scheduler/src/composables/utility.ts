import { useSpawn, errorString } from '@45drives/cockpit-helpers';
// @ts-ignore
import get_zfs_data_script from '../scripts/get-zfs-data.py?raw';
// @ts-ignore
import test_ssh_script from '../scripts/test-ssh.py?raw';
//@ts-ignore
import task_file_creation_script from '../scripts/task-file-creation.py?raw';
//@ts-ignore
import remove_task_script from '../scripts/remove-task-files.py?raw';
//@ts-ignore
import run_task_script from '../scripts/run-task-now.py?raw';

export async function getPoolData(host?, port?, user?) {
    try {
        const cmd = ['/usr/bin/env', 'python3', '-c', get_zfs_data_script, '-t', 'pools']
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
        const cmd = ['/usr/bin/env', 'python3', '-c', get_zfs_data_script, '-t', 'datasets']

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

export async function createTaskFiles(serviceTemplate, envFile, timerTemplate, scheduleFile) {
    return executePythonScript(task_file_creation_script, ['-t', 'create-task-schedule', '-st', serviceTemplate, '-e', envFile, '-tt', timerTemplate, '-s', scheduleFile]);
}

export async function createStandaloneTask(serviceTemplate, envFile) {
    return executePythonScript(task_file_creation_script, ['-t', 'create-task', '-st', serviceTemplate, '-e', envFile]);
}

export async function createScheduleForTask(taskName, timerTemplate, scheduleFile) {
    return executePythonScript(task_file_creation_script, ['-t', 'create-schedule', '-n', taskName, '-tt', timerTemplate, '-s', scheduleFile]);
}

export async function removeTask(taskName) {
    return executePythonScript(remove_task_script, [taskName]);
}

export async function runTask(taskName) {
    return executePythonScript(run_task_script, [taskName]);
}

//change the first letter of a word to upper case
export const upperCaseWord = (word => {
	let lowerCaseWord = word.toLowerCase();
	let firstLetter  = lowerCaseWord.charAt(0);
	let remainingLetters = lowerCaseWord.substring(1);
	let firstLetterCap = firstLetter.toUpperCase();
	return firstLetterCap + remainingLetters;
});

export function boolToYesNo(state: boolean) {
	if (state == true) { return 'Yes' } else if (state == false) { return 'No' }
}

export function formatTemplateName(templateName) {
    // Split the string into words using space as the delimiter
    let words = templateName.split(' ');
    // Capitalize the first letter of each word and lowercase the rest
    let formattedWords = words.map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
    // Join the words without spaces
    let formattedTemplateName = formattedWords.join('');
    return formattedTemplateName;
}