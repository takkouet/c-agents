<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';

	import Switch from '$lib/components/common/Switch.svelte';
	import Selector from '$lib/components/common/Selector.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let config = { enabled: false, routing_model: '', system_prompt: '' };
	export let models: Array<{ id: string; name: string }> = [];

	let localConfig = { ...config };
	$: if (config) localConfig = { ...config };

	function handleSave() {
		dispatch('save', { ...localConfig });
	}

	function handleReset() {
		localConfig = { ...config };
	}
</script>

<div class="p-4 rounded-2xl bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-850">
	<div class="flex items-center justify-between mb-4">
		<h3 class="text-lg font-semibold">{$i18n.t('Orchestrator Configuration')}</h3>
		<Switch bind:state={localConfig.enabled} />
	</div>

	{#if localConfig.enabled}
		<div class="space-y-4">
			<div>
				<label class="block text-sm font-medium mb-1.5">{$i18n.t('Routing Model')}</label>
				<Selector
					bind:value={localConfig.routing_model}
					placeholder={$i18n.t('Select a model')}
					items={models.map((m) => ({ value: m.id, label: m.name }))}
				/>
			</div>

			<div>
				<label class="block text-sm font-medium mb-1.5" for="orchestrator-system-prompt">
					{$i18n.t('System Prompt')}
				</label>
				<textarea
					id="orchestrator-system-prompt"
					bind:value={localConfig.system_prompt}
					rows="6"
					class="w-full rounded-xl border border-gray-200 dark:border-gray-800 bg-transparent px-4 py-2.5 text-sm outline-none focus:border-gray-300 dark:focus:border-gray-700 resize-y transition"
					placeholder={$i18n.t('Enter orchestrator system prompt...')}
				/>
			</div>

			<div class="flex justify-end gap-2 pt-1">
				<button
					type="button"
					class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={handleReset}
				>
					{$i18n.t('Reset')}
				</button>
				<button
					type="button"
					class="px-4 py-2 rounded-xl bg-gray-900 dark:bg-white text-white dark:text-gray-900 text-sm font-medium hover:opacity-80 transition"
					on:click={handleSave}
				>
					{$i18n.t('Save')}
				</button>
			</div>
		</div>
	{/if}
</div>
