<script lang="ts">
	import { writable } from 'svelte/store';
	import { SvelteFlow, Background, type Node, type Edge, type BackgroundVariant } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';
	import AgentNode from './AgentNode.svelte';
	import type { TimelineItem } from '$lib/stores/orchestration';

	export let timelineItems: TimelineItem[] = [];

	const variant: BackgroundVariant = 'dots';

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const nodeTypes: Record<string, any> = { agent: AgentNode };

	const nodes = writable<Node[]>([]);
	const edges = writable<Edge[]>([]);

	const X_POSITIONS: Record<number, number[]> = {
		1: [145],
		2: [30, 260],
		3: [0, 145, 290]
	};

	$: {
		const orchestratorItem =
			timelineItems.find((i) => i.id === 'orchestrator') ?? timelineItems[0];
		const agents = timelineItems.filter((i) => i.id !== 'orchestrator');

		nodes.set([
			{
				id: 'orchestrator',
				type: 'agent',
				position: { x: 145, y: 20 },
				data: orchestratorItem
			},
			...agents.map((item, idx) => ({
				id: item.id,
				type: 'agent',
				position: {
					x: (X_POSITIONS[agents.length] ?? [idx * 160])[idx] ?? idx * 160,
					y: 160
				},
				data: item
			}))
		]);

		edges.set(
			agents.map((item) => ({
				id: `orchestrator->${item.id}`,
				source: 'orchestrator',
				target: item.id,
				animated: item.status === 'active',
				style:
					item.status === 'done'
						? 'stroke:#22c55e; stroke-width:2px;'
						: item.status === 'active'
							? 'stroke:#3b82f6; stroke-width:2px;'
							: item.status === 'waiting'
								? 'stroke:#f59e0b; stroke-width:2px;'
								: 'stroke:#d1d5db; stroke-width:1.5px;'
			}))
		);
	}
</script>

<div class="h-full w-full">
	<SvelteFlow
		{nodes}
		{edges}
		{nodeTypes}
		fitView
		nodesDraggable={false}
		nodesConnectable={false}
		elementsSelectable={false}
		panOnDrag={false}
		zoomOnScroll={false}
	>
		<Background {variant} gap={16} size={1} color="#d1d5db" />
	</SvelteFlow>
</div>
