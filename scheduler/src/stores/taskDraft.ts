import { defineStore } from 'pinia';

export const useTaskDraftStore = defineStore('taskDraft', {
    state: () => ({ draft: null as any, mode: 'create' as 'create' | 'edit' }),
    actions: {
        setDraft(task: any, mode: 'create' | 'edit') { this.draft = task; this.mode = mode; },
        clear() { this.draft = null; this.mode = 'create'; },
    },
});