<script lang="ts">
	import { getContext } from 'svelte';
	import AgentCard from './Agents/AgentCard.svelte';

	const i18n = getContext('i18n');

	export let models = [];

	let search = '';

	$: filteredModels = models.filter((model) => {
		const q = search.toLowerCase();
		return (
			model.name?.toLowerCase().includes(q) || model.meta?.description?.toLowerCase().includes(q)
		);
	});
</script>

<div class="flex flex-col gap-4">
	<div class="w-full">
		<input
			type="text"
			bind:value={search}
			placeholder={$i18n.t('Search agents...')}
			class="w-full rounded-xl border border-gray-200 dark:border-gray-800 bg-transparent px-4 py-2.5 text-sm outline-none focus:border-gray-300 dark:focus:border-gray-700 transition"
		/>
	</div>

	{#if filteredModels.length > 0}
		<div class="grid lg:grid-cols-2 xl:grid-cols-3 gap-4">
			{#each filteredModels as model (model.id)}
				<AgentCard {model} on:edit />
			{/each}
		</div>
	{:else}
		<div class="text-center text-sm text-gray-500 dark:text-gray-400 py-8">
			{$i18n.t('No agents found')}
		</div>
	{/if}
</div>
