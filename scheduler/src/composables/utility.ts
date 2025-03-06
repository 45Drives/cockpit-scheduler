import { legacy } from "@45drives/houston-common-lib";
// @ts-ignore
import get_zfs_data_script from "../scripts/get-zfs-data.py?raw";
// @ts-ignore
import test_ssh_script from "../scripts/test-ssh.py?raw";
// @ts-ignore
import test_netcat_script from '../scripts/test-netcat.py?raw'
//@ts-ignore
import task_file_creation_script from "../scripts/task-file-creation.py?raw";
//@ts-ignore
import remove_task_script from "../scripts/remove-task-files.py?raw";
//@ts-ignore
import run_task_script from "../scripts/run-task-now.py?raw";
//@ts-ignore
import get_disks_script from "../scripts/get-disk-data.py?raw";

import { inject, InjectionKey, ref } from "vue";

const { useSpawn, errorString } = legacy;

export function injectWithCheck<T>(
  key: InjectionKey<T>,
  errorMessage: string
): T {
  const injectedValue = inject(key)!;
  if (!injectedValue) {
	throw new Error(errorMessage);
  }
  return injectedValue;
}

/* Getting values from Parameter structure to display in table */
export function findValue(obj, targetKey, valueKey) {
  if (!obj || typeof obj !== "object") return null;

  // Directly check at the current level if this is the targetKey
  if (obj.key === targetKey) {
	// If looking for the same key as targetKey and it has a value, return it
	if (targetKey === valueKey && obj.value !== undefined) {
	  return obj.value;
	}
	// If there's a different valueKey to find, look for it among children
	let foundChild = obj.children?.find((child) => child.key === valueKey);
	if (foundChild && foundChild.value !== undefined) {
	  return foundChild.value;
	}
  }

  // If no value found at this level, and there are children, search them recursively
  if (Array.isArray(obj.children)) {
	for (let child of obj.children) {
	  const result = findValue(child, targetKey, valueKey);
	  if (result !== null) {
		// Ensure '0', 'false', or empty string are considered valid returns
		return result;
	  }
	}
  }

  return null; // If the search yields no results, return null
}

export async function getPoolData(host?, port?, user?) {
  try {
	const cmd = [
	  "/usr/bin/env",
	  "python3",
	  "-c",
	  get_zfs_data_script,
	  "-t",
	  "pools",
	];
	if (host) {
	  cmd.push("--host");
	  cmd.push(host);
	}
	if (port) {
	  cmd.push("--port");
	  cmd.push(port);
	}
	if (user) {
	  cmd.push("--user");
	  cmd.push(user);
	}
	const state = useSpawn(cmd, { superuser: "try" });

	try {
	  const result = (await state.promise()).stdout!; // This contains the JSON string
	  // console.log('raw script output (pools):', result);
	  const parsedResult = JSON.parse(result); // Parse the JSON string into an object
	  if (parsedResult.success) {
	  //  console.log("Pools array:", parsedResult.data);
		return parsedResult.data;
	  } else if (parsedResult.error) {
		console.error("Script error:", parsedResult.error);
	  } else {
		console.log("Script executed but no pools found.");
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
	const cmd = [
	  "/usr/bin/env",
	  "python3",
	  "-c",
	  get_zfs_data_script,
	  "-t",
	  "datasets",
	];

	cmd.push("--pool");
	cmd.push(pool);

	if (host) {
	  cmd.push("--host");
	  cmd.push(host);
	}
	if (port) {
	  cmd.push("--port");
	  cmd.push(port);
	}
	if (user) {
	  cmd.push("--user");
	  cmd.push(user);
	}

	const state = useSpawn(cmd, { superuser: "try" });

	try {
	  const result = (await state.promise()).stdout!; // This contains the JSON string
	  // console.log('raw script output (pools):', result);
	  const parsedResult = JSON.parse(result); // Parse the JSON string into an object
	  if (parsedResult.success) {
	  //  console.log("Datasets array:", parsedResult.data);
		return parsedResult.data;
	  } else if (parsedResult.error) {
		console.error("Script error:", parsedResult.error);
	  } else {
		console.log("Script executed but no pools found.");
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
  //  console.log(`target: ${sshTarget}`);
	const state = useSpawn(
	  ["/usr/bin/env", "python3", "-c", test_ssh_script, sshTarget],
	  { superuser: "try", err: "out" }
	);

	const output = await state.promise();
  //  console.log("testSSH output:", output);

	if (output.stdout!.includes("True")) {
	  return true;
	} else {
	  return false;
	}
  } catch (error) {
	console.error(errorString(error));
	return false;
  }
}

export async function testNetcat(user, netcatHost, port) {
	try {
	  console.log(`target: ${netcatHost}, port: ${port}`);
	  
	  // Pass both hostname and port to the Python script
	  const state = useSpawn(
		["/usr/bin/env", "python3", "-c", test_netcat_script, user, netcatHost, port],
		{ superuser: "try" }
	  );
  
	  const output = await state.promise();
	  console.log("testNetcat output:", output);
  
	  // Check for "Connected" in stdout to confirm a successful connection
	  if (output.stdout!.includes("True")) {
		return true;
	  } else {
		return false;
	  }
	} catch (error) {
	  console.error(errorString(error));
	  return false;
	}
  }
  
export async function executePythonScript(
  script: string,
  args: string[]
): Promise<any> {
  try {
	const command = ["/usr/bin/env", "python3", "-c", script, ...args];
	const state = useSpawn(command, { superuser: "try" });

	const output = await state.promise();
	// console.log(`output:`, output);
	return output.stdout;
  } catch (error) {
	console.error(errorString(error));
	return false;
  }
}

export async function createTaskFiles(
  templateName,
  scriptPath,
  envFile,
  timerTemplate,
  scheduleFile
) {
	console.log("createTaskFiles ", templateName)
	console.log(" createTaskFiles Script Path: ",scriptPath)
  return executePythonScript(task_file_creation_script, [
	"-tN",
	templateName,
	"-t",
	"create-task-schedule",
	"-sP",
	scriptPath,
	"-e",
	envFile,
	"-tt",
	timerTemplate,
	"-s",
	scheduleFile,
  ]);
}

export async function createStandaloneTask(templateName, scriptPath, envFile) {
	console.log(" createStandaloneTask Template Name: ",templateName)

	console.log(" createStandaloneTask Script Path: ",scriptPath)

  return executePythonScript(task_file_creation_script, [
	"-tN",
	templateName,
	"-t",
	"create-task",
	"-sP",
	scriptPath,
	"-e",
	envFile,
  ]);
}

export async function createScheduleForTask(
  taskName,
  timerTemplate,
  scheduleFile
) {
  return executePythonScript(task_file_creation_script, [
	"-t",
	"create-schedule",
	"-n",
	taskName,
	"-tt",
	timerTemplate,
	"-s",
	scheduleFile,
  ]);
}

export async function removeTask(taskName) {
  return executePythonScript(remove_task_script, [taskName]);
}

export async function runTask(taskName) {
  return executePythonScript(run_task_script, [taskName]);
}

//change the first letter of a word to upper case
export const upperCaseWord = (word) => {
  let lowerCaseWord = word.toLowerCase();
  let firstLetter = lowerCaseWord.charAt(0);
  let remainingLetters = lowerCaseWord.substring(1);
  let firstLetterCap = firstLetter.toUpperCase();
  return firstLetterCap + remainingLetters;
};

export function boolToYesNo(state: boolean) {
  if (state == true) {
	return "Yes";
  } else if (state == false) {
	return "No";
  }
}

export function formatTemplateName(templateName) {
  // Split the string into words using space as the delimiter
  let words = templateName.split(" ");
  // Capitalize the first letter of each word and lowercase the rest
  let formattedWords = words.map(
	(word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
  );
  // Join the words without spaces
  let formattedTemplateName = formattedWords.join("");
  return formattedTemplateName;
}

export function validateNumber(field, number) {
  if (isNaN(number) || number < 0) {
	// errorList.value.push(`${field} must be a valid non-negative number.`);
	return false;
  } else {
	return true;
  }
}

export async function getDisks(diskGroup) {
  try {
	const state = useSpawn(
	  ["/usr/bin/env", "python3", "-c", get_disks_script],
	  { superuser: "try" }
	);
	const disks = (await state.promise()).stdout!;
	// return disks;
	const parsedJSON = JSON.parse(disks);
	//loops through and adds disk data from JSON to disk data object, pushes objects to disks array
	for (let i = 0; i < parsedJSON.length; i++) {
	  const disk: DiskData = {
		name: parsedJSON[i].name,
		capacity: parsedJSON[i].capacity,
		model: parsedJSON[i].model,
		type: parsedJSON[i].type,
		phy_path: parsedJSON[i].phy_path,
		sd_path: parsedJSON[i].sd_path,
		vdev_path: parsedJSON[i].vdev_path,
		serial: parsedJSON[i].serial,
		health: parsedJSON[i].health,
		temp: parsedJSON[i].temp,
	  };
	  diskGroup.value.push(disk);
	  // console.log("Disk:", disk);
	}
  } catch (state) {
	console.error(errorString(state));
	return null;
  }
}

export function getDiskIDName(
  disks: DiskData[],
  diskIdentifier: string,
  selectedDiskName: string
) {
  // console.log('disks:', disks, 'diskID:', diskIdentifier, 'selectedDiskName:', selectedDiskName);
  const phyPathPrefix = "/dev/disk/by-path/";
  const sdPathPrefix = "/dev/";
  const newDisk = ref();
  const diskName = ref("");
  const diskPath = ref("");

  newDisk.value = disks.find((disk) => disk.name === selectedDiskName);
  switch (diskIdentifier) {
	case "vdev_path":
	  diskPath.value = newDisk.value!.vdev_path;
	  diskName.value = selectedDiskName;
	  break;
	case "phy_path":
	  diskPath.value = newDisk.value!.phy_path;
	  diskName.value = diskPath.value.replace(phyPathPrefix, "");
	  break;
	case "sd_path":
	  diskPath.value = newDisk.value!.sd_path;
	  diskName.value = diskPath.value.replace(sdPathPrefix, "");
	  break;
	default:
	  console.log("error with selectedDiskNames/diskIdentifier");
	  break;
  }

  return { diskName: diskName.value, diskPath: diskPath.value };
}

export function truncateName(name: string, threshold: number) {
  return name.length > threshold ? name.slice(0, threshold) + "..." : name;
}

export function splitAndClean(inputString: string, isDisk: boolean) {
  // Trim any leading/trailing whitespace from string and remove both single and double quotes
  const cleanedString = inputString.trim().replace(/^['"]|['"]$/g, "");

  // Split the input string by comma
  const parts = cleanedString.split(",");

  // Trim any leading/trailing whitespace from each part and optionally remove the disk prefix
  const cleanedParts: string[] = parts.map((part) => {
	let cleanedPart = part.trim();
	// if (isDisk) {
	//     cleanedPart = cleanedPart.replace(/^\/dev\/disk\/by-vdev\//, '');
	// }
	return cleanedPart;
  });

  return cleanedParts;
}

export async function checkLocalPathExists(localPathStr: string): Promise<boolean> {
	try {
		console.log('Checking local path:', localPathStr);

		// Run 'test -e <path>' to check existence
		// test -e /the/dir && echo "exist" || echo "does not exist"
		const state = useSpawn(['test', '-e', localPathStr]);

		// Await the spawn state promise to get the exit code
		// const output = await state.promise();
		// if (output.stdout.includes("exists")) {
		//     return true;
		// } else {
		//     return false;
		// }

		await state.promise();
		// If the command succeeds, the path exists
		return true;
	} catch (error: any) {
		// If 'test' fails with status 1, it means the path does not exist
		if (error.status === 1) {
			console.log('Path does not exist:', localPathStr);
			return false;
		}

		// Log unexpected errors and rethrow them for debugging
		console.error('Unexpected error:', errorString(error));
		throw new Error(`Failed to check path existence: ${errorString(error)}`);
	}
}


export async function checkRemotePathExists(remoteName: string, remotePathStr: string) {
	try {
		console.log('remotePathStr:', remotePathStr);

		// Use 'rclone lsf' to list the remote path
		const state = useSpawn(['rclone', 'lsf', `${remoteName}:${remotePathStr}`]);

		// Await the promise and handle the exit code
		await state.promise();
		console.log('path exists');

		// If rclone lsf succeeds, the path exists
		return true;
	} catch (error: any) {
		// If 'rclone lsf' fails with exit code 1, it means the path does not exist
		if (error.status === 1) {
			console.log('Path does not exist');
			return false;
		}

		// Log unexpected errors
		console.error('Unexpected error:', JSON.stringify(error));
		return false;
	}
}

export async function isDatasetEmpty(mountpoint, user?: string, host?: string, port?: string) {
	try {
		const baseCommand = ['ls', '-la', `/${mountpoint}`,];
		let command: string[] = [];

	if (user && host) {
	  // Use SSH for remote command
	  command = ["ssh"];
	  if (port && port !== "22") {
		command.push("-p", port);
	  }
	  command.push(`${user}@${host}`, ...baseCommand);
	} else {
	  // Local command
	  command = baseCommand;
	}

	const state = useSpawn(command, { superuser: "try" });
	const output = await state.promise();
	// console.log(`output:`, output);
	// return output.stdout;

	// Split the output into lines
	const lines = output.stdout!.split("\n");

	// Define the regex pattern to match '.' and '..'
	const pattern =
	  /^\S+\s+\d+\s+\S+\s+\S+\s+\d+\s+\w+\s+\d+\s+\d+:\d+\s+(\.|\.\.)$/;

	// Check each line for matches
	const matches = lines.filter((line) => pattern.test(line));

	// If we find only '.' and '..', return true (dataset is empty)
	if (matches.length <= 2) {
	  console.log(`dataset at /${mountpoint} is empty`);
	  return true;
	} else {
	  console.log(`dataset at /${mountpoint} is NOT empty`);
	  return false;
	}
  } catch (error) {
	console.error(`Error checking dataset contents: ${errorString(error)}`);
	return false;
  }
}

export async function doSnapshotsExist(
  filesystem: string,
  user?: string,
  host?: string,
  port?: string
) {
  try {
	const baseCommand = ["zfs", "list", "-H", "-t", "snapshot", filesystem];
	let command: string[] = [];

	if (user && host) {
	  // Use SSH for remote command
	  command = ["ssh"];
	  if (port && port !== "22") {
		command.push("-p", port);
	  }
	  command.push(`${user}@${host}`, ...baseCommand);
	} else {
	  // Local command
	  command = baseCommand;
	}

	// Execute the command
	const state = useSpawn(command, { superuser: "try" }); // Ensure you handle superuser permissions if necessary
	const output = await state.promise();

	// Parse the output
	const lines = output.stdout!.trim().split("\n"); // Use trim() to remove empty lines
	if (lines.length === 1 && lines[0] === "") {
	  // If there's only one empty line, there are no snapshots
	  console.log("No snapshots found.");
	  return false;
	} else if (lines.length > 0) {
	  console.log("Snapshots exist, must overwrite dataset to continue.");
	  return true;
	}
  } catch (error) {
	console.error(`Error checking dataset contents: ${errorString(error)}`);
	return null;
  }
}
