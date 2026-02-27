<script>
	import { onMount } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { createEventDispatcher } from 'svelte';
	import { toast } from 'svelte-sonner';

	import RoomList from '$lib/components/chat/RoomList.svelte';

	const dispatch = createEventDispatcher();

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
	export let onRoomSelect = null;
	export let isAdmin = false;

	let showRoomSelector = false;

	$: activeBooking = booking;

	const STATUS_CONFIG = {
		draft: { label: 'Chờ xác nhận', color: '#6366f1', bg: 'indigo' },
		pending: { label: 'Chờ duyệt', color: '#f59e0b', bg: 'amber' },
		approved: { label: 'Đã duyệt', color: '#10b981', bg: 'emerald' },
		rejected: { label: 'Từ chối', color: '#ef4444', bg: 'red' },
		cancelled: { label: 'Đã hủy', color: '#6b7280', bg: 'gray' },
		sent: { label: 'Đã gửi', color: '#3b82f6', bg: 'blue' }
	};

	const CATERING_OPTIONS = [
		{ id: 'tea-coffee', name: 'Trà + Cà phê + Bánh', price: 35000 },
		{ id: 'coffee', name: 'Cà phê + Bánh', price: 30000 },
		{ id: 'water', name: 'Nước suối', price: 10000 },
		{ id: 'buffet', name: 'Buffet Trưa', price: 150000 },
		{ id: 'lunch-box', name: 'Cơm hộp', price: 50000 },
		{ id: 'fruit', name: 'Trái cây', price: 25000 }
	];

	$: statusConfig = activeBooking
		? STATUS_CONFIG[activeBooking.status] || STATUS_CONFIG.pending
		: STATUS_CONFIG.pending;

	let adminNote = '';
	let invitees = '';
	let inviteesError = false;
	let selectedCatering = [];
	let cateringTotal = 0;
	let expandedSection = null;
	let rejectNoteError = false;

	// ── Admin-simulation state (visible to non-admin users) ──────────────────
	let autoSimulate = true;
	let simulationStarted = false;
	let cateringSimulationStarted = false;

	async function startAdminSimulation() {
		const delay = Math.floor(Math.random() * 5001) + 5000;
		await new Promise((r) => setTimeout(r, delay));
		const willApprove = Math.random() > 0.2;
		const mockNote = willApprove
			? 'Đã xem xét và phê duyệt yêu cầu đặt phòng.'
			: 'Thời gian yêu cầu bị trùng lịch. Vui lòng chọn khung giờ khác.';
		adminNote = mockNote;
		if (onAddNote) onAddNote(activeBooking.id, mockNote);
		if (willApprove) { if (onApprove) onApprove(activeBooking.id); }
		else { if (onReject) onReject(activeBooking.id); }
	}

	async function startCateringSimulation() {
		const delay = Math.floor(Math.random() * 5001) + 5000;
		await new Promise((r) => setTimeout(r, delay));
		if (onApproveCatering) onApproveCatering(activeBooking.id);
	}

	// Reactive simulation triggers
	$: if (!isAdmin && autoSimulate && activeBooking?.status === 'pending' && !simulationStarted) {
		simulationStarted = true;
		startAdminSimulation();
	}
	$: if (!isAdmin && autoSimulate && activeBooking?.catering?.status === 'pending' && !cateringSimulationStarted) {
		cateringSimulationStarted = true;
		startCateringSimulation();
	}

	function handleAdminReject() {
		if (!adminNote.trim()) { rejectNoteError = true; return; }
		rejectNoteError = false;
		if (onReject) onReject(activeBooking.id);
	}

	function handleCateringReject() {
		if (!adminNote.trim()) { rejectNoteError = true; return; }
		rejectNoteError = false;
		if (onRejectCatering) onRejectCatering(activeBooking.id);
	}

	function formatDate(dateStr) {
		if (!dateStr) return 'Chưa có ngày';
		try {
			const [year, month, day] = dateStr.split('-');
			return `${day}/${month}/${year}`;
		} catch {
			return dateStr || 'Chưa có ngày';
		}
	}

	function formatTime(timeStr) {
		if (!timeStr) return '--:--';
		return timeStr;
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

	function recalcTotal() {
		cateringTotal = selectedCatering.reduce((sum, c) => sum + c.price * (c.quantity || 1), 0);
	}

	function toggleCatering(item) {
		const idx = selectedCatering.findIndex((c) => c.id === item.id);
		if (idx >= 0) {
			selectedCatering = selectedCatering.filter((c) => c.id !== item.id);
		} else {
			selectedCatering = [...selectedCatering, { ...item, quantity: 1 }];
		}
		recalcTotal();
	}

	function changeQuantity(itemId, delta) {
		selectedCatering = selectedCatering.map((c) =>
			c.id === itemId ? { ...c, quantity: Math.max(1, (c.quantity || 1) + delta) } : c
		);
		recalcTotal();
	}

	function validateInvitees() {
		if (!invitees.trim()) { inviteesError = false; return; }
		const emails = invitees.split(',').map((e) => e.trim()).filter(Boolean);
		const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		inviteesError = emails.some((e) => !emailRe.test(e));
	}

	function handleAddNote() {
		if (onAddNote && adminNote) onAddNote(activeBooking.id, adminNote);
	}

	function handleOrderCatering() {
		if (onOrderCatering) onOrderCatering(activeBooking.id, selectedCatering, cateringTotal);
		toast.success('Đã đặt catering thành công!');
	}

	function handleSelectRoom() {
		showRoomSelector = !showRoomSelector;
	}

	function handleRoomSelected(event) {
		const { room } = event.detail;
		const roomFields = {
			room_name: room.name,
			room_code: room.id,
			room_building: room.building,
			room_floor: room.floor,
			location: room.location,
			address: room.address,
			capacity: room.capacity,
			room_equipment: room.equipment
		};
		activeBooking = { ...activeBooking, ...roomFields };
		// Propagate room change to parent so parent's activeBooking stays in sync
		if (onRoomSelect) onRoomSelect(activeBooking.id, roomFields);
		showRoomSelector = false;
	}

	function handleRoomListClose() {
		showRoomSelector = false;
	}

	const EQUIPMENT_VI = {
		projector: 'Máy chiếu',
		tv: 'Tivi',
		video_conf: 'Họp video',
		phone: 'Điện thoại',
		whiteboard: 'Bảng trắng',
		ac: 'Điều hòa',
		whiteboard_mark: 'Bút bảng',
		sound: 'Hệ thống âm thanh',
		mic: 'Micro',
		laptop: 'Laptop',
		water: 'Nước uống'
	};

	const LOCATION_NAMES = {
		HN: 'Hà Nội',
		HCM: 'TP.HCM',
		DN: 'Đà Nẵng'
	};

	function translateEquipment(eq) {
		return EQUIPMENT_VI[eq] || eq;
	}

	function getLocationDisplay(code, building) {
		const city = LOCATION_NAMES[code] || code || '—';
		return building ? `${city} / ${building}` : city;
	}

	onMount(() => {
		if (activeBooking?.catering?.items) {
			selectedCatering = activeBooking.catering.items;
			cateringTotal = activeBooking.catering.total || 0;
		}
		if (activeBooking?.admin_note) adminNote = activeBooking.admin_note;
	});
</script>

{#if activeBooking}
	<div class="meeting-card" in:fly={{ y: 20, duration: 400 }}>
		<!-- Header -->
		<div class="card-header">
			<div class="header-content">
				<div class="company-brand">
					<svg class="cmc-logo" viewBox="0 0 24 24" fill="currentColor">
						<path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
					</svg>
					<span class="company-name">CMC Global</span>
				</div>
				<div class="header-top">
					<span class="section-tag">BOOKING REQUEST</span>
					<span
						class="status-badge"
						style="background: {statusConfig.color}20; color: {statusConfig.color}; border-color: {statusConfig.color}40"
					>
						{statusConfig.label}
					</span>
				</div>
				<div class="meeting-title-main">{activeBooking.title || 'Cuộc họp'}</div>
				<div class="requester-info">
					<span class="requester-label">Người đặt:</span>
					<span class="requester-name">{activeBooking.requester || '—'}</span>
				</div>
			</div>
			<div class="header-avatar">
				<div class="avatar-circle">
					{getInitials(activeBooking.approver?.name)}
				</div>
			</div>
		</div>

		<!-- Main Content -->
		<div class="card-body">
			{#if showRoomSelector}
				<RoomList
					embedded={true}
					booking={activeBooking}
					locked={activeBooking?.status !== "draft"}
					on:select={handleRoomSelected}
					on:close={handleRoomListClose}
				/>
			{:else}
				<div class="info-row">
					<div class="info-box">
						<div class="info-icon">
							<svg
								width="18"
								height="18"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							>
								<rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
								<line x1="16" y1="2" x2="16" y2="6"></line>
								<line x1="8" y1="2" x2="8" y2="6"></line>
								<line x1="3" y1="10" x2="21" y2="10"></line>
							</svg>
						</div>
						<div class="info-text">
							<div class="info-label">Ngày</div>
							<div class="info-value">{formatDate(activeBooking.date)}</div>
						</div>
					</div>

					<div class="info-box">
						<div class="info-icon">
							<svg
								width="18"
								height="18"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							>
								<circle cx="12" cy="12" r="10"></circle>
								<polyline points="12 6 12 12 16 14"></polyline>
							</svg>
						</div>
						<div class="info-text">
							<div class="info-label">Giờ</div>
							<div class="info-value">
								{formatTime(activeBooking.start_time)} - {formatTime(activeBooking.end_time)}
							</div>
						</div>
					</div>

					<div class="info-box">
						<div class="info-icon">
							<svg
								width="18"
								height="18"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							>
								<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
								<circle cx="9" cy="7" r="4"></circle>
								<path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
								<path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
							</svg>
						</div>
						<div class="info-text">
							<div class="info-label">Sức chứa</div>
							<div class="info-value">{activeBooking.capacity || '—'} người</div>
						</div>
					</div>
				</div>

				<!-- Location -->
				<div class="location-row">
					<div class="location-item">
						<span class="location-label">Khu vực</span>
						<span class="location-value">{getLocationDisplay(activeBooking.location, activeBooking.room_building)}</span>
					</div>
					<div class="location-divider"></div>
					<div class="location-item room-item">
						<span class="location-label">Phòng</span>
						<span class="location-value">{activeBooking.room_name || 'Chưa chọn'}</span>
						{#if activeBooking.status === "draft"}
						<button class="select-room-btn-small" on:click={handleSelectRoom}>
							<svg
								width="12"
								height="12"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							>
								<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
								<polyline points="9 22 9 12 15 12 15 22"></polyline>
							</svg>
						</button>
						{/if}
					</div>
					<div class="location-divider"></div>
					<div class="location-item">
						<span class="location-label">Tầng</span>
						<span class="location-value">Tầng {activeBooking.room_floor || '—'}</span>
					</div>
				</div>

				<!-- Equipment -->
				<div class="section">
					<div class="section-header">
						<span class="section-title">Thiết bị</span>
					</div>
					<div class="equipment-tags">
						{#if activeBooking.room_equipment?.length}
							{#each activeBooking.room_equipment as eq}
								<span class="tag">{translateEquipment(eq)}</span>
							{/each}
						{:else}
							<span class="no-equipment">Không cần thiết bị</span>
						{/if}
					</div>
				</div>

				<!-- Catering -->
				<div class="section">
					<div
						class="section-header"
						on:click={() => (expandedSection = expandedSection === 'catering' ? null : 'catering')}
					>
						<span class="section-title">Catering</span>
						<svg
							class="expand-icon {expandedSection === 'catering' ? 'expanded' : ''}"
							width="16"
							height="16"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
						>
							<polyline points="6 9 12 15 18 9"></polyline>
						</svg>
					</div>
					{#if expandedSection === 'catering'}
						<div class="catering-grid" transition:fly={{ y: -10, duration: 200 }}>
							{#each CATERING_OPTIONS as item}
								{@const isSelected = selectedCatering.some((c) => c.id === item.id)}
								{@const qty = selectedCatering.find((c) => c.id === item.id)?.quantity ?? 1}
								<button
									class="catering-btn {isSelected ? 'selected' : ''}"
									on:click={() => toggleCatering(item)}
								>
									<span class="check-icon">{isSelected ? '●' : '○'}</span>
									<span class="item-name">{item.name}</span>
									{#if isSelected}
										<div class="qty-stepper" on:click|stopPropagation>
											<button class="qty-btn" on:click={() => changeQuantity(item.id, -1)}>−</button>
											<span class="qty-val">{qty}</span>
											<button class="qty-btn" on:click={() => changeQuantity(item.id, 1)}>+</button>
										</div>
									{:else}
										<span class="item-price">{item.price.toLocaleString()} VNĐ</span>
									{/if}
								</button>
							{/each}
						</div>
						{#if selectedCatering.length > 0}
							<div class="catering-footer">
								<span>Tổng: <strong>{cateringTotal.toLocaleString()} VNĐ</strong></span>
								<button class="order-btn" on:click={handleOrderCatering}>Đặt</button>
							</div>
						{/if}
					{/if}
				</div>

				<!-- Invitees (visible to all users) -->
				<div class="section">
					<div class="section-header">
						<span class="section-title">Người tham dự</span>
					</div>
					<input
						type="text"
						class="invitees-input {inviteesError ? 'input-error' : ''}"
						placeholder="email1@cmcglobal.vn, email2@cmcglobal.vn"
						bind:value={invitees}
						on:blur={validateInvitees}
						disabled={activeBooking.status === 'sent'}
					/>
					{#if inviteesError}
						<div class="note-error">Email không hợp lệ. Vui lòng kiểm tra lại.</div>
					{/if}
				</div>

				<!-- Admin Note (visible to admin role only) -->
				{#if isAdmin}
				<div class="section">
					<div class="section-header">
						<span class="section-title">Ghi chú từ Admin</span>
					</div>
					<textarea
						class="note-input"
						placeholder="Thêm ghi chú cho admin..."
						bind:value={adminNote}
						on:blur={handleAddNote}
					></textarea>
				</div>
				{/if}

				<!-- Workflow -->
				<div class="section workflow-section">
					<div class="section-header">
						<span class="section-title">Approval Workflow</span>
					</div>
					{#if !isAdmin}
						<div class="sim-toggle-row">
							<span class="sim-toggle-label">🤖 Mô phỏng phê duyệt Admin</span>
							<label class="toggle-switch">
								<input type="checkbox" bind:checked={autoSimulate} />
								<span class="toggle-track" class:active={autoSimulate}>
									<span class="toggle-thumb"></span>
								</span>
							</label>
						</div>
					{/if}

					<div class="workflow-steps">
						<!-- Step 1 -->
						<div class="workflow-step completed">
							<div class="step-marker">
								<svg
									width="14"
									height="14"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="3"
								>
									<polyline points="20 6 9 17 4 12"></polyline>
								</svg>
							</div>
							<div class="step-info">
								<div class="step-name">Book Request</div>
								<div class="step-time">
									{formatDate(activeBooking.date)}
									{activeBooking.start_time}
								</div>
							</div>
						</div>

						<!-- Step 2 -->
						<div class="workflow-step {activeBooking.status === 'draft' ? 'active' : activeBooking.status === 'cancelled' ? 'rejected' : 'completed'}">
							<div class="step-marker {activeBooking.status === 'draft' ? 'pulse' : ''}">
								{#if activeBooking.status === 'cancelled'}
									<svg
										width="14"
										height="14"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="3"
									>
										<line x1="18" y1="6" x2="6" y2="18"></line>
										<line x1="6" y1="6" x2="18" y2="18"></line>
									</svg>
								{:else if activeBooking.status !== 'draft'}
									<svg
										width="14"
										height="14"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="3"
									>
										<polyline points="20 6 9 17 4 12"></polyline>
									</svg>
								{:else}
									2
								{/if}
							</div>
							<div class="step-info">
								<div class="step-name">Xác nhận từ người đặt</div>
								{#if activeBooking.status === 'draft'}
									<div class="step-actions">
										<button
											class="action-btn confirm"
											on:click={() => onConfirm && onConfirm(activeBooking.id)}>Xác nhận</button
										>
										<button
											class="action-btn reject"
											on:click={() => onCancel && onCancel(activeBooking.id)}>Từ chối</button
										>
									</div>
								{:else if activeBooking.status === 'cancelled'}
									<div class="step-time reject-hint">Đã từ chối — Nhập lại thông tin trong chat để đặt phòng mới</div>
								{:else}
									<div class="step-time">Đã xác nhận</div>
								{/if}
							</div>
						</div>

						<!-- Step 3 -->
						<div
							class="workflow-step {activeBooking.status === 'pending'
								? 'active'
								: activeBooking.status === 'approved' || activeBooking.status === 'sent'
									? 'completed'
									: 'pending'}"
						>
							<div class="step-marker {activeBooking.status === 'pending' ? 'pulse' : ''}">
								{#if activeBooking.status === 'approved' || activeBooking.status === 'sent'}
									<svg
										width="14"
										height="14"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="3"
									>
										<polyline points="20 6 9 17 4 12"></polyline>
									</svg>
								{:else if activeBooking.status === 'rejected'}
									<svg
										width="14"
										height="14"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="3"
									>
										<line x1="18" y1="6" x2="6" y2="18"></line>
										<line x1="6" y1="6" x2="18" y2="18"></line>
									</svg>
								{:else}
									3
								{/if}
							</div>
							<div class="step-info">
								<div class="step-name">Admin Approval</div>
								{#if activeBooking.status === 'pending'}
									<div class="step-assignee">
										<span class="mini-avatar">{getInitials(activeBooking.approver?.name)}</span>
										<span>{activeBooking.approver?.name}</span>
									</div>
									{#if isAdmin}
									<div class="step-actions">
										<button
											class="action-btn approve"
											on:click={() => onApprove && onApprove(activeBooking.id)}>Duyệt</button
										>
										<button
											class="action-btn reject"
											on:click={handleAdminReject}>Từ chối</button
										>
									</div>
									{#if rejectNoteError}
										<div class="note-error">Vui lòng thêm ghi chú lý do từ chối ở trên</div>
									{/if}
									{:else}
									<div class="sim-processing">
										<div class="sim-spinner"></div>
										<span>{autoSimulate ? 'Đang xử lý... Admin sẽ phản hồi trong vài giây' : 'Đang chờ Admin phê duyệt...'}</span>
									</div>
									{/if}
								{:else}
									<div class="step-time">
										{activeBooking.status === 'approved' || activeBooking.status === 'sent'
											? 'Đã duyệt'
											: activeBooking.status === 'rejected'
												? 'Đã từ chối'
												: 'Đang chờ'}
									</div>
								{/if}
							</div>
						</div>

						<!-- Step 4 -->
						<div
							class="workflow-step {activeBooking.catering?.status === 'pending'
								? 'active'
								: activeBooking.catering?.status === 'approved'
									? 'completed'
									: 'pending'}"
						>
							<div
								class="step-marker {activeBooking.catering?.status === 'pending' ? 'pulse' : ''}"
							>
								{#if activeBooking.catering?.status === 'approved'}
									<svg
										width="14"
										height="14"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="3"
									>
										<polyline points="20 6 9 17 4 12"></polyline>
									</svg>
								{:else}
									4
								{/if}
							</div>
							<div class="step-info">
								<div class="step-name">Catering Approval</div>
								{#if activeBooking.catering?.status === 'pending'}
									{#if isAdmin}
									<div class="step-actions">
										<button
											class="action-btn approve"
											on:click={() => onApproveCatering && onApproveCatering(activeBooking.id)}
											>Duyệt</button
										>
										<button
											class="action-btn reject"
											on:click={handleCateringReject}
											>Từ chối</button
										>
									</div>
									{#if rejectNoteError}
										<div class="note-error">Vui lòng thêm ghi chú lý do từ chối ở trên</div>
									{/if}
									{:else}
									<div class="sim-processing">
										<div class="sim-spinner"></div>
										<span>{autoSimulate ? 'Đang xử lý catering... Sẽ phản hồi trong vài giây' : 'Đang chờ duyệt catering...'}</span>
									</div>
									{/if}
								{:else}
									<div class="step-time">
										{activeBooking.catering?.status === 'approved' ? 'Đã duyệt' : 'Không có catering'}
									</div>
								{/if}
							</div>
						</div>

						<!-- Step 5 -->
						<div class="workflow-step {activeBooking.status === 'sent' ? 'completed' : 'pending'}">
							<div class="step-marker {activeBooking.status === 'sent' ? '' : 'pulse'}">
								{#if activeBooking.status === 'sent'}
									<svg
										width="14"
										height="14"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="3"
									>
										<polyline points="20 6 9 17 4 12"></polyline>
									</svg>
								{:else}
									5
								{/if}
							</div>
							<div class="step-info">
								<div class="step-name">Send Calendar Invite</div>
								{#if activeBooking.status === 'sent'}
									<div class="step-time">Sent successfully</div>
								{:else if activeBooking.status === 'approved'}
									<button
										class="action-btn send"
										on:click={() => onSendCalendar && onSendCalendar(activeBooking.id, invitees)}
										>Send Invite</button
									>
								{:else}
									<div class="step-time">Waiting for approval</div>
								{/if}
							</div>
						</div>
					</div>
				</div>

				<!-- Email Confirmation -->
				{#if activeBooking.status === 'sent' || activeBooking.email_sent}
					<div class="email-box" in:fade={{ duration: 300 }}>
						<div class="email-success-icon">
							<svg
								width="24"
								height="24"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							>
								<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
								<polyline points="22 4 12 14.01 9 11.01"></polyline>
							</svg>
						</div>
						<div class="email-content">
							<div class="email-title">Calendar Invite Sent</div>
							<div class="email-recipients">
								{#if activeBooking.email_details?.sent_to}
									{#each activeBooking.email_details.sent_to as recipient}
										<div class="recipient">• {recipient.email} ({recipient.type})</div>
									{/each}
								{:else}
									<div class="recipient">
										• {activeBooking.requester || 'user@cmcglobal.vn'} (người đặt)
									</div>
									{#if activeBooking.invitees}
										{#each (typeof activeBooking.invitees === 'string'
											? activeBooking.invitees.split(',').map((e) => e.trim()).filter(Boolean)
											: activeBooking.invitees) as inv}
											<div class="recipient">• {inv} (người tham dự)</div>
										{/each}
									{/if}
								{/if}
							</div>
							{#if activeBooking.email_details?.meeting_details}
								<div class="meeting-preview">
									<div class="preview-item">
										{activeBooking.email_details.meeting_details.title}
									</div>
									<div class="preview-item">
										{activeBooking.email_details.meeting_details.date} • {activeBooking
											.email_details.meeting_details.time}
									</div>
									<div class="preview-item">
										{activeBooking.email_details.meeting_details.room} - {activeBooking
											.email_details.meeting_details.location}
									</div>
								</div>
							{/if}
						</div>
					</div>
				{/if}
			{/if}
		</div>
	</div>
{/if}

<style>
	.meeting-card {
		background: linear-gradient(
			145deg,
			rgba(255, 255, 255, 0.95) 0%,
			rgba(248, 250, 252, 0.95) 100%
		);
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
		position: relative;
		font-family:
			'Century Gothic',
			'Trebuchet MS',
			'Segoe UI',
			-apple-system,
			BlinkMacSystemFont,
			sans-serif;
		margin: 0;
	}

	/* ── Admin simulation toggle ── */
	.sim-toggle-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 8px 12px;
		background: linear-gradient(135deg, #f0f4ff 0%, #e8f0fe 100%);
		border: 1px solid #c7d7fe;
		border-radius: 10px;
		margin-bottom: 14px;
	}

	.sim-toggle-label {
		font-size: 11px;
		color: #4f46e5;
		font-weight: 600;
		letter-spacing: 0.3px;
	}

	.toggle-switch {
		position: relative;
		display: inline-block;
		width: 36px;
		height: 20px;
		cursor: pointer;
		flex-shrink: 0;
	}

	.toggle-switch input {
		opacity: 0;
		width: 0;
		height: 0;
		position: absolute;
	}

	.toggle-track {
		position: absolute;
		inset: 0;
		background: #cbd5e1;
		border-radius: 10px;
		transition: background 0.2s;
	}

	.toggle-track.active {
		background: #6366f1;
	}

	.toggle-thumb {
		position: absolute;
		width: 14px;
		height: 14px;
		background: white;
		border-radius: 50%;
		top: 3px;
		left: 3px;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
		transition: transform 0.2s;
	}

	.toggle-track.active .toggle-thumb {
		transform: translateX(16px);
	}

	/* ── Simulation processing indicator ── */
	.sim-processing {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 8px;
		font-size: 12px;
		color: #6366f1;
		font-style: italic;
	}

	.sim-spinner {
		width: 14px;
		height: 14px;
		border: 2px solid #e0e7ff;
		border-top-color: #6366f1;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
		flex-shrink: 0;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.card-header {
		background: linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #6366f1 100%);
		padding: 24px;
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		position: relative;
		overflow: hidden;
	}

	.card-header::before {
		content: '';
		position: absolute;
		top: -50%;
		right: -20%;
		width: 200px;
		height: 200px;
		background: radial-gradient(circle, rgba(255, 255, 255, 0.15) 0%, transparent 70%);
		border-radius: 50%;
	}

	.card-header::after {
		content: '';
		position: absolute;
		bottom: -30%;
		left: -10%;
		width: 150px;
		height: 150px;
		background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
		border-radius: 50%;
	}

	.header-content {
		position: relative;
		z-index: 1;
	}

	.company-brand {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 12px;
	}

	.cmc-logo {
		width: 24px;
		height: 24px;
		color: #ffffff;
	}

	.company-name {
		font-size: 14px;
		font-weight: 700;
		color: #ffffff;
		letter-spacing: 0.5px;
	}

	.requester-info {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-top: 8px;
		font-size: 12px;
	}

	.requester-label {
		color: rgba(255, 255, 255, 0.7);
	}

	.requester-name {
		font-weight: 600;
		color: #ffffff;
	}

	.header-top {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 8px;
	}

	.section-tag {
		font-size: 10px;
		font-weight: 700;
		color: rgba(255, 255, 255, 0.6);
		letter-spacing: 1.5px;
	}

	.status-badge {
		padding: 4px 10px;
		border-radius: 20px;
		font-size: 11px;
		font-weight: 600;
		border: 1px solid;
	}

	.meeting-title-main {
		font-size: 20px;
		font-weight: 700;
		color: white;
		margin-bottom: 4px;
		line-height: 1.3;
	}

	.header-avatar {
		position: relative;
		z-index: 1;
	}

	.avatar-circle {
		width: 48px;
		height: 48px;
		border-radius: 14px;
		background: rgba(255, 255, 255, 0.2);
		backdrop-filter: blur(10px);
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 16px;
		font-weight: 700;
		color: white;
		border: 2px solid rgba(255, 255, 255, 0.3);
	}

	.card-body {
		padding: 20px;
	}

	.info-row {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 12px;
		margin-bottom: 16px;
	}

	.info-box {
		background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
		border: 1px solid #e2e8f0;
		border-radius: 14px;
		padding: 14px;
		display: flex;
		align-items: center;
		gap: 10px;
		transition: all 0.2s;
	}

	.info-box:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
	}

	.info-icon {
		width: 36px;
		height: 36px;
		border-radius: 10px;
		background: white;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #3b82f6;
		box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
	}

	.info-text {
		flex: 1;
	}

	.info-label {
		font-size: 10px;
		color: #94a3b8;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		font-weight: 600;
	}

	.info-value {
		font-size: 13px;
		font-weight: 600;
		color: #1e293b;
	}

	.select-room-btn-container {
		padding: 0 20px;
	}

	.select-room-btn-small {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		background: #3b82f6;
		color: white;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		transition: all 0.2s;
		margin-left: 4px;
		vertical-align: middle;
	}

	.select-room-btn-small:hover {
		background: #1d4ed8;
		transform: scale(1.1);
	}

	.room-item {
		position: relative;
	}

	.location-row {
		display: flex;
		align-items: center;
		background: #f8fafc;
		border-radius: 12px;
		padding: 12px 16px;
		margin-bottom: 16px;
	}

	.location-item {
		flex: 1;
		text-align: center;
	}

	.location-label {
		display: block;
		font-size: 10px;
		color: #94a3b8;
		margin-bottom: 2px;
	}

	.location-value {
		font-size: 13px;
		font-weight: 600;
		color: #1e293b;
	}

	.location-divider {
		width: 1px;
		height: 30px;
		background: #e2e8f0;
	}

	.section {
		margin-bottom: 16px;
	}

	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10px;
		cursor: pointer;
	}

	.section-title {
		font-size: 11px;
		font-weight: 700;
		color: #64748b;
		text-transform: uppercase;
		letter-spacing: 1px;
	}

	.expand-icon {
		color: #94a3b8;
		transition: transform 0.2s;
	}

	.expand-icon.expanded {
		transform: rotate(180deg);
	}

	.equipment-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.tag {
		background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
		color: #475569;
		padding: 6px 12px;
		border-radius: 8px;
		font-size: 12px;
		font-weight: 500;
		border: 1px solid #e2e8f0;
	}

	.no-equipment {
		color: #94a3b8;
		font-size: 12px;
		font-style: italic;
	}

	.catering-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 8px;
		margin-bottom: 12px;
	}

	.catering-btn {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		background: #f8fafc;
		border: 1px solid #e2e8f0;
		border-radius: 10px;
		cursor: pointer;
		transition: all 0.2s;
		text-align: left;
	}

	.catering-btn:hover {
		background: #f1f5f9;
		border-color: #cbd5e1;
	}

	.catering-btn.selected {
		background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
		border-color: #3b82f6;
	}

	.check-icon {
		color: #3b82f6;
		font-size: 14px;
	}

	.item-name {
		flex: 1;
		font-size: 12px;
		color: #1e293b;
	}

	.item-price {
		font-size: 11px;
		color: #64748b;
	}

	.qty-stepper {
		display: flex;
		align-items: center;
		gap: 4px;
		margin-left: auto;
	}

	.qty-btn {
		width: 20px;
		height: 20px;
		border-radius: 4px;
		border: 1px solid #cbd5e1;
		background: white;
		font-size: 14px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		line-height: 1;
		color: #1e293b;
	}

	.qty-btn:hover {
		background: #f1f5f9;
		border-color: #3b82f6;
	}

	.qty-val {
		font-size: 12px;
		font-weight: 600;
		min-width: 18px;
		text-align: center;
		color: #1e293b;
	}

	.invitees-input {
		width: 100%;
		padding: 10px 12px;
		border: 1px solid #e2e8f0;
		border-radius: 10px;
		font-size: 13px;
		font-family: inherit;
		background: #f8fafc;
		transition: all 0.2s;
		box-sizing: border-box;
	}

	.invitees-input:focus {
		outline: none;
		border-color: #3b82f6;
		background: white;
		box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
	}

	.invitees-input.input-error {
		border-color: #ef4444;
	}

	.invitees-input:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.catering-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 12px;
		border-top: 1px solid #e2e8f0;
	}

	.order-btn {
		padding: 8px 20px;
		background: #1e40af;
		color: white;
		border: none;
		border-radius: 8px;
		font-size: 12px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.order-btn:hover {
		background: #1e3a8a;
		transform: translateY(-1px);
	}

	.note-input {
		width: 100%;
		min-height: 70px;
		padding: 12px;
		border: 1px solid #e2e8f0;
		border-radius: 10px;
		font-size: 13px;
		resize: none;
		font-family: inherit;
		background: #f8fafc;
		transition: all 0.2s;
	}

	.note-input:focus {
		outline: none;
		border-color: #3b82f6;
		background: white;
		box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
	}

	.workflow-section {
		background: linear-gradient(135deg, #fafbfc 0%, #f8fafc 100%);
		border-radius: 14px;
		padding: 16px;
		border: 1px solid #e2e8f0;
	}

	.workflow-steps {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.workflow-step {
		display: flex;
		gap: 14px;
		padding: 12px 0;
		position: relative;
	}

	.workflow-step:not(:last-child)::after {
		content: '';
		position: absolute;
		left: 15px;
		top: 48px;
		bottom: -12px;
		width: 2px;
		background: #e2e8f0;
	}

	.workflow-step.completed::after {
		background: #10b981;
	}

	.workflow-step.active::after {
		background: linear-gradient(to bottom, #10b981 50%, #e2e8f0 50%);
	}

	.step-marker {
		width: 32px;
		height: 32px;
		border-radius: 10px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 12px;
		font-weight: 700;
		flex-shrink: 0;
		background: #e2e8f0;
		color: #64748b;
	}

	.workflow-step.completed .step-marker {
		background: #10b981;
		color: white;
	}

	.workflow-step.active .step-marker {
		background: #f59e0b;
		color: white;
	}

	.workflow-step.active .step-marker.pulse {
		animation: pulse 2s infinite;
	}

	.step-info {
		flex: 1;
	}

	.step-name {
		font-size: 13px;
		font-weight: 600;
		color: #1e293b;
	}

	.step-time {
		font-size: 11px;
		color: #64748b;
		margin-top: 2px;
	}

	.step-assignee {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-top: 6px;
		font-size: 12px;
		color: #475569;
	}

	.mini-avatar {
		width: 20px;
		height: 20px;
		border-radius: 6px;
		background: #1e40af;
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 8px;
		font-weight: 700;
	}

	.step-actions {
		display: flex;
		gap: 8px;
		margin-top: 8px;
	}

	.action-btn {
		padding: 6px 14px;
		border-radius: 8px;
		font-size: 11px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
		border: none;
	}

	.action-btn.confirm,
	.action-btn.approve,
	.action-btn.send {
		background: #1e40af;
		color: white;
	}

	.action-btn.confirm:hover,
	.action-btn.approve:hover,
	.action-btn.send:hover {
		background: #1e3a8a;
		transform: translateY(-1px);
	}

	.action-btn.cancel,
	.action-btn.reject {
		background: white;
		color: #64748b;
		border: 1px solid #e2e8f0;
	}

	.action-btn.cancel:hover,
	.action-btn.reject:hover {
		background: #f8fafc;
	}

	.email-box {
		display: flex;
		gap: 14px;
		background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
		border: 1px solid #bbf7d0;
		border-radius: 14px;
		padding: 16px;
		margin-top: 16px;
	}

	.email-success-icon {
		width: 48px;
		height: 48px;
		background: #10b981;
		border-radius: 12px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: white;
		flex-shrink: 0;
	}

	.email-title {
		font-size: 14px;
		font-weight: 600;
		color: #166534;
		margin-bottom: 4px;
	}

	.email-recipients {
		font-size: 12px;
		color: #15803d;
	}

	.workflow-step.rejected .step-marker {
		background: #ef4444;
		color: white;
	}

	.note-error {
		font-size: 11px;
		color: #ef4444;
		margin-top: 6px;
	}

	.reject-hint {
		font-size: 11px;
		color: #94a3b8;
		font-style: italic;
		margin-top: 2px;
	}

	@keyframes pulse {
		0%,
		100% {
			box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4);
		}
		50% {
			box-shadow: 0 0 0 8px rgba(245, 158, 11, 0);
		}
	}
</style>
