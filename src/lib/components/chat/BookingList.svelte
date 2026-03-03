<script>
	import { fly } from 'svelte/transition';

	export let bookings = [];

	const STATUS_CONFIG = {
		draft:     { label: 'Chờ xác nhận', color: '#6366f1' },
		pending:   { label: 'Chờ duyệt',    color: '#f59e0b' },
		approved:  { label: 'Đã duyệt',     color: '#10b981' },
		rejected:  { label: 'Từ chối',      color: '#ef4444' },
		cancelled: { label: 'Đã hủy',       color: '#6b7280' },
		sent:      { label: 'Đã gửi',       color: '#3b82f6' }
	};

	const LOCATION_NAMES = { HN: 'Hà Nội', HCM: 'TP.HCM', DN: 'Đà Nẵng' };
	const DAY_NAMES = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];

	function formatDate(dateStr) {
		if (!dateStr) return '—';
		try {
			const [y, m, d] = dateStr.split('-');
			const dow = DAY_NAMES[new Date(dateStr).getDay()];
			return `${dow}, ${d}/${m}/${y}`;
		} catch {
			return dateStr;
		}
	}

	function locationDisplay(b) {
		const city = LOCATION_NAMES[b.location] || b.location || '—';
		return b.room_name ? `${city} / ${b.room_name}` : city;
	}

	function clientDisplay(b) {
		return b.client?.trim() || 'Nội bộ';
	}

	function getStatus(b) {
		return STATUS_CONFIG[b.status] ?? STATUS_CONFIG.pending;
	}
</script>

<div class="booking-list-card" in:fly={{ y: 20, duration: 400 }}>
	<!-- Header -->
	<div class="list-header">
		<div class="header-left">
			<svg class="header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
				<line x1="16" y1="2" x2="16" y2="6"></line>
				<line x1="8" y1="2" x2="8" y2="6"></line>
				<line x1="3" y1="10" x2="21" y2="10"></line>
			</svg>
			<div>
				<div class="header-label">CMC GLOBAL</div>
				<div class="header-title">Lịch họp của bạn</div>
			</div>
		</div>
		<div class="header-count">{bookings.length} cuộc họp</div>
	</div>

	<!-- Body -->
	<div class="list-body">
		{#if bookings.length === 0}
			<div class="empty-state">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40">
					<rect x="3" y="4" width="18" height="18" rx="2"></rect>
					<line x1="16" y1="2" x2="16" y2="6"></line>
					<line x1="8" y1="2" x2="8" y2="6"></line>
					<line x1="3" y1="10" x2="21" y2="10"></line>
				</svg>
				<p>Không có lịch họp sắp tới.</p>
			</div>
		{:else}
			{#each bookings as booking, i}
				{@const status = getStatus(booking)}
				<div
					class="booking-row"
					style="--accent: {status.color}"
					in:fly={{ y: 10, duration: 250, delay: i * 60 }}
				>
					<div class="accent-bar"></div>
					<div class="row-content">
						<div class="row-top">
							<span class="client-name">{clientDisplay(booking)}</span>
							<span class="status-badge" style="background: {status.color}20; color: {status.color}; border-color: {status.color}40">
								{status.label}
							</span>
						</div>
						<div class="row-meta">
							<div class="meta-item">
								<svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
									<line x1="16" y1="2" x2="16" y2="6"></line>
									<line x1="8" y1="2" x2="8" y2="6"></line>
									<line x1="3" y1="10" x2="21" y2="10"></line>
								</svg>
								<span>{formatDate(booking.date)}</span>
							</div>
							<div class="meta-item">
								<svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<circle cx="12" cy="12" r="10"></circle>
									<polyline points="12 6 12 12 16 14"></polyline>
								</svg>
								<span>{booking.start_time || '—'} – {booking.end_time || '—'}</span>
							</div>
							<div class="meta-item">
								<svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"></path>
									<circle cx="12" cy="10" r="3"></circle>
								</svg>
								<span>{locationDisplay(booking)}</span>
							</div>
						</div>
						{#if booking.title}
							<div class="booking-title">{booking.title}</div>
						{/if}
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>

<style>
	.booking-list-card {
		background: linear-gradient(145deg, rgba(255, 255, 255, 0.95) 0%, rgba(248, 250, 252, 0.95) 100%);
		backdrop-filter: blur(20px);
		border: 1px solid rgba(226, 232, 240, 0.8);
		border-radius: 20px;
		box-shadow:
			0 4px 6px -1px rgba(0, 0, 0, 0.02),
			0 10px 15px -3px rgba(0, 0, 0, 0.04),
			0 25px 50px -12px rgba(0, 0, 0, 0.08);
		width: 100%;
		max-width: 100%;
		overflow: hidden;
		font-family: 'Century Gothic', 'Trebuchet MS', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
	}

	/* ── Header ── */
	.list-header {
		background: linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #6366f1 100%);
		padding: 18px 24px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		position: relative;
		overflow: hidden;
	}

	.list-header::before {
		content: '';
		position: absolute;
		top: -50%;
		right: -10%;
		width: 160px;
		height: 160px;
		background: radial-gradient(circle, rgba(255, 255, 255, 0.12) 0%, transparent 70%);
		border-radius: 50%;
	}

	.header-left {
		display: flex;
		align-items: center;
		gap: 12px;
		position: relative;
		z-index: 1;
	}

	.header-icon {
		width: 28px;
		height: 28px;
		color: rgba(255, 255, 255, 0.85);
		flex-shrink: 0;
	}

	.header-label {
		font-size: 10px;
		font-weight: 700;
		color: rgba(255, 255, 255, 0.6);
		letter-spacing: 1.5px;
		text-transform: uppercase;
		margin-bottom: 2px;
	}

	.header-title {
		font-size: 17px;
		font-weight: 700;
		color: white;
		letter-spacing: 0.2px;
	}

	.header-count {
		font-size: 12px;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.75);
		background: rgba(255, 255, 255, 0.15);
		padding: 4px 12px;
		border-radius: 20px;
		position: relative;
		z-index: 1;
	}

	/* ── Body ── */
	.list-body {
		padding: 14px 16px;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	/* ── Empty state ── */
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		padding: 32px 20px;
		color: #94a3b8;
	}

	.empty-state svg {
		opacity: 0.4;
	}

	.empty-state p {
		font-size: 13px;
		color: #94a3b8;
		margin: 0;
	}

	/* ── Booking row ── */
	.booking-row {
		display: flex;
		background: white;
		border: 1px solid #e2e8f0;
		border-radius: 12px;
		overflow: hidden;
		transition: box-shadow 0.2s, transform 0.2s;
	}

	.booking-row:hover {
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
		transform: translateY(-1px);
	}

	.accent-bar {
		width: 4px;
		min-width: 4px;
		background: var(--accent, #6366f1);
		border-radius: 0;
		flex-shrink: 0;
	}

	.row-content {
		flex: 1;
		padding: 12px 14px;
		min-width: 0;
	}

	/* ── Row top: client + badge ── */
	.row-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		margin-bottom: 8px;
	}

	.client-name {
		font-size: 13px;
		font-weight: 700;
		color: #1e293b;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.status-badge {
		font-size: 10px;
		font-weight: 600;
		padding: 3px 9px;
		border-radius: 20px;
		border: 1px solid;
		white-space: nowrap;
		flex-shrink: 0;
	}

	/* ── Meta row ── */
	.row-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 10px 16px;
	}

	.meta-item {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 12px;
		color: #475569;
	}

	.meta-icon {
		width: 13px;
		height: 13px;
		color: #94a3b8;
		flex-shrink: 0;
	}

	/* ── Optional title ── */
	.booking-title {
		margin-top: 6px;
		font-size: 11px;
		color: #94a3b8;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
