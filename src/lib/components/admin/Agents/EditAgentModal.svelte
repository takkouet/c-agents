<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';

	import Modal from '$lib/components/common/Modal.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let show = false;
	export let model: any = null;

	let localModel: any = null;
	let confirmDelete = false;

	$: if (show && model) {
		localModel = JSON.parse(JSON.stringify(model));
		confirmDelete = false;
	}

	$: tagsString = localModel?.meta?.tags?.map((t: { name: string }) => t.name).join(', ') ?? '';

	const handleTagsInput = (e: Event) => {
		const value = (e.target as HTMLInputElement).value;
		if (localModel?.meta) {
			localModel.meta.tags = value
				.split(',')
				.map((s: string) => s.trim())
				.filter((s: string) => s.length > 0)
				.map((name: string) => ({ name }));
		}
	};
</script>

<Modal size="sm" bind:show>
	{#if localModel}
		<div>
			<div class="flex justify-between dark:text-gray-300 px-5 pt-4 pb-2">
				<div class="text-lg font-medium self-center">{$i18n.t('Edit Agent')}</div>
				<button
					class="self-center"
					aria-label={$i18n.t('Close')}
					on:click={() => {
						show = false;
					}}
				>
					<XMark className={'size-5'} />
				</button>
			</div>

			<form
				class="flex flex-col w-full"
				on:submit|preventDefault={() => {
					dispatch('save', localModel);
					show = false;
				}}
			>
				<div class="px-5 pt-3 pb-5 w-full flex flex-col gap-4">
					<div class="flex flex-col w-full">
						<div class="mb-1 text-xs text-gray-500">{$i18n.t('Name')}</div>
						<input
							type="text"
							bind:value={localModel.name}
							class="w-full rounded-xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm outline-none focus:border-gray-300 dark:focus:border-gray-700 transition"
							placeholder={$i18n.t('Agent Name')}
							autocomplete="off"
							required
						/>
					</div>

					<div class="flex flex-col w-full">
						<div class="mb-1 text-xs text-gray-500">{$i18n.t('Description')}</div>
						<textarea
							bind:value={localModel.meta.description}
							class="w-full rounded-xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm outline-none focus:border-gray-300 dark:focus:border-gray-700 transition resize-none"
							placeholder={$i18n.t('A brief description of this agent')}
							rows="3"
						/>
					</div>

					<div class="flex flex-col w-full">
						<div class="mb-1 text-xs text-gray-500">{$i18n.t('Tags')}</div>
						<input
							type="text"
							value={tagsString}
							on:input={handleTagsInput}
							class="w-full rounded-xl border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 text-sm outline-none focus:border-gray-300 dark:focus:border-gray-700 transition"
							placeholder={$i18n.t('Comma-separated tags')}
							autocomplete="off"
						/>
					</div>

					<div class="flex items-center justify-between w-full">
						<div class="text-sm text-gray-700 dark:text-gray-300">{$i18n.t('Active')}</div>
						<Switch bind:state={localModel.is_active} />
					</div>

					<div class="flex justify-between items-center pt-3">
						<div>
							{#if confirmDelete}
								<button
									type="button"
									class="px-3.5 py-1.5 text-sm font-medium text-red-500 hover:text-red-600 transition"
									on:click={() => {
										dispatch('delete', { id: model.id });
										show = false;
									}}
								>
									{$i18n.t('Confirm Delete')}
								</button>
							{:else}
								<button
									type="button"
									class="px-3.5 py-1.5 text-sm font-medium text-red-500 hover:text-red-600 transition"
									on:click={() => {
										confirmDelete = true;
									}}
								>
									{$i18n.t('Delete')}
								</button>
							{/if}
						</div>

						<div class="flex gap-2">
							<button
								type="button"
								class="px-3.5 py-1.5 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition rounded-full"
								on:click={() => {
									show = false;
								}}
							>
								{$i18n.t('Cancel')}
							</button>
							<button
								type="submit"
								class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
							>
								{$i18n.t('Save')}
							</button>
						</div>
					</div>
				</div>
			</form>
		</div>
	{/if}
</Modal>
