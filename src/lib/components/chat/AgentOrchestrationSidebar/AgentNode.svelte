<script lang="ts">
	import { Handle, Position } from '@xyflow/svelte';
	import type { TimelineItem } from '$lib/stores/orchestration';

	export let data: TimelineItem;
</script>

{#if data.id !== 'orchestrator'}
	<Handle type="target" position={Position.Top} style="opacity:0; pointer-events:none;" />
{/if}

<div
	class="flex flex-col items-center gap-1 px-3 py-2.5 rounded-xl border text-center w-[110px] select-none
		{data.status === 'done'
		? 'bg-green-500/10 border-green-500/30'
		: data.status === 'active'
			? 'bg-blue-500/10 border-blue-500/30'
			: data.status === 'waiting'
				? 'bg-amber-500/10 border-amber-500/30'
				: 'bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700'}"
>
	{#if data.status === 'done'}
		<div
			class="flex items-center justify-center w-9 h-9 rounded-full bg-green-500 text-white text-sm font-bold shrink-0"
		>
			<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
				<path
					fill-rule="evenodd"
					d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
					clip-rule="evenodd"
				/>
			</svg>
		</div>
	{:else if data.status === 'waiting'}
		<div
			class="flex items-center justify-center w-9 h-9 rounded-full bg-amber-500 text-white shrink-0"
		>
			<span class="text-base leading-none">⏳</span>
		</div>
	{:else if data.status === 'active'}
		<div class="relative flex items-center justify-center w-9 h-9 rounded-full bg-blue-500 text-white shrink-0">
			<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-20"></span>
			<span class="text-base leading-none relative">{data.icon}</span>
		</div>
	{:else}
		<div
			class="flex items-center justify-center w-9 h-9 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-500 shrink-0"
		>
			<span class="text-base leading-none">{data.icon}</span>
		</div>
	{/if}

	<p class="text-[10px] font-semibold text-gray-800 dark:text-gray-200 leading-tight break-words w-full">
		{data.label}
	</p>
	{#if data.department}
		<p class="text-[9px] text-gray-500 dark:text-gray-400 leading-tight">{data.department}</p>
	{/if}
</div>

<Handle type="source" position={Position.Bottom} style="opacity:0; pointer-events:none;" />
