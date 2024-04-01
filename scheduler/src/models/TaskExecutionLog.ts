export class TaskExecutionLog {
    entries: TaskExecutionResult[];

    constructor(entries: TaskExecutionResult[]) {
        this.entries = entries;
    }

    loadEntries() {

    }

    getEntriesFor(TaskInstance) {
        // return TaskExecutionResult[];
    }

    getLatesEntryFor(TaskInstance) {
        return TaskExecutionResult || 'None';
    }

}

export class TaskExecutionResult {
    exitCode: number;
    output: string;
    startDate: Date;
    finishDate: Date;

    constructor(exitCode: number, output: string, startDate: Date, finishDate: Date) {
        this.exitCode = exitCode;
        this.output = output;
        this.startDate = startDate;
        this.finishDate = finishDate;
    }
}

