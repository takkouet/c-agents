<script lang="ts">
	import { onMount } from 'svelte';

	const PROXY = 'http://localhost:4000';

	type Booking = Record<string, any>;
	type Room = Record<string, any>;
	type Admin = Record<string, any>;
	type CateringOption = Record<string, any>;

	let activeTab: 'bookings' | 'rooms' | 'admins' | 'catering' = 'bookings';

	// ── Bookings tab ──
	let bookings: Booking[] = [];
	let bookingFilter = 'all';
	let expandedBookingId: string | null = null;
	let bookingsLoading = false;
	let bookingsError = '';
	let bookingEditDraft: Record<string, any> = {};
	let bookingEditSaving = false;

	// ── Reference data ──
	let rooms: Room[] = [];
	let admins: Admin[] = [];
	let catering: CateringOption[] = [];
	let refLoading = false;

	// ── Room edit state ──
	let editingRoomId: string | null = null;
	let editRoomDraft: Room = {};
	let isAddingRoom = false;
	let addRoomDraft: Room = {};

	// ── Admin edit state ──
	let editingAdminId: string | null = null;
	let editAdminDraft: Admin = {};
	let isAddingAdmin = false;
	let addAdminDraft: Admin = {};

	// ── Catering edit state ──
	let editingCateringId: string | null = null;
	let editCateringDraft: CateringOption = {};
	let isAddingCatering = false;
	let addCateringDraft: CateringOption = {};

	// ── Toast ──
	let toast = '';
	let toastType: 'success' | 'error' = 'success';
	function showToast(msg: string, type: 'success' | 'error' = 'success') {
		toast = msg;
		toastType = type;
		setTimeout(() => { toast = ''; }, 3000);
	}

	const STATUS_COLORS: Record<string, string> = {
		draft: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
		pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
		approved: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
		rejected: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
		cancelled: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
		sent: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
	};

	const STATUS_LABELS: Record<string, string> = {
		draft: 'Chờ xác nhận',
		pending: 'Chờ duyệt',
		approved: 'Đã duyệt',
		rejected: 'Từ chối',
		cancelled: 'Đã hủy',
		sent: 'Đã gửi'
	};

	// ── Fetch ──
	async function fetchBookings() {
		bookingsLoading = true;
		bookingsError = '';
		try {
			const res = await fetch(`${PROXY}/api/bookings`);
			bookings = res.ok ? await res.json() : [];
		} catch {
			bookingsError = 'Không thể kết nối proxy (localhost:4000)';
		} finally {
			bookingsLoading = false;
		}
	}

	async function fetchReferenceData() {
		refLoading = true;
		const safeJson = async (url: string): Promise<any[]> => {
			try {
				const r = await fetch(url);
				return r.ok ? r.json() : [];
			} catch {
				return [];
			}
		};
		// departments is fetched but not stored (unused in UI for now)
		const [r, a, , c] = await Promise.all([
			safeJson(`${PROXY}/api/meeting-rooms`),
			safeJson(`${PROXY}/api/admins`),
			safeJson(`${PROXY}/api/departments`),
			safeJson(`${PROXY}/api/catering-options`)
		]);
		rooms = r; admins = a; catering = c;
		refLoading = false;
	}

	$: filteredBookings =
		bookingFilter === 'all' ? bookings : bookings.filter((b) => b.status === bookingFilter);

	function formatDate(d: string) {
		if (!d) return '—';
		const [y, m, day] = d.split('-');
		return `${day}/${m}/${y}`;
	}

	// ── Booking actions ──
	function openBooking(b: Booking) {
		const isOpening = expandedBookingId !== b.id;
		expandedBookingId = isOpening ? b.id : null;
		if (isOpening) bookingEditDraft = { status: b.status, admin_note: b.admin_note || '' };
	}

	async function saveBookingEdit(bookingId: string) {
		bookingEditSaving = true;
		try {
			const res = await fetch(`${PROXY}/api/bookings/${bookingId}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(bookingEditDraft)
			});
			if (res.ok) {
				await fetchBookings();
				showToast('Booking updated');
			} else {
				showToast('Update failed', 'error');
			}
		} catch {
			showToast('Connection error', 'error');
		} finally {
			bookingEditSaving = false;
		}
	}

	async function deleteBooking(bookingId: string) {
		if (!confirm('Delete this booking? This cannot be undone.')) return;
		try {
			const res = await fetch(`${PROXY}/api/bookings/${bookingId}`, { method: 'DELETE' });
			if (res.ok) {
				expandedBookingId = null;
				await fetchBookings();
				showToast('Booking deleted');
			} else {
				showToast('Delete failed', 'error');
			}
		} catch {
			showToast('Connection error', 'error');
		}
	}

	// ── Room CRUD ──
	function startEditRoom(r: Room) {
		editingRoomId = r.id;
		editRoomDraft = { ...r, equipment: (r.equipment ?? []).join(', ') };
	}
	function cancelEditRoom() { editingRoomId = null; editRoomDraft = {}; }

	function parseEquipment(raw: string): string[] {
		return (raw || '').split(',').map((s: string) => s.trim()).filter(Boolean);
	}

	async function saveRoom() {
		const payload = { ...editRoomDraft, equipment: parseEquipment(editRoomDraft.equipment as string) };
		try {
			const res = await fetch(`${PROXY}/api/meeting-rooms/${editingRoomId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});
			if (res.ok) { cancelEditRoom(); await fetchReferenceData(); showToast('Room updated'); }
			else showToast('Update failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	async function deleteRoom(roomId: string) {
		if (!confirm('Delete this room?')) return;
		try {
			const res = await fetch(`${PROXY}/api/meeting-rooms/${roomId}`, { method: 'DELETE' });
			if (res.ok) { await fetchReferenceData(); showToast('Room deleted'); }
			else showToast('Delete failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	async function addRoom() {
		const payload = { ...addRoomDraft, equipment: parseEquipment(addRoomDraft.equipment as string) };
		try {
			const res = await fetch(`${PROXY}/api/meeting-rooms`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});
			if (res.ok) {
				isAddingRoom = false; addRoomDraft = {};
				await fetchReferenceData(); showToast('Room added');
			} else showToast('Add failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	// ── Admin CRUD ──
	function startEditAdmin(a: Admin) { editingAdminId = a.id; editAdminDraft = { ...a }; }
	function cancelEditAdmin() { editingAdminId = null; editAdminDraft = {}; }

	async function saveAdmin() {
		try {
			const res = await fetch(`${PROXY}/api/admins/${editingAdminId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(editAdminDraft)
			});
			if (res.ok) { cancelEditAdmin(); await fetchReferenceData(); showToast('Admin updated'); }
			else showToast('Update failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	async function deleteAdmin(adminId: string) {
		if (!confirm('Delete this admin?')) return;
		try {
			const res = await fetch(`${PROXY}/api/admins/${adminId}`, { method: 'DELETE' });
			if (res.ok) { await fetchReferenceData(); showToast('Admin deleted'); }
			else showToast('Delete failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	async function addAdmin() {
		try {
			const res = await fetch(`${PROXY}/api/admins`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(addAdminDraft)
			});
			if (res.ok) {
				isAddingAdmin = false; addAdminDraft = {};
				await fetchReferenceData(); showToast('Admin added');
			} else showToast('Add failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	// ── Catering CRUD ──
	function startEditCatering(c: CateringOption) { editingCateringId = c.id; editCateringDraft = { ...c }; }
	function cancelEditCatering() { editingCateringId = null; editCateringDraft = {}; }

	async function saveCatering() {
		const payload = { ...editCateringDraft, per_person: Boolean(editCateringDraft.per_person) };
		try {
			const res = await fetch(`${PROXY}/api/catering-options/${editingCateringId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});
			if (res.ok) { cancelEditCatering(); await fetchReferenceData(); showToast('Option updated'); }
			else showToast('Update failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	async function deleteCatering(id: string) {
		if (!confirm('Delete this catering option?')) return;
		try {
			const res = await fetch(`${PROXY}/api/catering-options/${id}`, { method: 'DELETE' });
			if (res.ok) { await fetchReferenceData(); showToast('Option deleted'); }
			else showToast('Delete failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	async function addCatering() {
		const payload = { ...addCateringDraft, per_person: Boolean(addCateringDraft.per_person) };
		try {
			const res = await fetch(`${PROXY}/api/catering-options`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});
			if (res.ok) {
				isAddingCatering = false; addCateringDraft = {};
				await fetchReferenceData(); showToast('Option added');
			} else showToast('Add failed', 'error');
		} catch { showToast('Connection error', 'error'); }
	}

	onMount(() => {
		fetchBookings();
		fetchReferenceData();
	});
</script>

<!-- Toast -->
{#if toast}
	<div class="fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg text-sm font-medium shadow-lg transition-all
		{toastType === 'success'
			? 'bg-emerald-500 text-white'
			: 'bg-red-500 text-white'}">
		{toast}
	</div>
{/if}

<div class="w-full max-w-6xl mx-auto px-4 py-6">
	<!-- Header -->
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-xl font-semibold text-gray-800 dark:text-gray-100">Booking Management</h1>
	</div>

	<!-- Tabs -->
	<div class="flex gap-1 text-sm font-medium border-b border-gray-200 dark:border-gray-700 mb-6">
		{#each [['bookings', 'Bookings'], ['rooms', 'Meeting Rooms'], ['admins', 'Admins'], ['catering', 'Catering']] as [tab, label]}
			<button
				class="px-4 py-2 border-b-2 transition-colors {activeTab === tab
					? 'border-blue-500 text-blue-600 dark:text-blue-400'
					: 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'}"
				on:click={() => { activeTab = tab as typeof activeTab; }}
			>
				{label}
				{#if tab === 'bookings' && bookings.length > 0}
					<span class="ml-1 text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-1.5 py-0.5 rounded-full">{bookings.length}</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- ── Bookings Tab ── -->
	{#if activeTab === 'bookings'}
		<div class="flex items-center gap-3 mb-4">
			<select
				class="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-1.5 bg-white dark:bg-gray-850 text-gray-700 dark:text-gray-300"
				bind:value={bookingFilter}
			>
				<option value="all">All statuses</option>
				{#each Object.entries(STATUS_LABELS) as [val, lbl]}
					<option value={val}>{lbl}</option>
				{/each}
			</select>
			<button
				class="text-sm px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 transition-colors"
				on:click={fetchBookings}
			>
				↺ Refresh
			</button>
			{#if bookingsError}
				<span class="text-xs text-red-500">{bookingsError}</span>
			{/if}
		</div>

		{#if bookingsLoading}
			<div class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">Loading...</div>
		{:else if filteredBookings.length === 0}
			<div class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">No bookings found.</div>
		{:else}
			<div class="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">
						<tr>
							<th class="px-4 py-3 text-left">ID</th>
							<th class="px-4 py-3 text-left">Title</th>
							<th class="px-4 py-3 text-left">Client</th>
							<th class="px-4 py-3 text-left">Date</th>
							<th class="px-4 py-3 text-left">Room</th>
							<th class="px-4 py-3 text-left">Requester</th>
							<th class="px-4 py-3 text-left">Status</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100 dark:divide-gray-700">
						{#each filteredBookings as b}
							<tr
								class="hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
								on:click={() => openBooking(b)}
							>
								<td class="px-4 py-3 font-mono text-xs text-gray-500 dark:text-gray-400 max-w-[120px] truncate">{b.id}</td>
								<td class="px-4 py-3 font-medium text-gray-800 dark:text-gray-100">{b.title || '—'}</td>
								<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{b.client || '—'}</td>
								<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{formatDate(b.date)}</td>
								<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{b.room_name || '—'}</td>
								<td class="px-4 py-3 text-gray-600 dark:text-gray-300 max-w-[160px] truncate">{b.requester || '—'}</td>
								<td class="px-4 py-3">
									<span class="px-2 py-0.5 rounded-full text-xs font-medium {STATUS_COLORS[b.status] ?? STATUS_COLORS.draft}">
										{STATUS_LABELS[b.status] ?? b.status}
									</span>
								</td>
							</tr>
							{#if expandedBookingId === b.id}
								<tr class="bg-gray-50 dark:bg-gray-800/30">
									<td colspan="7" class="px-4 py-4">
										<!-- Details -->
										<div class="grid grid-cols-2 gap-x-8 gap-y-2 text-xs text-gray-600 dark:text-gray-300 mb-4">
											{#if b.client}
												<div class="col-span-2"><span class="font-medium text-gray-800 dark:text-gray-100">Client:</span> <span class="ml-1">{b.client}</span></div>
											{/if}
											<div><span class="font-medium text-gray-800 dark:text-gray-100">Time:</span> {b.start_time || '—'} – {b.end_time || '—'}</div>
											<div><span class="font-medium text-gray-800 dark:text-gray-100">Capacity:</span> {b.capacity ?? '—'} người</div>
											<div><span class="font-medium text-gray-800 dark:text-gray-100">Location:</span> {b.location || '—'}</div>
											<div><span class="font-medium text-gray-800 dark:text-gray-100">Building:</span> {b.room_building || '—'} (Tầng {b.room_floor ?? '—'})</div>
											<div><span class="font-medium text-gray-800 dark:text-gray-100">Approver:</span> {b.approver?.name ?? '—'} &lt;{b.approver?.email ?? ''}&gt;</div>
											<div><span class="font-medium text-gray-800 dark:text-gray-100">Email sent:</span> {b.email_sent ? 'Yes' : 'No'}</div>
											{#if b.admin_note}
												<div class="col-span-2"><span class="font-medium text-gray-800 dark:text-gray-100">Admin note:</span> {b.admin_note}</div>
											{/if}
											{#if b.invitees?.length > 0}
												<div class="col-span-2">
													<span class="font-medium text-gray-800 dark:text-gray-100">Attendees:</span>
													<span class="ml-1">{b.invitees.join(', ')}</span>
												</div>
											{/if}
											{#if b.catering}
												<div class="col-span-2">
													<div class="flex items-center gap-2 flex-wrap">
														<span class="font-medium text-gray-800 dark:text-gray-100">Catering:</span>
														<span class="px-1.5 py-0.5 rounded text-xs font-medium {STATUS_COLORS[b.catering.status] ?? 'bg-gray-100 text-gray-600'}">
															{STATUS_LABELS[b.catering.status] ?? b.catering.status}
														</span>
														<span>— {b.catering.total?.toLocaleString() ?? 0} VNĐ</span>
													</div>
													{#if b.catering.items?.length > 0}
														<ul class="mt-1 ml-2 space-y-0.5 list-none">
															{#each b.catering.items as item}
																<li class="flex items-center gap-1">
																	<span class="text-gray-400">•</span>
																	<span>{item.icon ?? ''} {item.name}</span>
																	<span class="text-gray-400">—</span>
																	<span>{item.price?.toLocaleString() ?? '?'} VNĐ</span>
																	{#if item.per_person}<span class="text-gray-400 text-xs">(per person)</span>{/if}
																</li>
															{/each}
														</ul>
													{/if}
												</div>
											{/if}
										</div>

										<!-- Admin Controls -->
										<div class="border-t border-gray-200 dark:border-gray-600 pt-3">
											<div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Admin Controls</div>
											<div class="flex flex-wrap items-end gap-3">
												<div class="flex flex-col gap-1">
													<label class="text-xs text-gray-500 dark:text-gray-400">Status</label>
													<select
														class="text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-850 text-gray-700 dark:text-gray-300"
														bind:value={bookingEditDraft.status}
														on:click|stopPropagation
													>
														{#each Object.entries(STATUS_LABELS) as [val, lbl]}
															<option value={val}>{lbl}</option>
														{/each}
													</select>
												</div>
												<div class="flex flex-col gap-1 flex-1 min-w-[200px]">
													<label class="text-xs text-gray-500 dark:text-gray-400">Admin Note</label>
													<input
														type="text"
														class="text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-850 text-gray-700 dark:text-gray-300"
														placeholder="Add a note..."
														bind:value={bookingEditDraft.admin_note}
														on:click|stopPropagation
													/>
												</div>
												<button
													class="text-sm px-4 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors disabled:opacity-50"
													disabled={bookingEditSaving}
													on:click|stopPropagation={() => saveBookingEdit(b.id)}
												>
													{bookingEditSaving ? 'Saving…' : 'Save'}
												</button>
												<button
													class="text-sm px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 text-red-600 dark:text-red-400 font-medium transition-colors"
													on:click|stopPropagation={() => deleteBooking(b.id)}
												>
													Delete
												</button>
											</div>
										</div>
									</td>
								</tr>
							{/if}
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- ── Meeting Rooms Tab ── -->
	{#if activeTab === 'rooms'}
		<div class="flex items-center justify-between mb-4">
			<span class="text-sm text-gray-500 dark:text-gray-400">{rooms.length} room{rooms.length !== 1 ? 's' : ''}</span>
			<button
				class="text-sm px-3 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors"
				on:click={() => { isAddingRoom = true; addRoomDraft = { available: true }; cancelEditRoom(); }}
			>
				+ Add Room
			</button>
		</div>

		{#if refLoading}
			<div class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">Loading...</div>
		{:else}
			<div class="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">
						<tr>
							<th class="px-4 py-3 text-left">Name</th>
							<th class="px-4 py-3 text-left">Office</th>
							<th class="px-4 py-3 text-left">Building</th>
							<th class="px-4 py-3 text-left">Floor</th>
							<th class="px-4 py-3 text-left">Capacity</th>
							<th class="px-4 py-3 text-left">Equipment</th>
							<th class="px-4 py-3 text-left">Actions</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100 dark:divide-gray-700">
						<!-- Add form row -->
						{#if isAddingRoom}
							<tr class="bg-green-50 dark:bg-green-900/10">
								<td colspan="7" class="px-4 py-3">
									<div class="grid grid-cols-3 gap-2 mb-2">
										<div><label class="text-xs text-gray-500">Name</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addRoomDraft.name} placeholder="Orchid" /></div>
										<div><label class="text-xs text-gray-500">Office Code</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addRoomDraft.code} placeholder="HN" /></div>
										<div><label class="text-xs text-gray-500">Building</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addRoomDraft.building} /></div>
										<div><label class="text-xs text-gray-500">Floor</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="number" bind:value={addRoomDraft.floor} /></div>
										<div><label class="text-xs text-gray-500">Capacity</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="number" bind:value={addRoomDraft.capacity} /></div>
										<div><label class="text-xs text-gray-500">Equipment (comma-separated)</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addRoomDraft.equipment} placeholder="Projector, Whiteboard" /></div>
									</div>
									<div class="flex items-center gap-3">
										<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300">
											<input type="checkbox" bind:checked={addRoomDraft.available} />
											Available
										</label>
										<button class="text-sm px-4 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors" on:click={addRoom}>Add Room</button>
										<button class="text-sm px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium transition-colors" on:click={() => { isAddingRoom = false; addRoomDraft = {}; }}>Cancel</button>
									</div>
								</td>
							</tr>
						{/if}

						{#each rooms as r}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
								{#if editingRoomId === r.id}
									<td colspan="7" class="px-4 py-3 bg-blue-50 dark:bg-blue-900/10">
										<div class="grid grid-cols-3 gap-2 mb-2">
											<div><label class="text-xs text-gray-500">Name</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editRoomDraft.name} /></div>
											<div><label class="text-xs text-gray-500">Office Code</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editRoomDraft.code} /></div>
											<div><label class="text-xs text-gray-500">Building</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editRoomDraft.building} /></div>
											<div><label class="text-xs text-gray-500">Floor</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="number" bind:value={editRoomDraft.floor} /></div>
											<div><label class="text-xs text-gray-500">Capacity</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="number" bind:value={editRoomDraft.capacity} /></div>
											<div><label class="text-xs text-gray-500">Equipment (comma-separated)</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editRoomDraft.equipment} /></div>
										</div>
										<div class="flex items-center gap-3">
											<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300">
												<input type="checkbox" bind:checked={editRoomDraft.available} />
												Available
											</label>
											<button class="text-sm px-4 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors" on:click={saveRoom}>Save</button>
											<button class="text-sm px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium transition-colors" on:click={cancelEditRoom}>Cancel</button>
										</div>
									</td>
								{:else}
									<td class="px-4 py-3 font-medium text-gray-800 dark:text-gray-100">
										{r.name}
										{#if !r.available}
											<span class="ml-1 text-xs bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400 px-1.5 py-0.5 rounded">Unavailable</span>
										{/if}
									</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{r.code}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{r.building || '—'}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{r.floor ?? '—'}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{r.capacity ?? '—'} người</td>
									<td class="px-4 py-3">
										<div class="flex flex-wrap gap-1">
											{#each (r.equipment ?? []) as eq}
												<span class="px-1.5 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{eq}</span>
											{/each}
										</div>
									</td>
									<td class="px-4 py-3">
										<div class="flex gap-2">
											<button class="text-xs px-2.5 py-1 rounded-md text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 font-medium transition-colors" on:click={() => startEditRoom(r)}>Edit</button>
											<button class="text-xs px-2.5 py-1 rounded-md text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 font-medium transition-colors" on:click={() => deleteRoom(r.id)}>Delete</button>
										</div>
									</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- ── Admins Tab ── -->
	{#if activeTab === 'admins'}
		<div class="flex items-center justify-between mb-4">
			<span class="text-sm text-gray-500 dark:text-gray-400">{admins.length} admin{admins.length !== 1 ? 's' : ''}</span>
			<button
				class="text-sm px-3 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors"
				on:click={() => { isAddingAdmin = true; addAdminDraft = {}; cancelEditAdmin(); }}
			>
				+ Add Admin
			</button>
		</div>

		{#if refLoading}
			<div class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">Loading...</div>
		{:else}
			<div class="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">
						<tr>
							<th class="px-4 py-3 text-left">Name</th>
							<th class="px-4 py-3 text-left">Email</th>
							<th class="px-4 py-3 text-left">Role</th>
							<th class="px-4 py-3 text-left">Office</th>
							<th class="px-4 py-3 text-left">Floor</th>
							<th class="px-4 py-3 text-left">Actions</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100 dark:divide-gray-700">
						<!-- Add form row -->
						{#if isAddingAdmin}
							<tr class="bg-green-50 dark:bg-green-900/10">
								<td colspan="6" class="px-4 py-3">
									<div class="grid grid-cols-3 gap-2 mb-2">
										<div><label class="text-xs text-gray-500">Name</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addAdminDraft.name} /></div>
										<div><label class="text-xs text-gray-500">Email</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="email" bind:value={addAdminDraft.email} /></div>
										<div><label class="text-xs text-gray-500">Role</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addAdminDraft.role} /></div>
										<div><label class="text-xs text-gray-500">Office Code</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addAdminDraft.department_code} placeholder="HN" /></div>
										<div><label class="text-xs text-gray-500">Floor</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="number" bind:value={addAdminDraft.floor} /></div>
									</div>
									<div class="flex gap-2">
										<button class="text-sm px-4 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors" on:click={addAdmin}>Add Admin</button>
										<button class="text-sm px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium transition-colors" on:click={() => { isAddingAdmin = false; addAdminDraft = {}; }}>Cancel</button>
									</div>
								</td>
							</tr>
						{/if}

						{#each admins as a}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
								{#if editingAdminId === a.id}
									<td colspan="6" class="px-4 py-3 bg-blue-50 dark:bg-blue-900/10">
										<div class="grid grid-cols-3 gap-2 mb-2">
											<div><label class="text-xs text-gray-500">Name</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editAdminDraft.name} /></div>
											<div><label class="text-xs text-gray-500">Email</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="email" bind:value={editAdminDraft.email} /></div>
											<div><label class="text-xs text-gray-500">Role</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editAdminDraft.role} /></div>
											<div><label class="text-xs text-gray-500">Office Code</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editAdminDraft.department_code} /></div>
											<div><label class="text-xs text-gray-500">Floor</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="number" bind:value={editAdminDraft.floor} /></div>
										</div>
										<div class="flex gap-2">
											<button class="text-sm px-4 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors" on:click={saveAdmin}>Save</button>
											<button class="text-sm px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium transition-colors" on:click={cancelEditAdmin}>Cancel</button>
										</div>
									</td>
								{:else}
									<td class="px-4 py-3 font-medium text-gray-800 dark:text-gray-100">{a.name}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300 font-mono text-xs">{a.email}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{a.role || '—'}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{a.department_code}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{a.floor ?? '—'}</td>
									<td class="px-4 py-3">
										<div class="flex gap-2">
											<button class="text-xs px-2.5 py-1 rounded-md text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 font-medium transition-colors" on:click={() => startEditAdmin(a)}>Edit</button>
											<button class="text-xs px-2.5 py-1 rounded-md text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 font-medium transition-colors" on:click={() => deleteAdmin(a.id)}>Delete</button>
										</div>
									</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- ── Catering Tab ── -->
	{#if activeTab === 'catering'}
		<div class="flex items-center justify-between mb-4">
			<span class="text-sm text-gray-500 dark:text-gray-400">{catering.length} option{catering.length !== 1 ? 's' : ''}</span>
			<button
				class="text-sm px-3 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors"
				on:click={() => { isAddingCatering = true; addCateringDraft = { per_person: true }; cancelEditCatering(); }}
			>
				+ Add Option
			</button>
		</div>

		{#if refLoading}
			<div class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">Loading...</div>
		{:else}
			<div class="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
				<table class="w-full text-sm">
					<thead class="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-xs uppercase tracking-wide">
						<tr>
							<th class="px-4 py-3 text-left">Icon</th>
							<th class="px-4 py-3 text-left">Name</th>
							<th class="px-4 py-3 text-left">Price (VNĐ)</th>
							<th class="px-4 py-3 text-left">Per person</th>
							<th class="px-4 py-3 text-left">Actions</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100 dark:divide-gray-700">
						<!-- Add form row -->
						{#if isAddingCatering}
							<tr class="bg-green-50 dark:bg-green-900/10">
								<td colspan="5" class="px-4 py-3">
									<div class="grid grid-cols-4 gap-2 mb-2">
										<div><label class="text-xs text-gray-500">Icon (emoji)</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addCateringDraft.icon} placeholder="☕" /></div>
										<div><label class="text-xs text-gray-500">Name</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={addCateringDraft.name} /></div>
										<div><label class="text-xs text-gray-500">Price</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="number" bind:value={addCateringDraft.price} /></div>
										<div class="flex flex-col justify-end">
											<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 mb-1.5">
												<input type="checkbox" bind:checked={addCateringDraft.per_person} />
												Per person
											</label>
										</div>
									</div>
									<div class="flex gap-2">
										<button class="text-sm px-4 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors" on:click={addCatering}>Add Option</button>
										<button class="text-sm px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium transition-colors" on:click={() => { isAddingCatering = false; addCateringDraft = {}; }}>Cancel</button>
									</div>
								</td>
							</tr>
						{/if}

						{#each catering as c}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
								{#if editingCateringId === c.id}
									<td colspan="5" class="px-4 py-3 bg-blue-50 dark:bg-blue-900/10">
										<div class="grid grid-cols-4 gap-2 mb-2">
											<div><label class="text-xs text-gray-500">Icon (emoji)</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editCateringDraft.icon} /></div>
											<div><label class="text-xs text-gray-500">Name</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" bind:value={editCateringDraft.name} /></div>
											<div><label class="text-xs text-gray-500">Price</label><input class="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-400" type="number" bind:value={editCateringDraft.price} /></div>
											<div class="flex flex-col justify-end">
												<label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 mb-1.5">
													<input type="checkbox" bind:checked={editCateringDraft.per_person} />
													Per person
												</label>
											</div>
										</div>
										<div class="flex gap-2">
											<button class="text-sm px-4 py-1.5 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium transition-colors" on:click={saveCatering}>Save</button>
											<button class="text-sm px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-medium transition-colors" on:click={cancelEditCatering}>Cancel</button>
										</div>
									</td>
								{:else}
									<td class="px-4 py-3 text-lg">{c.icon || ''}</td>
									<td class="px-4 py-3 font-medium text-gray-800 dark:text-gray-100">{c.name}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{c.price?.toLocaleString() ?? '—'}</td>
									<td class="px-4 py-3 text-gray-600 dark:text-gray-300">{c.per_person ? 'Yes' : 'No'}</td>
									<td class="px-4 py-3">
										<div class="flex gap-2">
											<button class="text-xs px-2.5 py-1 rounded-md text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 font-medium transition-colors" on:click={() => startEditCatering(c)}>Edit</button>
											<button class="text-xs px-2.5 py-1 rounded-md text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 font-medium transition-colors" on:click={() => deleteCatering(c.id)}>Delete</button>
										</div>
									</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>

