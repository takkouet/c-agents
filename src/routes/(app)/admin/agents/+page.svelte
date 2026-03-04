<script lang="ts">
	import { getContext } from 'svelte';
	import { user } from '$lib/stores';

	const i18n = getContext('i18n');
</script>

<div class="w-full h-full flex flex-col gap-1 px-5 py-4">
	<div class="flex items-center gap-2 mb-4">
		<div class="text-lg font-semibold">{$i18n.t('Agents')}</div>
	</div>
	<div class="text-sm text-gray-500 dark:text-gray-400">
		{$i18n.t('Loading agents...')}
	</div>
</div>
