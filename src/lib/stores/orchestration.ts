import { writable } from 'svelte/store';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const orchestrationEvents = writable<any[]>([]);

// true once the chat response is fully delivered; prevents background orchestrator
// calls (title generation, pipeline hooks) from resetting the timeline.
export const orchestrationDone = writable(false);

export function lockOrchestration() {
	orchestrationDone.set(true);
}

export function resetOrchestration() {
	orchestrationEvents.set([]);
	orchestrationDone.set(false);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function pushOrchestrationEvent(event: any) {
	orchestrationEvents.update((events) => [...events, event]);
}

export type OrchestrationStep =
	| 'connected'
	| 'session_start'
	| 'routing'
	| 'agent_active'
	| 'agent_waiting'
	| 'agent_done'
	| 'session_done';

export interface OrchestrationMessage {
	step: OrchestrationStep;
	session_id?: string;
	agent_id?: string;
	agent_label?: string;
	agent_icon?: string;
	agent_dept?: string;
	action?: string;
	waiting_message?: string;
	message?: string;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	agents?: any[];
}

export type ItemStatus = 'idle' | 'active' | 'waiting' | 'done';

export interface TimelineItem {
	id: string;
	label: string;
	icon: string;
	department: string;
	action: string;
	status: ItemStatus;
	waitingMessage?: string;
}
