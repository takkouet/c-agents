const AGENTS_BASE_URL = 'http://localhost:4001';

export interface AgentInfo {
	id: string;
	name: string;
	purpose: string;
	department: string;
	icon: string;
	model: string;
	enabled: boolean;
	created: number;
	base_url: string;
	is_external: boolean;
}

export interface AgentConfig extends AgentInfo {
	base_url: string;
	api_key: string;
	llm_base_url: string;
	llm_api_key: string;
	system_prompt: string;
	is_orchestrator?: boolean;
	is_external: boolean;
}

export async function getAgents(): Promise<AgentInfo[]> {
	try {
		const res = await fetch(`${AGENTS_BASE_URL}/v1/agents`);
		if (!res.ok) return [];
		const data = await res.json();
		return data.data ?? [];
	} catch {
		return [];
	}
}

export async function getAllAgents(): Promise<AgentConfig[]> {
	try {
		const res = await fetch(`${AGENTS_BASE_URL}/v1/agents/all`);
		if (!res.ok) return [];
		const data = await res.json();
		return data.data ?? [];
	} catch {
		return [];
	}
}

export async function getAgent(id: string): Promise<AgentConfig | null> {
	try {
		const res = await fetch(`${AGENTS_BASE_URL}/v1/agents/${id}`);
		if (!res.ok) return null;
		return await res.json();
	} catch {
		return null;
	}
}

export async function createAgent(config: Partial<AgentConfig>): Promise<AgentConfig> {
	const res = await fetch(`${AGENTS_BASE_URL}/v1/agents`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(config)
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({}));
		throw new Error(err?.error ?? `HTTP ${res.status}`);
	}
	return await res.json();
}

export async function updateAgent(id: string, config: Partial<AgentConfig>): Promise<AgentConfig> {
	const res = await fetch(`${AGENTS_BASE_URL}/v1/agents/${id}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(config)
	});
	if (!res.ok) {
		const err = await res.json().catch(() => ({}));
		throw new Error(err?.error ?? `HTTP ${res.status}`);
	}
	return await res.json();
}

export async function deleteAgent(id: string): Promise<boolean> {
	try {
		const res = await fetch(`${AGENTS_BASE_URL}/v1/agents/${id}`, { method: 'DELETE' });
		return res.ok;
	} catch {
		return false;
	}
}

export async function getAgentHealth(): Promise<boolean> {
	try {
		const res = await fetch(`${AGENTS_BASE_URL}/health`);
		return res.ok;
	} catch {
		return false;
	}
}

export async function getAgentHealthById(agent: AgentInfo): Promise<boolean> {
	try {
		let healthUrl: string;
		if (agent.is_external && agent.base_url) {
			healthUrl = agent.base_url.replace(/\/+$/, '') + '/health';
		} else {
			healthUrl = `${AGENTS_BASE_URL}/v1/${agent.id}/health`;
		}
		const res = await fetch(healthUrl, { signal: AbortSignal.timeout(5000) });
		return res.ok;
	} catch {
		return false;
	}
}
