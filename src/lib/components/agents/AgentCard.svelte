<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { AgentInfo } from '$lib/apis/agents';

	export let agent: AgentInfo;
	export let online: boolean = false;

	const dispatch = createEventDispatcher<{ edit: string }>();
</script>

<div
	class="group relative flex flex-col gap-3 rounded-2xl border border-gray-200 dark:border-gray-700
		   bg-white dark:bg-gray-900 p-5 shadow-sm transition-all duration-200
		   hover:shadow-md hover:-translate-y-0.5 hover:border-blue-300 dark:hover:border-blue-600
		   cursor-pointer"
	role="button"
	tabindex="0"
	on:click={() => dispatch('edit', agent.id)}
	on:keydown={(e) => e.key === 'Enter' && dispatch('edit', agent.id)}
>
	<!-- Status indicator (hides on hover to show edit icon) -->
	<span
		class="absolute top-4 right-4 h-2.5 w-2.5 rounded-full transition-opacity group-hover:opacity-0
			{online
			? 'bg-green-400 shadow-[0_0_6px_1px_rgba(74,222,128,0.6)]'
			: 'bg-gray-300 dark:bg-gray-600'}"
		title={online ? 'Online' : 'Offline'}
	/>

	<!-- Edit pencil icon (shows on hover) -->
	<span
		class="absolute top-3.5 right-3.5 opacity-0 group-hover:opacity-100 transition-opacity
			   text-gray-400 dark:text-gray-500"
		title="Edit agent"
	>
		<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
			<path
				d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
			/>
		</svg>
	</span>

	<!-- Icon + title row -->
	<div class="flex items-center gap-3">
		<div
			class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl
				   bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-blue-900/40 dark:to-indigo-900/40
				   text-2xl shadow-inner"
		>
			{agent.icon}
		</div>
		<div class="min-w-0">
			<h3 class="truncate text-sm font-semibold text-gray-900 dark:text-white">
				{agent.name}
			</h3>
			<div class="flex items-center gap-1 mt-0.5">
				<span
					class="inline-block rounded-full bg-blue-100 dark:bg-blue-900/50 px-2 py-0.5
						   text-[10px] font-medium text-blue-700 dark:text-blue-300 uppercase tracking-wide"
				>
					{agent.department}
				</span>
				{#if agent.is_external}
					<span
						class="inline-block rounded-full bg-amber-100 dark:bg-amber-900/50 px-2 py-0.5
							   text-[10px] font-medium text-amber-700 dark:text-amber-300 uppercase tracking-wide"
					>
						External
					</span>
				{/if}
			</div>
		</div>
	</div>

	<!-- Purpose -->
	<p class="text-xs leading-relaxed text-gray-500 dark:text-gray-400 line-clamp-3">
		{agent.purpose}
	</p>

	<!-- Footer -->
	<div
		class="mt-auto flex items-center justify-between pt-2 border-t border-gray-100 dark:border-gray-800"
	>
		<span class="text-[10px] font-mono text-gray-400 dark:text-gray-600 uppercase tracking-widest">
			{agent.id}
		</span>
		<span class="text-[10px] text-gray-400 dark:text-gray-600">
			{online ? 'Ready' : 'Offline'}
		</span>
	</div>
</div>
