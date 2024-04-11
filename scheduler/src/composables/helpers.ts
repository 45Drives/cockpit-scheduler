import { useSpawn, errorString } from '@45drives/cockpit-helpers';
import { ref, Ref } from 'vue';
// @ts-ignore
import test_ssh_script from"../scripts/test-ssh.py?raw";

//change true to 'on' and false to 'off'
export function isBoolOnOff(bool : boolean) {
	if (bool) {return 'on'} else {return 'off'}
}

//change 'on' to true and 'off' to false
export function onOffToBool(state : string) {
    if (state == 'on') { return true } else if (state == 'off') { return false }
}

//change 'yes' to true and 'no' to false
export function yesNoToBool(state: string) {
	if (state == 'yes') { return true } else if (state == 'no') { return false }
}

//change the first letter of a word to upper case
export const upperCaseWord = (word => {
	let lowerCaseWord = word.toLowerCase();
	let firstLetter  = lowerCaseWord.charAt(0);
	let remainingLetters = lowerCaseWord.substring(1);
	let firstLetterCap = firstLetter.toUpperCase();
	return firstLetterCap + remainingLetters;
});

//get a string output of the current timestamp
export function getTimestampString() {
	const currentDateTime = new Date();
	const timestampString = currentDateTime.toLocaleString('en-US', {
		hour: 'numeric',
		minute: 'numeric',
		second: 'numeric',
		day: '2-digit',
		month: '2-digit',
		year: 'numeric'
	});

	//console.log("timestampString:", timestampString);
	
	return timestampString;
}

export function getSnapshotTimestamp() {
	const currentDateTime = new Date();
  
	const year = currentDateTime.getFullYear();
	const month = String(currentDateTime.getMonth() + 1).padStart(2, '0'); // Adding 1 because months are zero-based
	const day = String(currentDateTime.getDate()).padStart(2, '0');
	const hour = String(currentDateTime.getHours()).padStart(2, '0');
	const minute = String(currentDateTime.getMinutes()).padStart(2, '0');
	const second = String(currentDateTime.getSeconds()).padStart(2, '0');
  
	const timestamp = `${year}.${month}.${day}-${hour}.${minute}.${second}`;
  
	return timestamp;
}

/* export function getRawTimestampFromString(timestampString) {
	const rawTimestamp = new Date(timestampString).getTime() / 1000;
	return rawTimestamp;
}
 */
export function getRawTimestampFromString(timestampString) {
	// Check if timestampString is undefined or null
	if (timestampString === undefined || timestampString === null) {
	  // Return an appropriate value, for example, you can return null or throw an error
	  return null; // or throw new Error('Timestamp string is undefined or null');
	}
  
	const rawTimestamp = new Date(timestampString).getTime() / 1000;
	return rawTimestamp;
}

export function convertRawTimestampToString(rawTimestamp) {
	const date = new Date(rawTimestamp * 1000);
    const timestamp = date.toISOString().replace(/T|Z/g, ' ').trim();
    return timestamp.substring(0, 19);
}

export function convertTimestampToLocal(timestamp) {
    // Check if the timestamp already has a space between date and time
    const hasSpace = timestamp.includes(' ');

    // If it has a space, use it directly; otherwise, convert to the desired format
    const utcTimestamp = hasSpace ? timestamp.replace(' ', 'T') + 'Z' : timestamp;

    const localTimestamp = new Date(utcTimestamp).toLocaleString('en-US', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    });

    const rearrangedTimestamp = localTimestamp.replace(/\//g, '-').replace(',', '');

    const [date, time] = rearrangedTimestamp.split(' ');

    const [month, day, year] = date.split('-');
    const rearrangedDate = `${year}-${month}-${day}`;

    const finalTimestamp = `${rearrangedDate} ${time}`;

    return finalTimestamp;
}

export function convertTimestampFormat(timestamp) {
    const parsedTimestamp = new Date(timestamp);
    const year = parsedTimestamp.getFullYear();
    const month = (parsedTimestamp.getMonth() + 1).toString().padStart(2, '0');
    const day = parsedTimestamp.getDate().toString().padStart(2, '0');
    const hours = parsedTimestamp.getHours().toString().padStart(2, '0');
    const minutes = parsedTimestamp.getMinutes().toString().padStart(2, '0');
    const seconds = parsedTimestamp.getSeconds().toString().padStart(2, '0');

    const customFormat = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    return customFormat;
}
  
export function getParentPath(datasetName) {
	const segments = datasetName.split('/');
	segments.pop();
	return segments.join('/');
}

export function convertSecondsToString(seconds) {
    let result = '';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) {
        result += `${hours} hour${hours > 1 ? 's' : ''} `;
    }
    
    if (minutes > 0) {
        result += `${minutes} minute${minutes > 1 ? 's' : ''} `;
    }

    if (hours === 0 && minutes === 0) {
        result += `${seconds} second${seconds > 1 ? 's' : ''} `;
    }
    
    return result.trim();
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

export function truncateName(name : string, threshold : number) {
    return (name.length > threshold ? name.slice(0, threshold) + '...' : name)
}