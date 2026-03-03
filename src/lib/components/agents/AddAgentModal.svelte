<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import {
		createAgent,
		updateAgent,
		deleteAgent,
		getAgentHealth,
		type AgentConfig
	} from '$lib/apis/agents';

	export let show = false;
	/** Pass an existing agent to open in edit mode; undefined = create mode */
	export let agent: AgentConfig | undefined = undefined;

	const dispatch = createEventDispatcher<{ saved: AgentConfig; deleted: string }>();

	// ── Form state ──────────────────────────────────────────────────
	let mode: 'external' | 'builtin' = 'builtin';
	let id = '';
	let name = '';
	let icon = '🤖';
	let department = '';
	let purpose = '';
	let base_url = '';
	let api_key = '';
	let llm_base_url = '';
	let llm_api_key = '';
	let model = '';
	let system_prompt = '';
	let enabled = true;

	let saving = false;
	let deleting = false;
	let connectionStatus: 'idle' | 'testing' | 'ok' | 'fail' = 'idle';
	let errorMsg = '';
	let confirmDelete = false;

	$: isEdit = !!agent;

	// Auto-generate slug from name (create mode only)
	$: if (!isEdit && name) {
		id = name
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-|-$/g, '');
	}

	// Populate form when agent changes
	$: if (agent) {
		id = agent.id;
		name = agent.name;
		icon = agent.icon;
		department = agent.department;
		purpose = agent.purpose;
		base_url = agent.base_url ?? '';
		api_key = agent.api_key ?? '';
		llm_base_url = agent.llm_base_url ?? '';
		llm_api_key = agent.llm_api_key ?? '';
		model = agent.model;
		system_prompt = agent.system_prompt;
		enabled = agent.enabled ?? true;
		mode = agent.is_external ? 'external' : 'builtin';
	}

	function reset() {
		mode = 'builtin';
		id = '';
		name = '';
		icon = '🤖';
		department = '';
		purpose = '';
		base_url = '';
		api_key = '';
		llm_base_url = '';
		llm_api_key = '';
		model = '';
		system_prompt = '';
		enabled = true;
		saving = false;
		deleting = false;
		connectionStatus = 'idle';
		errorMsg = '';
		confirmDelete = false;
	}

	function close() {
		reset();
		show = false;
	}

	async function testConnection() {
		connectionStatus = 'testing';
		try {
			if (mode === 'external') {
				if (!base_url) {
					connectionStatus = 'idle';
					return;
				}
				const healthUrl = base_url.replace(/\/+$/, '') + '/health';
				const res = await fetch(healthUrl, { signal: AbortSignal.timeout(5000) });
				connectionStatus = res.ok ? 'ok' : 'fail';
			} else {
				const ok = await getAgentHealth();
				connectionStatus = ok ? 'ok' : 'fail';
			}
		} catch {
			connectionStatus = 'fail';
		}
	}

	async function save() {
		if (mode === 'external') {
			if (!name.trim() || !base_url.trim()) {
				errorMsg = 'Name and Base URL are required for external agents.';
				return;
			}
		} else {
			if (!name.trim() || !llm_base_url.trim() || !model.trim() || !system_prompt.trim()) {
				errorMsg = 'Name, LLM Base URL, Model, and System Prompt are required for built-in agents.';
				return;
			}
		}
		errorMsg = '';
		saving = true;
		try {
			const payload: Partial<AgentConfig> = {
				id,
				name,
				icon,
				department,
				purpose,
				model,
				system_prompt,
				enabled
			};
			if (mode === 'external') {
				payload.base_url = base_url;
				payload.api_key = api_key;
				payload.llm_base_url = '';
				payload.llm_api_key = '';
			} else {
				payload.llm_base_url = llm_base_url;
				payload.llm_api_key = llm_api_key;
				payload.base_url = '';
				payload.api_key = '';
			}
			let saved: AgentConfig;
			if (isEdit) {
				saved = await updateAgent(agent!.id, payload);
			} else {
				saved = await createAgent(payload);
			}
			dispatch('saved', saved);
			close();
		} catch (e: unknown) {
			errorMsg = e instanceof Error ? e.message : 'An error occurred.';
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (!confirmDelete) {
			confirmDelete = true;
			return;
		}
		deleting = true;
		const ok = await deleteAgent(agent!.id);
		if (ok) {
			dispatch('deleted', agent!.id);
			close();
		} else {
			errorMsg = 'Failed to delete agent.';
		}
		deleting = false;
	}
</script>

<Modal bind:show size="md" on:close={close}>
	<div
		class="flex items-center justify-between px-5 pt-4 pb-3 border-b border-gray-100 dark:border-gray-800"
	>
		<h2 class="text-sm font-semibold text-gray-900 dark:text-white">
			{isEdit ? 'Edit Agent' : 'Add Agent'}
		</h2>
		<button
			class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
			on:click={close}
			aria-label="Close"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-4 w-4"
				viewBox="0 0 20 20"
				fill="currentColor"
			>
				<path
					fill-rule="evenodd"
					d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
					clip-rule="evenodd"
				/>
			</svg>
		</button>
	</div>

	<div class="px-5 py-4 space-y-4 overflow-y-auto max-h-[70vh]">
		<!-- Mode toggle -->
		<div class="flex flex-col gap-2">
			<div
				class="flex rounded-lg border border-gray-200 dark:border-gray-700 p-0.5 bg-gray-50 dark:bg-gray-800"
			>
				<button
					type="button"
					class="flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-all
						{mode === 'external'
						? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm'
						: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
					on:click={() => {
						mode = 'external';
						connectionStatus = 'idle';
					}}
				>
					External Agent
				</button>
				<button
					type="button"
					class="flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-all
						{mode === 'builtin'
						? 'bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm'
						: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
					on:click={() => {
						mode = 'builtin';
						connectionStatus = 'idle';
					}}
				>
					Built-in Agent
				</button>
			</div>
			<p class="text-[11px] text-gray-400 dark:text-gray-500">
				{mode === 'external'
					? 'Connect to an agent running on a separate server.'
					: 'Run an agent on this server using an LLM backend.'}
			</p>
		</div>

		<!-- Identity row -->
		<div class="flex gap-3">
			<!-- Icon -->
			<div class="flex flex-col w-16 shrink-0">
				<label for="agent-icon" class="mb-1 text-xs text-gray-500 dark:text-gray-400">Icon</label>
				<input
					id="agent-icon"
					class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1.5 text-center text-xl outline-none focus:ring-1 focus:ring-blue-500"
					type="text"
					bind:value={icon}
					maxlength="2"
					placeholder="🤖"
				/>
			</div>
			<!-- Name -->
			<div class="flex flex-col flex-1">
				<label for="agent-name" class="mb-1 text-xs text-gray-500 dark:text-gray-400"
					>Name <span class="text-red-400">*</span></label
				>
				<input
					id="agent-name"
					class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-blue-500"
					type="text"
					bind:value={name}
					placeholder="e.g. Legal Agent"
				/>
			</div>
		</div>

		<!-- Agent ID -->
		<div class="flex flex-col">
			<label for="agent-id" class="mb-1 text-xs text-gray-500 dark:text-gray-400">
				Agent ID
				{#if !isEdit}<span class="text-gray-400">(auto-generated from name)</span>{/if}
			</label>
			<input
				id="agent-id"
				class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-1.5 text-sm font-mono outline-none
					{isEdit ? 'opacity-60 cursor-not-allowed' : 'focus:ring-1 focus:ring-blue-500'}"
				type="text"
				bind:value={id}
				placeholder="e.g. legal"
				disabled={isEdit}
			/>
		</div>

		<!-- Department + Purpose -->
		<div class="flex gap-3">
			<div class="flex flex-col w-40 shrink-0">
				<label for="agent-dept" class="mb-1 text-xs text-gray-500 dark:text-gray-400"
					>Department</label
				>
				<input
					id="agent-dept"
					class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-blue-500"
					type="text"
					bind:value={department}
					placeholder="e.g. Legal"
				/>
			</div>
			<div class="flex flex-col flex-1">
				<label for="agent-purpose" class="mb-1 text-xs text-gray-500 dark:text-gray-400"
					>Purpose</label
				>
				<input
					id="agent-purpose"
					class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-blue-500"
					type="text"
					bind:value={purpose}
					placeholder="Brief description shown in the directory"
				/>
			</div>
		</div>

		<!-- ── Connection section (varies by mode) ── -->
		{#if mode === 'external'}
			<!-- External: Base URL + Test -->
			<div class="flex flex-col">
				<label for="agent-url" class="mb-1 text-xs text-gray-500 dark:text-gray-400">
					Base URL <span class="text-red-400">*</span>
				</label>
				<div class="flex gap-2">
					<input
						id="agent-url"
						class="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm font-mono outline-none focus:ring-1 focus:ring-blue-500"
						type="text"
						bind:value={base_url}
						placeholder="http://localhost:5001/v1"
					/>
					<button
						class="shrink-0 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1.5 text-xs font-medium
							hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors
							{connectionStatus === 'ok' ? 'border-green-400 text-green-600' : ''}
							{connectionStatus === 'fail' ? 'border-red-400 text-red-500' : ''}
							{connectionStatus === 'testing' ? 'opacity-60 cursor-wait' : ''}"
						on:click={testConnection}
						disabled={connectionStatus === 'testing'}
						type="button"
					>
						{#if connectionStatus === 'testing'}
							Testing...
						{:else if connectionStatus === 'ok'}
							Connected
						{:else if connectionStatus === 'fail'}
							Failed
						{:else}
							Test
						{/if}
					</button>
				</div>
			</div>

			<!-- External: API Key -->
			<div class="flex flex-col">
				<label for="agent-apikey" class="mb-1 text-xs text-gray-500 dark:text-gray-400"
					>API Key</label
				>
				<SensitiveInput
					id="agent-apikey"
					bind:value={api_key}
					placeholder="Leave blank if not required"
				/>
			</div>
		{:else}
			<!-- Built-in: LLM Base URL + Test -->
			<div class="flex flex-col">
				<label for="agent-llm-url" class="mb-1 text-xs text-gray-500 dark:text-gray-400">
					LLM Base URL <span class="text-red-400">*</span>
				</label>
				<div class="flex gap-2">
					<input
						id="agent-llm-url"
						class="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm font-mono outline-none focus:ring-1 focus:ring-blue-500"
						type="text"
						bind:value={llm_base_url}
						placeholder="https://generativelanguage.googleapis.com/v1beta"
					/>
					<button
						class="shrink-0 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-1.5 text-xs font-medium
							hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors
							{connectionStatus === 'ok' ? 'border-green-400 text-green-600' : ''}
							{connectionStatus === 'fail' ? 'border-red-400 text-red-500' : ''}
							{connectionStatus === 'testing' ? 'opacity-60 cursor-wait' : ''}"
						on:click={testConnection}
						disabled={connectionStatus === 'testing'}
						type="button"
					>
						{#if connectionStatus === 'testing'}
							Testing...
						{:else if connectionStatus === 'ok'}
							Connected
						{:else if connectionStatus === 'fail'}
							Failed
						{:else}
							Test
						{/if}
					</button>
				</div>
				<span class="mt-1 text-[10px] text-gray-400 dark:text-gray-600"
					>Tests agent server health at localhost:4001</span
				>
			</div>

			<!-- Built-in: LLM API Key -->
			<div class="flex flex-col">
				<label for="agent-llm-apikey" class="mb-1 text-xs text-gray-500 dark:text-gray-400"
					>LLM API Key</label
				>
				<SensitiveInput
					id="agent-llm-apikey"
					bind:value={llm_api_key}
					placeholder="Leave blank if not required"
				/>
			</div>
		{/if}

		<!-- Model -->
		<div class="flex flex-col">
			<label for="agent-model" class="mb-1 text-xs text-gray-500 dark:text-gray-400">
				Model {#if mode === 'builtin'}<span class="text-red-400">*</span>{/if}
			</label>
			<input
				id="agent-model"
				class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-sm font-mono outline-none focus:ring-1 focus:ring-blue-500"
				type="text"
				bind:value={model}
				placeholder="e.g. gemini-2.5-flash, gpt-4o, llama3"
			/>
		</div>

		<!-- System Prompt -->
		<div class="flex flex-col">
			<label for="agent-prompt" class="mb-1 text-xs text-gray-500 dark:text-gray-400">
				System Prompt {#if mode === 'builtin'}<span class="text-red-400">*</span>{/if}
			</label>
			<textarea
				id="agent-prompt"
				class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-blue-500 resize-y min-h-[100px]"
				bind:value={system_prompt}
				placeholder="You are a specialist AI assistant for..."
				rows="5"
			/>
		</div>

		{#if errorMsg}
			<p class="text-xs text-red-500">{errorMsg}</p>
		{/if}
	</div>

	<!-- Footer -->
	<div
		class="flex items-center justify-between px-5 py-3 border-t border-gray-100 dark:border-gray-800"
	>
		<!-- Delete (edit mode) -->
		<div>
			{#if isEdit && !agent?.is_orchestrator}
				{#if confirmDelete}
					<div class="flex items-center gap-2">
						<span class="text-xs text-red-500">Are you sure?</span>
						<button
							class="px-3 py-1.5 text-xs font-medium rounded-full bg-red-500 hover:bg-red-600 text-white transition-colors"
							on:click={remove}
							disabled={deleting}
						>
							{deleting ? 'Deleting...' : 'Confirm Delete'}
						</button>
						<button
							class="px-3 py-1.5 text-xs font-medium rounded-full border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
							on:click={() => (confirmDelete = false)}
						>
							Cancel
						</button>
					</div>
				{:else}
					<button
						class="px-3 py-1.5 text-xs font-medium rounded-full border border-red-200 dark:border-red-900 text-red-500 hover:bg-red-50 dark:hover:bg-red-950 transition-colors"
						on:click={remove}
					>
						Delete
					</button>
				{/if}
			{/if}
		</div>

		<!-- Save / Cancel -->
		<div class="flex items-center gap-2">
			<button
				class="px-3.5 py-1.5 text-xs font-medium rounded-full border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
				on:click={close}
			>
				Cancel
			</button>
			<button
				class="px-3.5 py-1.5 text-xs font-medium rounded-full bg-black hover:bg-gray-800 dark:bg-white dark:hover:bg-gray-200 text-white dark:text-black transition-colors disabled:opacity-50"
				on:click={save}
				disabled={saving}
			>
				{saving ? 'Saving...' : isEdit ? 'Save Changes' : 'Add Agent'}
			</button>
		</div>
	</div>
</Modal>
