<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { showOrchestrationSidebar } from '$lib/stores';
	import { orchestrationDone } from '$lib/stores/orchestration';
	import type { OrchestrationMessage, TimelineItem } from '$lib/stores/orchestration';
	import FlowView from './AgentOrchestrationSidebar/FlowView.svelte';

	// ── State ────────────────────────────────────────────────────────────
	const ORCHESTRATOR_IDLE: TimelineItem = {
		id: 'orchestrator',
		label: 'Orchestrator',
		icon: '🧠',
		department: 'Platform',
		action: 'Waiting for a request…',
		status: 'idle'
	};

	let timelineItems: TimelineItem[] = [{ ...ORCHESTRATOR_IDLE }];
	let currentSessionId: string | null = null;
	let globalStatus: 'idle' | 'active' | 'done' = 'idle';
	let statusMessage = 'Waiting for a request…';
	let viewMode: 'timeline' | 'flow' = 'timeline';

	// ── Helpers ──────────────────────────────────────────────────────────
	function updateItem(id: string, patch: Partial<TimelineItem>) {
		const idx = timelineItems.findIndex((i) => i.id === id);
		if (idx >= 0) {
			timelineItems[idx] = { ...timelineItems[idx], ...patch };
			timelineItems = timelineItems; // trigger Svelte reactivity
		}
	}

	function addOrUpdate(item: TimelineItem) {
		const idx = timelineItems.findIndex((i) => i.id === item.id);
		if (idx >= 0) {
			timelineItems[idx] = { ...timelineItems[idx], ...item };
			timelineItems = timelineItems;
		} else {
			timelineItems = [...timelineItems, item];
		}
	}

	// ── Event handler ────────────────────────────────────────────────────
	function handleMessage(msg: OrchestrationMessage) {
		// Guard: ignore stale events from a previous session
		if (msg.session_id && msg.session_id !== currentSessionId && msg.step !== 'session_start') {
			return;
		}

		switch (msg.step) {
			case 'session_start':
				if ($orchestrationDone) return; // locked — background call, response already in UI
				currentSessionId = msg.session_id ?? null;
				timelineItems = [
					{ ...ORCHESTRATOR_IDLE, action: 'Planning request…', status: 'active' }
				];
				statusMessage = msg.message ?? 'Request received';
				globalStatus = 'active';
				break;

			case 'agent_active':
				updateItem('orchestrator', { action: 'Routing to specialist agents', status: 'active' });
				addOrUpdate({
					id: msg.agent_id!,
					label: msg.agent_label!,
					icon: msg.agent_icon!,
					department: msg.agent_dept!,
					action: msg.action!,
					status: 'active'
				});
				statusMessage = `Routing to ${msg.agent_label}…`;
				break;

			case 'agent_waiting':
				updateItem(msg.agent_id!, {
					status: 'waiting',
					waitingMessage: msg.waiting_message
				});
				statusMessage = 'Awaiting user input…';
				break;

			case 'agent_done':
				updateItem(msg.agent_id!, { status: 'done', waitingMessage: undefined });
				statusMessage = `${msg.agent_label} responded`;
				break;

			case 'session_done':
				timelineItems = timelineItems.map((i) => ({ ...i, status: 'done' }));
				statusMessage = msg.message ?? 'Completed ✓';
				globalStatus = 'done';
				break;
		}
	}

	// ── WebSocket ────────────────────────────────────────────────────────
	const WS_URL = 'ws://localhost:4001/v1/orchestration/ws';
	let ws: WebSocket | null = null;
	let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
	let destroyed = false;

	function connect() {
		if (destroyed) return;
		ws = new WebSocket(WS_URL);

		ws.onmessage = (e) => {
			try {
				const msg: OrchestrationMessage = JSON.parse(e.data);
				handleMessage(msg);
			} catch {
				// ignore malformed frames
			}
		};

		ws.onclose = () => {
			if (!destroyed) {
				reconnectTimer = setTimeout(connect, 2000);
			}
		};

		ws.onerror = () => {
			// onclose fires after onerror — reconnect handled there
		};
	}

	onMount(connect);

	onDestroy(() => {
		destroyed = true;
		if (reconnectTimer) clearTimeout(reconnectTimer);
		ws?.close();
		ws = null;
	});
</script>

<div class="flex flex-col h-full bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800">
	<!-- Header -->
	<div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800 shrink-0">
		<div class="flex items-center gap-2">
			<span class="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
				Agent Thinking
			</span>
			{#if globalStatus !== 'idle'}
				<span
					class="h-1.5 w-1.5 rounded-full {globalStatus === 'done'
						? 'bg-green-400'
						: 'bg-blue-400 animate-pulse'}"
				></span>
			{/if}
		</div>

		<div class="flex items-center gap-1">
			<!-- Timeline view toggle -->
			<button
				class="p-1 rounded transition-colors text-gray-500 dark:text-gray-400
					{viewMode === 'timeline'
					? 'bg-gray-200 dark:bg-gray-700'
					: 'hover:bg-gray-100 dark:hover:bg-gray-800'}"
				title="Timeline view"
				on:click={() => (viewMode = 'timeline')}
			>
				<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
					<path fill-rule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd" />
				</svg>
			</button>

			<!-- Flow view toggle -->
			<button
				class="p-1 rounded transition-colors text-gray-500 dark:text-gray-400
					{viewMode === 'flow'
					? 'bg-gray-200 dark:bg-gray-700'
					: 'hover:bg-gray-100 dark:hover:bg-gray-800'}"
				title="Flow view"
				on:click={() => (viewMode = 'flow')}
			>
				<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
					<path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v1h8v-1zM6 8a2 2 0 11-4 0 2 2 0 014 0zM16 18v-1a5.972 5.972 0 00-.75-2.906A3.005 3.005 0 0119 15v1h-3zM4.75 14.094A5.973 5.973 0 004 17v1H1v-1a3 3 0 013.75-2.906z" />
				</svg>
			</button>

			<!-- Collapse -->
			<button
				class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
				title="Collapse thinking sidebar"
				on:click={() => showOrchestrationSidebar.set(false)}
			>
				<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
					<path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
				</svg>
			</button>
		</div>
	</div>

	<!-- Body: timeline or flow -->
	{#if viewMode === 'timeline'}
		<div class="flex-1 overflow-y-auto p-5 min-h-0">
			{#each timelineItems as item, i (item.id)}
				<div
					class="grid grid-cols-[40px_1fr] gap-x-3"
					class:opacity-50={item.status === 'idle' && i > 0}
				>
					<!-- Left col: status circle + connector -->
					<div class="flex flex-col items-center">
						{#if item.status === 'done'}
							<div class="flex items-center justify-center w-10 h-10 rounded-full bg-green-500 text-white shadow-md z-10 shrink-0">
								<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
									<path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
								</svg>
							</div>
						{:else if item.status === 'waiting'}
							<div class="flex items-center justify-center w-10 h-10 rounded-full bg-amber-500 text-white shadow-[0_0_12px_rgba(245,158,11,0.4)] z-10 shrink-0">
								<span class="text-base leading-none">⏳</span>
							</div>
						{:else if item.status === 'active'}
							<div class="relative flex items-center justify-center w-10 h-10 rounded-full bg-blue-500 text-white z-10 shrink-0 shadow-[0_0_15px_rgba(59,130,246,0.4)]">
								<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-20"></span>
								<span class="text-lg leading-none relative">{item.icon}</span>
							</div>
						{:else}
							<div class="flex items-center justify-center w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-500 z-10 shrink-0">
								<span class="text-lg leading-none">{item.icon}</span>
							</div>
						{/if}

						<!-- Connector to next item -->
						{#if i < timelineItems.length - 1}
							{#if timelineItems[i + 1].status === 'idle'}
								<div class="border-l-2 border-dashed border-gray-200 dark:border-gray-700 flex-1 mt-1 ml-px"></div>
							{:else}
								<div class="w-0.5 bg-gray-200 dark:bg-gray-700 flex-1 mt-1"></div>
							{/if}
						{/if}
					</div>

					<!-- Right col: name + badge + action chip / waiting card -->
					<div class="pb-6 pt-1">
						<div class="flex items-start justify-between gap-2 mb-2">
							<div class="min-w-0">
								<p class="text-gray-900 dark:text-white text-sm font-semibold leading-normal truncate">
									{item.label}
								</p>
								{#if item.department}
									<p class="text-gray-500 dark:text-gray-400 text-xs mt-0.5">{item.department}</p>
								{/if}
							</div>

							{#if item.status === 'done'}
								<span class="inline-flex items-center shrink-0 px-2 py-0.5 rounded text-xs font-medium bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20">
									Done
								</span>
							{:else if item.status === 'waiting'}
								<span class="inline-flex items-center gap-1.5 shrink-0 px-2 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
									<span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>
									Waiting
								</span>
							{:else if item.status === 'active'}
								<span class="inline-flex items-center gap-1.5 shrink-0 px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
									<span class="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
									Active
								</span>
							{:else if i > 0}
								<span class="inline-flex items-center shrink-0 px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-700">
									Pending
								</span>
							{/if}
						</div>

						<!-- Action chip -->
						<div class="inline-flex items-center px-2.5 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-300 leading-relaxed">
							{item.action}
						</div>

						<!-- Waiting card (human-in-the-loop) -->
						{#if item.status === 'waiting' && item.waitingMessage}
							<div class="mt-3 rounded-xl overflow-hidden border border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-950/20">
								<div class="p-3 flex items-start gap-2.5">
									<div class="p-1 rounded-md bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5">
										<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
											<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd" />
										</svg>
									</div>
									<p class="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">{item.waitingMessage}</p>
								</div>
								<div class="h-1 bg-amber-100 dark:bg-amber-900/30">
									<div class="h-full w-2/3 bg-amber-500 rounded-r-full animate-pulse"></div>
								</div>
							</div>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="flex-1 min-h-0">
			<FlowView {timelineItems} />
		</div>
	{/if}

	<!-- Status bar -->
	<div class="px-4 py-2.5 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950 flex items-center gap-2 shrink-0">
		{#if globalStatus === 'active'}
			<span class="relative flex h-2 w-2 shrink-0">
				<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
				<span class="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
			</span>
		{:else if globalStatus === 'done'}
			<span class="h-2 w-2 rounded-full bg-green-400 shrink-0"></span>
		{:else}
			<span class="h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600 shrink-0"></span>
		{/if}
		<span class="text-xs text-gray-500 dark:text-gray-400 truncate">{statusMessage}</span>
	</div>
</div>
