<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import Badge from '$lib/components/common/Badge.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let model;
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
	class="flex flex-col gap-3 p-4 rounded-2xl bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-850 hover:shadow-md transition cursor-pointer"
	on:click={() => dispatch('edit', model)}
>
	<div class="flex items-center gap-3">
		<img
			src={model.meta?.profile_image_url || '/static/favicon.png'}
			alt={model.name}
			class="w-10 h-10 rounded-full object-cover shrink-0"
		/>
		<div class="flex flex-col min-w-0">
			<div class="flex items-center gap-2">
				<span
					class="w-2 h-2 rounded-full inline-block shrink-0 {model.is_active
						? 'bg-green-500'
						: 'bg-gray-400'}"
				/>
				<span class="font-medium text-sm line-clamp-1 text-gray-900 dark:text-white">
					{model.name}
				</span>
			</div>
		</div>
	</div>

	{#if model.meta?.description}
		<div class="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
			{model.meta.description}
		</div>
	{/if}

	{#if model.meta?.tags?.length}
		<div class="flex flex-wrap gap-1">
			{#each model.meta.tags as tag}
				<Badge type="muted" content={tag.name} />
			{/each}
		</div>
	{/if}
</div>
