<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';
	import { getOrchestratorConfig, setOrchestratorConfig } from '$lib/apis/configs';
	import { getModelItems, updateModelById, deleteModelById } from '$lib/apis/models';
	import Agents from '$lib/components/admin/Agents.svelte';
	import OrchestratorPromptEditor from '$lib/components/admin/Agents/OrchestratorPromptEditor.svelte';
	import EditAgentModal from '$lib/components/admin/Agents/EditAgentModal.svelte';

	const i18n = getContext('i18n');

	let models = [];
	let orchestratorConfig = { enabled: false, routing_model: '', system_prompt: '' };
	let selectedModel = null;
	let showEditModal = false;
	let loading = true;

	onMount(async () => {
		await loadData();
	});

	async function loadData() {
		loading = true;
		try {
			const [modelsRes, configRes] = await Promise.all([
				getModelItems($user?.token, '', null, null, null, null, null),
				getOrchestratorConfig($user?.token)
			]);
			// Filter out orchestrator virtual model from agent cards
			models = (modelsRes?.items ?? []).filter((m) => m.id !== 'orchestrator');
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

	function handleEditAgent(event) {
		selectedModel = event.detail;
		showEditModal = true;
	}
</script>

<EditAgentModal
	bind:show={showEditModal}
	model={selectedModel}
	on:save={handleSaveAgent}
	on:delete={handleDeleteAgent}
/>

<div class="w-full h-full flex flex-col gap-4 px-5 py-4">
	<OrchestratorPromptEditor config={orchestratorConfig} {models} on:save={handleSaveConfig} />

	{#if loading}
		<div class="text-sm text-gray-500 dark:text-gray-400">{$i18n.t('Loading agents...')}</div>
	{:else}
		<Agents {models} on:edit={handleEditAgent} />
	{/if}
</div>
