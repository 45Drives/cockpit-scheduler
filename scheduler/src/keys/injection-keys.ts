import { type InjectionKey, type Ref } from "vue";
import { Scheduler } from '../models/Scheduler';
import { TaskExecutionLog } from '../models/TaskLog';
import { TaskInstance, TaskTemplate } from '../models/Tasks';

export const loadingInjectionKey: InjectionKey<Ref<boolean>> = Symbol('loading');
export const schedulerInjectionKey: InjectionKey<Scheduler> = Symbol('scheduler');
export const logInjectionKey: InjectionKey<TaskExecutionLog> = Symbol('log');
export const taskInstancesInjectionKey: InjectionKey<Ref<TaskInstance[]>> = Symbol('task-instances');
export const taskTemplatesInjectionKey: InjectionKey<TaskTemplate[]> = Symbol('task-templates');