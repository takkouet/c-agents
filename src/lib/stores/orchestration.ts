// Orchestration event types — mirrors the backend WebSocket payload schema.
// All timeline state is owned locally by AgentOrchestrationSidebar.svelte;
// this file also exposes a thin writable store for chat-history persistence.

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
	| 'agent_active'
	| 'agent_waiting' // agent paused, needs human input/approval
	| 'agent_done'
	| 'session_done';

export interface OrchestrationMessage {
	step: OrchestrationStep;
	session_id?: string;
	// agent identity — present on agent_* steps
	agent_id?: string;
	agent_label?: string;
	agent_icon?: string;
	agent_dept?: string;
	// agent_active: specific task assigned
	action?: string;
	// agent_waiting: what the agent is waiting for
	waiting_message?: string;
	// human-readable status
	message?: string;
}

// Timeline item status
export type ItemStatus = 'idle' | 'active' | 'waiting' | 'done';

export interface TimelineItem {
	id: string;
	label: string;
	icon: string;
	department: string;
	action: string;
	status: ItemStatus;
	waitingMessage?: string; // shown in amber card when status === 'waiting'
}
