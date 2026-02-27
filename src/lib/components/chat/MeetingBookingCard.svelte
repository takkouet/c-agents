<script>
	import { onMount } from 'svelte';

	export let booking = null;
	export let onConfirm = null;
	export let onCancel = null;
	export let onApprove = null;
	export let onReject = null;
	export let onAddNote = null;
	export let onOrderCatering = null;
	export let onApproveCatering = null;
	export let onRejectCatering = null;
	export let onSendCalendar = null;

	const STATUS_CONFIG = {
		draft: {
			label: 'Chờ xác nhận',
			color: 'bg-slate-100 text-slate-700 border-slate-300',
			bgColor: 'bg-slate-50'
		},
		pending: {
			label: 'Chờ duyệt',
			color: 'bg-amber-100 text-amber-700 border-amber-300',
			bgColor: 'bg-amber-50'
		},
		approved: {
			label: 'Đã duyệt',
			color: 'bg-emerald-100 text-emerald-700 border-emerald-300',
			bgColor: 'bg-emerald-50'
		},
		rejected: {
			label: 'Từ chối',
			color: 'bg-red-100 text-red-700 border-red-300',
			bgColor: 'bg-red-50'
		},
		cancelled: {
			label: 'Đã hủy',
			color: 'bg-slate-100 text-slate-500 border-slate-300',
			bgColor: 'bg-slate-50'
		},
		sent: {
			label: 'Đã gửi',
			color: 'bg-blue-100 text-blue-700 border-blue-300',
			bgColor: 'bg-blue-50'
		}
	};

	const EQUIPMENT_LABELS = {
		projector: 'Projector',
		whiteboard: 'Whiteboard',
		video_conf: 'Video Conference',
		tv: 'TV 55"',
		phone: 'Conference Phone',
		ac: 'Air Conditioning'
	};

	const CATERING_OPTIONS = [
		{ id: 'tea-coffee', name: 'Trà + Cà phê + Bánh', price: 35000 },
		{ id: 'coffee', name: 'Cà phê + Bánh', price: 30000 },
		{ id: 'water', name: 'Nước suối', price: 10000 },
		{ id: 'buffet', name: 'Buffet Trưa', price: 150000 },
		{ id: 'lunch-box', name: 'Cơm hộp', price: 50000 },
		{ id: 'fruit', name: 'Trái cây', price: 25000 }
	];

	$: statusConfig = booking
		? STATUS_CONFIG[booking.status] || STATUS_CONFIG.pending
		: STATUS_CONFIG.pending;

	let adminNote = booking?.admin_note || '';
	let selectedCatering = [];
	let cateringTotal = 0;

	function formatDate(dateStr) {
		if (!dateStr) return '';
		const [year, month, day] = dateStr.split('-');
		return `${day}/${month}/${year}`;
	}

	function getInitials(name) {
		if (!name) return 'A';
		return name
			.split(' ')
			.map((n) => n[0])
			.join('')
			.toUpperCase()
			.slice(0, 2);
	}

	function toggleCatering(item) {
		const idx = selectedCatering.findIndex((c) => c.id === item.id);
		if (idx >= 0) {
			selectedCatering = selectedCatering.filter((c) => c.id !== item.id);
		} else {
			selectedCatering = [...selectedCatering, { ...item, quantity: booking?.capacity || 5 }];
		}
		updateCateringTotal();
	}

	function updateCateringTotal() {
		cateringTotal = selectedCatering.reduce(
			(sum, item) => sum + item.price * (item.quantity || 1),
			0
		);
	}

	function handleAddNote() {
		if (onAddNote && adminNote) {
			onAddNote(booking.id, adminNote);
		}
	}

	function handleOrderCatering() {
		if (onOrderCatering) {
			onOrderCatering(booking.id, selectedCatering, cateringTotal);
		}
	}

	onMount(() => {
		if (booking?.catering?.items) {
			selectedCatering = booking.catering.items;
			updateCateringTotal();
		}
		if (booking?.admin_note) {
			adminNote = booking.admin_note;
		}
	});
</script>

{#if booking}
	<div class="meeting-booking-card">
		<!-- Header -->
		<div class="card-header">
			<div class="header-left">
				<span class="section-label">BOOKING REQUEST</span>
				<span class="booking-id">{booking.id}</span>
			</div>
			<div class="status-badge {statusConfig.color}">
				{statusConfig.label}
			</div>
		</div>

		<!-- Main Content -->
		<div class="card-body">
			<!-- Title -->
			<div class="detail-section">
				<div class="detail-label">Meeting Title</div>
				<div class="detail-value title-value">
					{booking.title || 'Cuộc họp'}
				</div>
			</div>

			<!-- Date, Time, Capacity Grid -->
			<div class="info-grid">
				<div class="info-item">
					<div class="info-label">Date</div>
					<div class="info-value">{formatDate(booking.date)}</div>
				</div>
				<div class="info-item">
					<div class="info-label">Time</div>
					<div class="info-value">{booking.start_time} - {booking.end_time}</div>
				</div>
				<div class="info-item">
					<div class="info-label">Capacity</div>
					<div class="info-value">{booking.capacity || booking.room_capacity || 5} persons</div>
				</div>
			</div>

			<!-- Location & Room -->
			<div class="info-grid">
				<div class="info-item">
					<div class="info-label">Location</div>
					<div class="info-value">{booking.room_code || 'HNO'}</div>
				</div>
				<div class="info-item">
					<div class="info-label">Room</div>
					<div class="info-value">{booking.room_name || 'Phòng A1'}</div>
				</div>
				<div class="info-item">
					<div class="info-label">Floor</div>
					<div class="info-value">Floor {booking.room_floor || booking.floor || 1}</div>
				</div>
			</div>

			<!-- Divider -->
			<div class="divider"></div>

			<!-- Equipment -->
			<div class="detail-section">
				<div class="detail-label">Equipment</div>
				<div class="equipment-list">
					{#if booking.room_equipment && booking.room_equipment.length > 0}
						{#each booking.room_equipment as eq}
							<span class="equipment-tag">{EQUIPMENT_LABELS[eq] || eq}</span>
						{/each}
					{:else if booking.equipment && booking.equipment.length > 0}
						{#each booking.equipment as eq}
							<span class="equipment-tag">{EQUIPMENT_LABELS[eq] || eq}</span>
						{/each}
					{:else}
						<span class="no-equipment">No equipment required</span>
					{/if}
				</div>
			</div>

			<!-- Divider -->
			<div class="divider"></div>

			<!-- Catering -->
			<div class="detail-section">
				<div class="detail-label">Catering</div>
				<div class="catering-grid">
					{#each CATERING_OPTIONS as item}
						{@const isSelected = selectedCatering.some((c) => c.id === item.id)}
						<button
							class="catering-item {isSelected ? 'selected' : ''}"
							on:click={() => toggleCatering(item)}
						>
							<span class="catering-check">{isSelected ? '☑' : '☐'}</span>
							<span class="catering-name">{item.name}</span>
							<span class="catering-price">{item.price.toLocaleString()} VNĐ</span>
						</button>
					{/each}
				</div>
				{#if selectedCatering.length > 0}
					<div class="catering-total">
						<span>Total:</span>
						<span class="total-amount">{cateringTotal.toLocaleString()} VNĐ</span>
					</div>
				{/if}
			</div>

			<!-- Divider -->
			<div class="divider"></div>

			<!-- Admin Note -->
			<div class="detail-section">
				<div class="detail-label">Admin Note</div>
				<textarea
					class="admin-note-input"
					placeholder="Add note for admin..."
					bind:value={adminNote}
					on:blur={handleAddNote}
				></textarea>
			</div>

			<!-- Divider -->
			<div class="divider"></div>

			<!-- Workflow Timeline -->
			<div class="detail-section">
				<div class="detail-label">Approval Workflow</div>
				<div class="workflow-timeline">
					<!-- Step 1: Book Request -->
					<div class="workflow-step completed">
						<div class="step-indicator">
							<span class="step-icon">✓</span>
						</div>
						<div class="step-content">
							<div class="step-title">Book Request</div>
							<div class="step-time">{formatDate(booking.date)} {booking.start_time}</div>
						</div>
					</div>

					<!-- Step 2: User Confirmation -->
					<div
						class="workflow-step {booking.status === 'draft'
							? 'in-progress'
							: booking.status === 'cancelled'
								? 'rejected'
								: 'completed'}"
					>
						<div class="step-indicator">
							<span class="step-icon">{booking.status === 'draft' ? '2' : '✓'}</span>
						</div>
						<div class="step-content">
							<div class="step-title">User Confirmation</div>
							{#if booking.status === 'draft'}
								<div class="step-action">
									<button class="btn-confirm" on:click={() => onConfirm && onConfirm(booking.id)}>
										Confirm Booking
									</button>
									<button class="btn-cancel" on:click={() => onCancel && onCancel(booking.id)}>
										Cancel
									</button>
								</div>
							{:else}
								<div class="step-time">Confirmed</div>
							{/if}
						</div>
					</div>

					<!-- Step 3: Admin Approval -->
					<div
						class="workflow-step {booking.status === 'pending'
							? 'in-progress'
							: booking.status === 'approved' || booking.status === 'sent'
								? 'completed'
								: booking.status === 'rejected'
									? 'rejected'
									: 'pending'}"
					>
						<div class="step-indicator">
							<span class="step-icon">
								{booking.status === 'pending'
									? '3'
									: booking.status === 'approved' || booking.status === 'sent'
										? '✓'
										: '○'}
							</span>
						</div>
						<div class="step-content">
							<div class="step-title">Admin Approval</div>
							{#if booking.status === 'pending'}
								<div class="step-assignee">
									<span class="avatar">{getInitials(booking.approver?.name)}</span>
									<span class="assignee-name">{booking.approver?.name || 'Nguyễn Văn Trang'}</span>
								</div>
								<div class="step-action">
									<button class="btn-approve" on:click={() => onApprove && onApprove(booking.id)}>
										Approve
									</button>
									<button class="btn-reject" on:click={() => onReject && onReject(booking.id)}>
										Reject
									</button>
								</div>
							{:else if booking.status === 'approved' || booking.status === 'sent'}
								<div class="step-time">Approved by {booking.approver?.name}</div>
							{:else}
								<div class="step-time">Pending</div>
							{/if}
						</div>
					</div>

					<!-- Step 4: Catering Approval -->
					<div
						class="workflow-step {booking.catering?.status === 'pending'
							? 'in-progress'
							: booking.catering?.status === 'approved'
								? 'completed'
								: 'pending'}"
					>
						<div class="step-indicator">
							<span class="step-icon">
								{booking.catering?.status === 'pending'
									? '4'
									: booking.catering?.status === 'approved'
										? '✓'
										: '○'}
							</span>
						</div>
						<div class="step-content">
							<div class="step-title">Catering Approval</div>
							{#if booking.catering?.status === 'pending'}
								<div class="step-action">
									<button
										class="btn-approve"
										on:click={() => onApproveCatering && onApproveCatering(booking.id)}
									>
										Approve Catering
									</button>
									<button
										class="btn-reject"
										on:click={() => onRejectCatering && onRejectCatering(booking.id)}
									>
										Reject
									</button>
								</div>
							{:else if booking.catering?.status === 'approved'}
								<div class="step-time">Catering Approved</div>
							{:else}
								<div class="step-time">No catering ordered</div>
							{/if}
						</div>
					</div>

					<!-- Step 5: Send Calendar -->
					<div class="workflow-step {booking.status === 'sent' ? 'completed' : 'pending'}">
						<div class="step-indicator">
							<span class="step-icon">{booking.status === 'sent' ? '✓' : '5'}</span>
						</div>
						<div class="step-content">
							<div class="step-title">Send Calendar Invite</div>
							{#if booking.status === 'sent'}
								<div class="step-time">Calendar invite sent</div>
							{:else if booking.status === 'approved'}
								<div class="step-action">
									<button
										class="btn-send"
										on:click={() => onSendCalendar && onSendCalendar(booking.id)}
									>
										Send Calendar Invite
									</button>
								</div>
							{:else}
								<div class="step-time">Waiting for approval</div>
							{/if}
						</div>
					</div>
				</div>
			</div>

			<!-- Email Confirmation (if sent) -->
			{#if booking.status === 'sent'}
				<div class="divider"></div>
				<div class="email-confirmation">
					<div class="email-success">
						<span class="email-icon">✓</span>
						<span class="email-title">Calendar Invite Sent Successfully</span>
					</div>
					<div class="recipients-list">
						<div class="recipients-label">Recipients:</div>
						<div class="recipient-item">
							• {booking.requester || 'user@cmcglobal.vn'} (Requester)
						</div>
						<div class="recipient-item">
							• {booking.approver?.email || 'nvtrang3@cmcglobal.vn'} (Admin)
						</div>
						{#if booking.attendees && booking.attendees.length > 0}
							{#each booking.attendees as attendee}
								<div class="recipient-item">• {attendee}</div>
							{/each}
						{/if}
					</div>
					<div class="meeting-preview">
						<div class="preview-label">Meeting Details:</div>
						<div class="preview-item">
							{formatDate(booking.date)} • {booking.start_time} - {booking.end_time}
						</div>
						<div class="preview-item">{booking.room_name} - {booking.room_code}</div>
						<div class="preview-item">{booking.title}</div>
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.meeting-booking-card {
		background: #ffffff;
		border: 1px solid #e2e8f0;
		border-radius: 12px;
		max-width: 560px;
		overflow: hidden;
		font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
	}

	.card-header {
		background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
		padding: 16px 20px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.header-left {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.section-label {
		font-size: 11px;
		font-weight: 600;
		color: rgba(255, 255, 255, 0.7);
		letter-spacing: 0.5px;
	}

	.booking-id {
		font-size: 18px;
		font-weight: 700;
		color: #ffffff;
		font-family: 'JetBrains Mono', monospace;
	}

	.status-badge {
		padding: 6px 12px;
		border-radius: 20px;
		font-size: 12px;
		font-weight: 600;
		border: 1px solid;
	}

	.card-body {
		padding: 20px;
	}

	.detail-section {
		margin-bottom: 16px;
	}

	.detail-label {
		font-size: 11px;
		font-weight: 600;
		color: #64748b;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		margin-bottom: 8px;
	}

	.detail-value {
		font-size: 15px;
		color: #1e293b;
	}

	.title-value {
		font-size: 17px;
		font-weight: 600;
	}

	.info-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 12px;
		margin-bottom: 16px;
	}

	.info-item {
		background: #f8fafc;
		padding: 12px;
		border-radius: 8px;
	}

	.info-label {
		font-size: 11px;
		color: #94a3b8;
		margin-bottom: 4px;
	}

	.info-value {
		font-size: 14px;
		font-weight: 600;
		color: #1e293b;
	}

	.divider {
		height: 1px;
		background: #e2e8f0;
		margin: 16px 0;
	}

	.equipment-list {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.equipment-tag {
		background: #f1f5f9;
		color: #475569;
		padding: 6px 12px;
		border-radius: 6px;
		font-size: 13px;
	}

	.no-equipment {
		color: #94a3b8;
		font-size: 13px;
		font-style: italic;
	}

	.catering-grid {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.catering-item {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 10px 12px;
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 8px;
		cursor: pointer;
		transition: all 0.2s;
		text-align: left;
	}

	.catering-item:hover {
		background: #f1f5f9;
		border-color: #cbd5e1;
	}

	.catering-item.selected {
		background: #eff6ff;
		border-color: #3b82f6;
	}

	.catering-check {
		font-size: 14px;
		color: #3b82f6;
	}

	.catering-name {
		flex: 1;
		font-size: 13px;
		color: #1e293b;
	}

	.catering-price {
		font-size: 12px;
		color: #64748b;
	}

	.catering-total {
		display: flex;
		justify-content: space-between;
		margin-top: 12px;
		padding-top: 12px;
		border-top: 1px solid #e2e8f0;
		font-weight: 600;
	}

	.total-amount {
		color: #1e40af;
		font-size: 16px;
	}

	.admin-note-input {
		width: 100%;
		min-height: 80px;
		padding: 12px;
		border: 1px solid #e2e8f0;
		border-radius: 8px;
		font-size: 13px;
		resize: vertical;
		font-family: inherit;
	}

	.admin-note-input:focus {
		outline: none;
		border-color: #3b82f6;
	}

	.workflow-timeline {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.workflow-step {
		display: flex;
		gap: 12px;
		padding: 12px 0;
		position: relative;
	}

	.workflow-step:not(:last-child)::before {
		content: '';
		position: absolute;
		left: 15px;
		top: 44px;
		bottom: -12px;
		width: 2px;
		background: #e2e8f0;
	}

	.workflow-step.completed::before {
		background: #10b981;
	}

	.workflow-step.rejected::before {
		background: #ef4444;
	}

	.step-indicator {
		width: 32px;
		height: 32px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 13px;
		font-weight: 600;
		flex-shrink: 0;
		background: #e2e8f0;
		color: #64748b;
	}

	.workflow-step.completed .step-indicator {
		background: #10b981;
		color: white;
	}

	.workflow-step.in-progress .step-indicator {
		background: #f59e0b;
		color: white;
		animation: pulse 2s infinite;
	}

	.workflow-step.rejected .step-indicator {
		background: #ef4444;
		color: white;
	}

	.step-icon {
		font-size: 14px;
	}

	.step-content {
		flex: 1;
	}

	.step-title {
		font-size: 14px;
		font-weight: 600;
		color: #1e293b;
	}

	.step-time {
		font-size: 12px;
		color: #64748b;
		margin-top: 2px;
	}

	.step-assignee {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 8px;
	}

	.avatar {
		width: 24px;
		height: 24px;
		border-radius: 50%;
		background: #1e40af;
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 10px;
		font-weight: 600;
	}

	.assignee-name {
		font-size: 13px;
		color: #475569;
	}

	.step-action {
		display: flex;
		gap: 8px;
		margin-top: 8px;
	}

	.btn-confirm,
	.btn-approve,
	.btn-send {
		padding: 6px 14px;
		background: #1e40af;
		color: white;
		border: none;
		border-radius: 6px;
		font-size: 12px;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.2s;
	}

	.btn-confirm:hover,
	.btn-approve:hover,
	.btn-send:hover {
		background: #1e3a8a;
	}

	.btn-cancel,
	.btn-reject {
		padding: 6px 14px;
		background: white;
		color: #64748b;
		border: 1px solid #e2e8f0;
		border-radius: 6px;
		font-size: 12px;
		font-weight: 500;
		cursor: pointer;
	}

	.btn-cancel:hover,
	.btn-reject:hover {
		background: #f8fafc;
	}

	.email-confirmation {
		background: #f0fdf4;
		border: 1px solid #bbf7d0;
		border-radius: 8px;
		padding: 16px;
	}

	.email-success {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 12px;
	}

	.email-icon {
		width: 28px;
		height: 28px;
		background: #10b981;
		color: white;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 14px;
	}

	.email-title {
		font-size: 15px;
		font-weight: 600;
		color: #166534;
	}

	.recipients-list {
		margin-bottom: 12px;
	}

	.recipients-label,
	.preview-label {
		font-size: 11px;
		color: #64748b;
		text-transform: uppercase;
		margin-bottom: 6px;
	}

	.recipient-item,
	.preview-item {
		font-size: 13px;
		color: #475569;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.6;
		}
	}
</style>
