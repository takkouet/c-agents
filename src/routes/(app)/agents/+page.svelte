<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';
	import { user, showSidebar, WEBUI_NAME } from '$lib/stores';
	import { getAllModelsAdmin, getBaseModels, updateModelById, deleteModelById } from '$lib/apis/models';
	import { getModels } from '$lib/apis';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import EditAgentModal from '$lib/components/admin/Agents/EditAgentModal.svelte';

	const i18n = getContext('i18n');

	let agents = [];
	let baseModels = [];
	let loading = true;
	let selectedAgent = null;
	let showEditModal = false;

	// Multi-select state
	let selectMode = false;
	let selectedIds = new Set<string>();
	let showDeleteConfirm = false;

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
			const [workspaceRes, liveRes, baseModelsRes] = await Promise.all([
				getAllModelsAdmin($user?.token),
				getModels($user?.token),
				getBaseModels($user?.token)
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
		} catch (e) {
			toast.error($i18n.t('Failed to load agents'));
		} finally {
			loading = false;
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

	function handleCardClick(agent) {
		if (selectMode) return;
		sessionStorage.selectedModels = JSON.stringify([agent.id]);
		goto('/');
	}

	function toggleSelect(agentId) {
		if (selectedIds.has(agentId)) {
			selectedIds.delete(agentId);
		} else {
			selectedIds.add(agentId);
		}
		selectedIds = selectedIds; // trigger reactivity
	}

	function toggleSelectAll() {
		if (selectedIds.size === agents.length) {
			selectedIds = new Set();
		} else {
			selectedIds = new Set(agents.map((a) => a.id));
		}
	}

	function exitSelectMode() {
		selectMode = false;
		selectedIds = new Set();
	}

	async function handleBulkDelete() {
		const ids = [...selectedIds];
		try {
			await Promise.all(ids.map((id) => deleteModelById($user?.token, id)));
			toast.success($i18n.t(`Deleted ${ids.length} agent(s)`));
			exitSelectMode();
			await loadData();
		} catch (e) {
			toast.error($i18n.t('Failed to delete some agents'));
			await loadData();
		}
	}

	function isWorkspaceModel(agent) {
		return !(agent.connection_type === 'external' && !agent.info);
	}

	$: systemOnline = agents.some((a) => a.is_active);
	$: onlineCount = agents.filter((a) => a.is_active).length;

	const TAG_BADGE_CLASS = 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300';
</script>

<svelte:head>
	<title>Agents &bull; {$WEBUI_NAME}</title>
</svelte:head>

<ConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete Agents')}
	message={$i18n.t(`Are you sure you want to delete ${selectedIds.size} agent(s)? This action cannot be undone.`)}
	onConfirm={handleBulkDelete}
/>

<EditAgentModal
	bind:show={showEditModal}
	model={selectedAgent}
	on:save={handleSaveAgent}
	on:delete={handleDeleteAgent}
/>

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
		{#if !loading && agents.length > 0}
			<div class="flex items-center gap-2">
				{#if selectMode && selectedIds.size > 0}
					<button
						class="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-gray-900 hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-100 text-white dark:text-gray-900 text-sm font-medium transition"
						on:click={() => (showDeleteConfirm = true)}
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
							<path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
						</svg>
						{$i18n.t('Delete')}
					</button>
				{/if}
				{#if selectMode}
					<button
						class="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm font-medium transition text-gray-700 dark:text-gray-300"
						on:click={exitSelectMode}
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
						</svg>
						{$i18n.t('Deselect All')}
					</button>
				{:else}
					<button
						class="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm font-medium transition text-gray-700 dark:text-gray-300"
						on:click={() => (selectMode = true)}
					>
						<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-4">
							<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
						</svg>
						{$i18n.t('Select')}
					</button>
				{/if}
			</div>
		{/if}
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
					class="flex flex-col gap-3 p-4 rounded-2xl bg-white dark:bg-gray-800 border shadow-sm dark:shadow-gray-950/50 hover:shadow-md transition relative h-[10rem] cursor-pointer {selectedIds.has(agent.id)
						? 'border-blue-400 dark:border-blue-500 ring-2 ring-blue-200 dark:ring-blue-800'
						: 'border-gray-200 dark:border-gray-600'}"
					on:click={() => {
						if (selectMode) {
							toggleSelect(agent.id);
						} else {
							handleCardClick(agent);
						}
					}}
				>
					<!-- Select checkbox (top-left, only in select mode) -->
					{#if selectMode}
						<div class="absolute top-3 left-3 z-10">
							<div
								class="w-5 h-5 rounded-md border-2 flex items-center justify-center transition {selectedIds.has(agent.id)
									? 'bg-blue-500 border-blue-500 text-white'
									: 'border-gray-300 dark:border-gray-500 bg-white dark:bg-gray-700'}"
							>
								{#if selectedIds.has(agent.id)}
									<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor" class="w-3 h-3">
										<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
									</svg>
								{/if}
							</div>
						</div>
					{/if}

					<!-- Online dot -->
					<span
						class="absolute top-4 right-4 w-2.5 h-2.5 rounded-full {agent.is_active
							? 'bg-green-500'
							: 'bg-gray-300 dark:bg-gray-600'}"
					></span>

					<!-- Avatar + Name -->
					<div class="flex items-center gap-3 pr-5 {selectMode ? 'pl-6' : ''}">
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

					<!-- Gear icon (bottom-right, only for workspace models, hidden in select mode) -->
					{#if !selectMode && isWorkspaceModel(agent)}
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<button
							class="absolute bottom-3 right-3 p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
							title={$i18n.t('Edit Agent')}
							on:click|stopPropagation={() => handleEditAgent(agent)}
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-4 h-4">
								<path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
								<path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
							</svg>
						</button>
					{/if}

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
