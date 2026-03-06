<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { user, showSidebar, WEBUI_NAME } from '$lib/stores';
	import { getAllModelsAdmin, getBaseModels, updateModelById, deleteModelById } from '$lib/apis/models';
	import { getModels } from '$lib/apis';
	import { getOrchestratorConfig, setOrchestratorConfig } from '$lib/apis/configs';
	import Modal from '$lib/components/common/Modal.svelte';
	import OrchestratorPromptEditor from '$lib/components/admin/Agents/OrchestratorPromptEditor.svelte';
	import EditAgentModal from '$lib/components/admin/Agents/EditAgentModal.svelte';

	const i18n = getContext('i18n');

	let agents = [];
	let baseModels = [];
	let orchestratorConfig = { enabled: false, routing_model: '', system_prompt: '', show_model_selector: false };
	let loading = true;
	let showOrchestratorModal = false;
	let selectedAgent = null;
	let showEditModal = false;

	onMount(async () => {
		if ($user?.role !== 'admin') {
			goto('/');
			return;
		}
		await loadData();
	});

	async function loadData() {
		loading = true;
		try {
			const [workspaceRes, liveRes, baseModelsRes, configRes] = await Promise.all([
				getAllModelsAdmin($user?.token),
				getModels($user?.token),
				getBaseModels($user?.token),
				getOrchestratorConfig($user?.token)
			]);

			// Workspace models (DB records) — already have meta, is_active, etc.
			const workspaceModels = (workspaceRes ?? []).filter((m) => m.id !== 'orchestrator');
			const workspaceIds = new Set(workspaceModels.map((m) => m.id));

			// External connection models not already represented as workspace models
			const externalModels = (liveRes?.data ?? liveRes ?? [])
				.filter(
					(m) =>
						m.connection_type === 'external' &&
						m.id !== 'orchestrator' &&
						!workspaceIds.has(m.id)
				)
				.map((m) => ({
					...m,
					is_active: true, // live by definition (server responded)
					meta: {
						profile_image_url: null,
						description: null,
						tags: (m.tags ?? []).map((t) => (typeof t === 'string' ? { name: t } : t))
					}
				}));

			agents = [...workspaceModels, ...externalModels];
			baseModels = baseModelsRes ?? [];
			if (configRes) orchestratorConfig = configRes;
		} catch (e) {
			toast.error($i18n.t('Failed to load agents'));
		} finally {
			loading = false;
		}
	}

	async function handleSaveConfig(event) {
		try {
			const saved = await setOrchestratorConfig($user?.token, event.detail);
			if (saved) {
				orchestratorConfig = saved;
				toast.success($i18n.t('Orchestrator config saved'));
				showOrchestratorModal = false;
			}
		} catch (e) {
			toast.error($i18n.t('Failed to save config'));
		}
	}

	async function handleSaveAgent(event) {
		const model = event.detail;
		try {
			await updateModelById($user?.token, model.id, model);
			toast.success($i18n.t('Agent saved'));
			showEditModal = false;
			await loadData();
		} catch (e) {
			toast.error($i18n.t('Failed to save agent'));
		}
	}

	async function handleDeleteAgent(event) {
		try {
			await deleteModelById($user?.token, event.detail.id);
			toast.success($i18n.t('Agent deleted'));
			showEditModal = false;
			await loadData();
		} catch (e) {
			toast.error($i18n.t('Failed to delete agent'));
		}
	}

	function handleEditAgent(agent) {
		// Only workspace models (with a DB record) can be edited via the modal
		if (agent.connection_type === 'external' && !agent.info) return;
		selectedAgent = agent;
		showEditModal = true;
	}

	$: systemOnline = agents.some((a) => a.is_active);
	$: onlineCount = agents.filter((a) => a.is_active).length;

	const TAG_BADGE_CLASS = 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300';
</script>

<svelte:head>
	<title>Agents • {$WEBUI_NAME}</title>
</svelte:head>

<EditAgentModal
	bind:show={showEditModal}
	model={selectedAgent}
	on:save={handleSaveAgent}
	on:delete={handleDeleteAgent}
/>

<!-- Orchestrator System Prompt Modal -->
<Modal bind:show={showOrchestratorModal} size="md">
	<div>
		<div class="flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
			<div class="text-lg font-medium self-center">{$i18n.t('Orchestrator Configuration')}</div>
			<button
				class="self-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition"
				aria-label={$i18n.t('Close')}
				on:click={() => (showOrchestratorModal = false)}
			>
				<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-5">
					<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
				</svg>
			</button>
		</div>
		<div class="px-5 pb-5">
			<OrchestratorPromptEditor
				config={orchestratorConfig}
				models={baseModels}
				on:save={handleSaveConfig}
				hideTitleAndBorder={true}
			/>
		</div>
	</div>
</Modal>

<div
	class="flex flex-col w-full h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''} max-w-full"
>
<div class="pb-1 px-3 md:px-[18px] flex-1 overflow-y-auto py-4">
	<!-- Header -->
	<div class="flex items-start justify-between mb-4">
		<div>
			<div class="flex items-center gap-3 mb-1">
				<h1 class="text-xl font-medium text-gray-900 dark:text-white">{$i18n.t('Agent Directory')}</h1>
				{#if !loading}
					<span
						class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium {systemOnline
							? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
							: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'}"
					>
						<span class="w-1.5 h-1.5 rounded-full {systemOnline ? 'bg-green-500' : 'bg-gray-400'}"></span>
						{systemOnline ? $i18n.t('System Online') : $i18n.t('System Offline')}
					</span>
				{/if}
			</div>
			<p class="text-sm text-gray-500 dark:text-gray-400">
				{$i18n.t('Manage and monitor all specialist agents available in the orchestration network.')}
			</p>
		</div>
		<button
			class="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800 transition text-gray-700 dark:text-gray-300"
			on:click={() => (showOrchestratorModal = true)}
		>
			<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
				<path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
			</svg>
			{$i18n.t('Edit System Prompt')}
		</button>
	</div>

	<!-- Agent Grid -->
	{#if loading}
		<div class="flex-1 flex items-center justify-center">
			<div class="text-sm text-gray-400 dark:text-gray-500">{$i18n.t('Loading agents...')}</div>
		</div>
	{:else if agents.length === 0}
		<div class="flex-1 flex items-center justify-center">
			<div class="text-center">
				<div class="text-sm text-gray-400 dark:text-gray-500 mb-1">{$i18n.t('No agents found')}</div>
				<div class="text-xs text-gray-300 dark:text-gray-600">{$i18n.t('Create custom models in Workspace → Models to register agents.')}</div>
			</div>
		</div>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-4">
			{#each agents as agent (agent.id)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<div
					class="flex flex-col gap-3 p-4 rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 shadow-sm dark:shadow-gray-950/50 hover:shadow-md transition relative h-[10rem] {agent.connection_type === 'external' && !agent.info ? 'cursor-default' : 'cursor-pointer'}"
					on:click={() => handleEditAgent(agent)}
				>
					<!-- Online dot -->
					<span
						class="absolute top-4 right-4 w-2.5 h-2.5 rounded-full {agent.is_active
							? 'bg-green-500'
							: 'bg-gray-300 dark:bg-gray-600'}"
					></span>

					<!-- Avatar + Name -->
					<div class="flex items-center gap-3 pr-5">
						<img
							src={agent.meta?.profile_image_url || '/static/favicon.png'}
							alt={agent.name}
							class="w-10 h-10 rounded-full object-cover shrink-0"
						/>
						<div class="flex flex-col min-w-0">
							<span class="font-semibold text-sm text-gray-900 dark:text-white line-clamp-1">
								{agent.name}
							</span>
							<div class="flex min-w-0 gap-1">
								{#each (agent.meta?.tags ?? []) as tag, i}
									{#if i < 2}
										<span class="inline-block text-[10px] font-medium uppercase px-2 py-0.5 mt-1 rounded-full {TAG_BADGE_CLASS}">
											{tag.name}
										</span>
									{:else if i === 2}
										<span class="inline-block text-[10px] font-medium px-2 py-0.5 mt-1 rounded-full bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">
											+{(agent.meta?.tags ?? []).length - 2}
										</span>
									{/if}
								{/each}
							</div>
						</div>
					</div>

					<!-- Description -->
					<p class="flex-1 text-xs text-gray-500 dark:text-gray-400 line-clamp-3 leading-relaxed overflow-hidden">
						{agent.meta?.description ?? ''}
					</p>

				</div>
			{/each}
		</div>
	{/if}

	<!-- Status Bar — always shown after loading -->
	{#if !loading}
		<div class="flex items-center justify-between py-3 px-4 rounded-xl bg-gray-50 dark:bg-gray-900/50 border border-gray-100 dark:border-gray-850 text-xs text-gray-500 dark:text-gray-400">
			<div class="flex items-center gap-4">
				<span class="flex items-center gap-1.5">
					<span class="w-2 h-2 rounded-full bg-green-500"></span>
					{$i18n.t('Online')}
				</span>
				<span class="flex items-center gap-1.5">
					<span class="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600"></span>
					{$i18n.t('Offline')}
				</span>
			</div>
			<span>{agents.length} {$i18n.t('agents registered')}</span>
		</div>
	{/if}
</div>
</div>
