<script lang="ts">
	import { onMount } from 'svelte';
	import {
		getAgents,
		getAgentHealth,
		getAgentHealthById,
		getAgent,
		type AgentInfo,
		type AgentConfig
	} from '$lib/apis/agents';
	import AgentCard from '$lib/components/agents/AgentCard.svelte';
	import AddAgentModal from '$lib/components/agents/AddAgentModal.svelte';

	let agents: AgentInfo[] = [];
	let online = false;
	let agentHealth: Record<string, boolean> = {};
	let loading = true;

	let showModal = false;
	let editingAgent: AgentConfig | undefined = undefined;

	async function checkAgentHealth(agent: AgentInfo): Promise<boolean> {
		return getAgentHealthById(agent);
	}

	async function refresh() {
		const [systemHealth, agentList] = await Promise.all([getAgentHealth(), getAgents()]);
		online = systemHealth;
		agents = agentList;

		// Check per-agent health in parallel
		const healthResults = await Promise.all(
			agentList.map(async (a) => ({
				id: a.id,
				healthy: await checkAgentHealth(a)
			}))
		);
		agentHealth = {};
		for (const result of healthResults) {
			agentHealth[result.id] = result.healthy;
		}
	}

	onMount(async () => {
		await refresh();
		loading = false;
	});

	function openCreate() {
		editingAgent = undefined;
		showModal = true;
	}

	async function openEdit(id: string) {
		const config = await getAgent(id);
		if (config) {
			editingAgent = config;
			showModal = true;
		}
	}

	async function onSaved() {
		await refresh();
	}

	async function onDeleted() {
		await refresh();
	}
</script>

<svelte:head>
	<title>Agents — C-Agents</title>
</svelte:head>

<AddAgentModal
	bind:show={showModal}
	agent={editingAgent}
	on:saved={onSaved}
	on:deleted={onDeleted}
/>

<div class="flex flex-col h-full px-6 py-8 max-w-6xl mx-auto w-full">
	<!-- Header -->
	<div class="mb-8">
		<div class="flex items-center gap-3 mb-2">
			<h1 class="text-2xl font-bold text-gray-900 dark:text-white">Agent Directory</h1>
			<span
				class="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium
					   {online
					? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
					: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}"
			>
				<span class="h-1.5 w-1.5 rounded-full {online ? 'bg-green-500' : 'bg-gray-400'}" />
				{online ? 'System Online' : 'System Offline'}
			</span>

			<button
				class="ml-auto flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-full
					bg-black hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-200
					text-white dark:text-black transition-colors"
				on:click={openCreate}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="h-3.5 w-3.5"
					viewBox="0 0 20 20"
					fill="currentColor"
				>
					<path
						fill-rule="evenodd"
						d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
						clip-rule="evenodd"
					/>
				</svg>
				Add Agent
			</button>
		</div>
		<p class="text-sm text-gray-500 dark:text-gray-400">
			Manage and monitor all specialist agents available in the orchestration network.
		</p>
	</div>

	<!-- Agent grid -->
	{#if loading}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
			{#each Array(4) as _}
				<div class="h-44 rounded-2xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
			{/each}
		</div>
	{:else if agents.length === 0}
		<div class="flex flex-col items-center justify-center flex-1 text-center gap-3 py-20">
			<div class="text-5xl">🤖</div>
			<p class="text-gray-500 dark:text-gray-400 text-sm">
				No agents found. Make sure the agent server is running on port 4001.
			</p>
			<button
				class="mt-2 px-4 py-2 text-sm font-medium rounded-full bg-black hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-200 text-white dark:text-black transition-colors"
				on:click={openCreate}
			>
				Add your first agent
			</button>
		</div>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
			{#each agents as agent (agent.id)}
				<AgentCard
					{agent}
					online={agentHealth[agent.id] ?? false}
					on:edit={() => openEdit(agent.id)}
				/>
			{/each}
		</div>

		<!-- Legend / info bar -->
		<div
			class="mt-8 flex items-center gap-6 rounded-xl border border-gray-200 dark:border-gray-700
				   bg-gray-50 dark:bg-gray-900 px-5 py-3 text-xs text-gray-500 dark:text-gray-400"
		>
			<span class="flex items-center gap-1.5">
				<span class="h-2 w-2 rounded-full bg-green-400" /> Online
			</span>
			<span class="flex items-center gap-1.5">
				<span class="h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600" /> Offline
			</span>
			<span class="flex items-center gap-1.5">
				<span
					class="rounded-full bg-amber-100 dark:bg-amber-900/50 px-1.5 py-px text-[9px] font-medium text-amber-700 dark:text-amber-300"
					>E</span
				> External
			</span>
			<span class="ml-auto">
				{agents.length} agent{agents.length !== 1 ? 's' : ''} registered
			</span>
		</div>
	{/if}
</div>
