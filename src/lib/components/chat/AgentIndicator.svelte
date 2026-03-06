<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let selectedModelId = '';
	export let models = [];

	$: agent = models.find((m) => m.id === selectedModelId);
</script>

<div
	class="flex items-center gap-2 px-2 py-1 rounded-xl text-sm font-medium text-gray-700 dark:text-gray-300"
>
	<img
		src={agent?.meta?.profile_image_url || '/static/favicon.png'}
		class="w-6 h-6 rounded-full"
		alt={agent?.name || $i18n.t('AI Assistant')}
	/>
	<span>{agent?.name || $i18n.t('AI Assistant')}</span>
</div>
