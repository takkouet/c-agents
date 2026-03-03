<script>
	import { onMount, createEventDispatcher, tick } from 'svelte';
	import { fade, fly } from 'svelte/transition';
	import 'leaflet/dist/leaflet.css';

	const dispatch = createEventDispatcher();

	export let show = false;
	export let booking = null;
	export let embedded = false;
	export let locked = false;

	const MOCK_ROOMS = [
		{
			id: 'sunflower',
			name: 'Sun Flower',
			location: 'HCM',
			building: 'Vietcombank Tower',
			address: 'Quận 1, TP.HCM',
			lat: 10.7769,
			lng: 106.7009,
			floor: 3,
			capacity: 20,
			equipment: ['projector', 'tv', 'video_conf', 'phone'],
			image: 'https://images.unsplash.com/photo-1497366216548-37526070297c?w=400'
		},
		{
			id: 'blossom',
			name: 'Blossom',
			location: 'HCM',
			building: 'Saigon Trade Center',
			address: 'Quận 3, TP.HCM',
			lat: 10.7869,
			lng: 106.6881,
			floor: 5,
			capacity: 15,
			equipment: ['projector', 'whiteboard', 'ac'],
			image: 'https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=400'
		},
		{
			id: 'daisy',
			name: 'Daisy',
			location: 'HCM',
			building: 'Crescent Office Tower',
			address: 'Quận 7, TP.HCM',
			lat: 10.7469,
			lng: 106.695,
			floor: 2,
			capacity: 10,
			equipment: ['tv', 'video_conf', 'ac'],
			image: 'https://images.unsplash.com/photo-1503423571797-2d2bb372094a?w=400'
		},
		{
			id: 'rose',
			name: 'Rose',
			location: 'HCM',
			building: 'CMC HCM Office',
			address: 'Quận 10, TP.HCM',
			lat: 10.7929,
			lng: 106.6831,
			floor: 4,
			capacity: 8,
			equipment: ['projector', 'whiteboard', 'sound'],
			image: 'https://images.unsplash.com/photo-1524758631624-e2822e304c36?w=400'
		},
		{
			id: 'lotus',
			name: 'Lotus',
			location: 'HN',
			building: 'CMC Tower Hà Nội',
			address: 'Quận Cầu Giấy, Hà Nội',
			lat: 21.0285,
			lng: 105.8542,
			floor: 6,
			capacity: 25,
			equipment: ['projector', 'tv', 'video_conf', 'phone', 'mic'],
			image: 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=400'
		},
		{
			id: 'orchid',
			name: 'Orchid',
			location: 'HN',
			building: 'Lotte Center Hanoi',
			address: 'Quận Ba Đình, Hà Nội',
			lat: 21.0355,
			lng: 105.8085,
			floor: 8,
			capacity: 18,
			equipment: ['projector', 'tv', 'video_conf', 'ac'],
			image: 'https://images.unsplash.com/photo-1497215842964-222b430dc094?w=400'
		},
		{
			id: 'jasmine',
			name: 'Jasmine',
			location: 'DN',
			building: 'CMC Global Đà Nẵng',
			address: 'Quận Hải Châu, Đà Nẵng',
			lat: 16.0544,
			lng: 108.2022,
			floor: 3,
			capacity: 12,
			equipment: ['projector', 'tv', 'video_conf'],
			image: 'https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=400'
		},
		{
			id: 'tulip',
			name: 'Tulip',
			location: 'DN',
			building: 'Blooming Tower',
			address: 'Quận Ngũ Hành Sơn, Đà Nẵng',
			lat: 16.0013,
			lng: 108.2635,
			floor: 5,
			capacity: 16,
			equipment: ['projector', 'whiteboard', 'ac', 'sound'],
			image: 'https://images.unsplash.com/photo-1571624436279-b272aff752b5?w=400'
		}
	];

	const EQUIPMENT_VI = {
		projector: 'Máy chiếu',
		tv: 'Tivi',
		video_conf: 'Họp video',
		phone: 'Điện thoại',
		whiteboard: 'Bảng trắng',
		ac: 'Điều hòa',
		sound: 'Âm thanh',
		mic: 'Micro'
	};

	const LOCATIONS = [
		{ id: 'all', name: 'Tất cả' },
		{ id: 'HCM', name: 'TP. Hồ Chí Minh' },
		{ id: 'HN', name: 'Hà Nội' },
		{ id: 'DN', name: 'Đà Nẵng' }
	];

	let selectedLocation = 'all';
	let selectedRoom = null;
	let mapContainer;
	let map;
	let markers = [];
	let occupiedRooms = [];

	async function fetchOccupied() {
		const { date, start_time, end_time, id } = booking ?? {};
		if (!date || !start_time || !end_time) {
			occupiedRooms = [];
			return;
		}
		try {
			const params = new URLSearchParams({ date, start_time, end_time });
			if (id) params.set('exclude_id', id);
			console.log('[RoomList] fetchOccupied →', params.toString());
			const res = await fetch(`http://localhost:4000/api/availability?${params}`);
			const data = await res.json();
			console.log('[RoomList] availability response →', data);
			if (res.ok) occupiedRooms = data.occupied ?? [];
		} catch (e) {
			console.error('[RoomList] fetchOccupied error →', e);
			occupiedRooms = [];
		}
	}

	$: if (booking?.date || booking?.start_time || booking?.end_time) fetchOccupied();

	$: filteredRooms =
		selectedLocation === 'all'
			? MOCK_ROOMS
			: MOCK_ROOMS.filter((r) => r.location === selectedLocation);

	// When locked, pre-select the already-confirmed room so the confirm-btn shows its name
	$: if (locked && booking?.room_code) {
		const found = MOCK_ROOMS.find((r) => r.id === booking.room_code);
		if (found) selectedRoom = found;
	}

	function translateEquipment(eq) {
		return EQUIPMENT_VI[eq] || eq;
	}

	function selectRoom(room) {
		selectedRoom = room;
		focusRoomOnMap(room);
	}

	function confirmRoom() {
		if (selectedRoom) {
			dispatch('select', { room: selectedRoom, booking: booking });
			close();
		}
	}

	function close() {
		selectedRoom = null;
		dispatch('close');
		if (!embedded) {
			show = false;
		}
	}

	function handleKeydown(e) {
		if (e.key === 'Escape') close();
	}

	function focusRoomOnMap(room) {
		if (map) {
			map.invalidateSize();
			map.setView([room.lat, room.lng], 15);
		}
	}

	onMount(async () => {
		if (typeof window !== 'undefined') {
			await import('leaflet');
			await import('leaflet/dist/leaflet.css');

			setTimeout(() => {
				if (mapContainer) {
					initMap();
				}
			}, 100);
		}
	});

	// Init map when modal is shown or in embedded mode
	$: if (embedded && !map && typeof window !== 'undefined') {
		waitForMapContainer();
	}

	async function waitForMapContainer() {
		let attempts = 0;
		while (!mapContainer && attempts < 10) {
			await new Promise((resolve) => setTimeout(resolve, 100));
			attempts++;
		}
		if (mapContainer) {
			initMap();
		}
	}

	async function initMap() {
		if (typeof window !== 'undefined' && mapContainer) {
			const L = await import('leaflet');
			await tick();

			if (!map && mapContainer) {
				map = L.map(mapContainer).setView([10.7769, 106.7009], 12);

				// Prevent Leaflet's internal focus() call from scrolling the page
				// when setView/panTo is triggered (Leaflet calls container.focus() without preventScroll).
				const _mapContainer = map.getContainer();
				_mapContainer.focus = function (opts) {
					HTMLElement.prototype.focus.call(this, { preventScroll: true });
				};

				L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
					attribution: '© OpenStreetMap'
				}).addTo(map);

				MOCK_ROOMS.forEach((room) => {
					const marker = L.marker([room.lat, room.lng]).addTo(map);
					marker.on('click', () => {
						selectRoom(room);
						scrollToRoomInList(room.id);
					});
					markers.push(marker);
				});
			}
		}
	}

	function scrollToRoomInList(roomId) {
		const element = document.querySelector(`[data-room-id="${roomId}"]`);
		const list = element?.closest('.room-list');
		if (element && list) {
			// Use getBoundingClientRect so the offset is always relative to the
			// viewport (and therefore the list), not the element's offsetParent.
			const elementRect = element.getBoundingClientRect();
			const listRect = list.getBoundingClientRect();
			const top =
				list.scrollTop +
				(elementRect.top - listRect.top) -
				list.clientHeight / 2 +
				element.clientHeight / 2;
			list.scrollTo({ top, behavior: 'smooth' });
		}
	}

	$: if (show && map && selectedRoom) {
		focusRoomOnMap(selectedRoom);
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if show || embedded}
	{#if embedded}
		<div class="room-selector-embedded">
			<div class="embedded-header">
				<div class="header-title">
					<svg
						width="24"
						height="24"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
						<polyline points="9 22 9 12 15 12 15 22"></polyline>
					</svg>
					<h2>Chọn phòng họp</h2>
				</div>
				<button class="close-btn" on:click={close}>
					<svg
						width="20"
						height="20"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>
			<div class="embedded-body">
				<div class="sidebar">
					<div class="filter-section">
						<label class="filter-label">Khu vực</label>
						<div class="location-tabs">
							{#each LOCATIONS as loc}
								<button
									class="location-tab {selectedLocation === loc.id ? 'active' : ''}"
									on:click={() => (selectedLocation = loc.id)}
								>
									{loc.name}
								</button>
							{/each}
						</div>
					</div>
					<div class="room-list">
						{#each filteredRooms as room}
							{@const occupied = occupiedRooms.includes(room.id)}
							<button
								class="room-card {selectedRoom?.id === room.id ? 'selected' : ''} {occupied ? 'occupied' : ''}"
								data-room-id={room.id}
								disabled={occupied}
								on:click={() => !occupied && selectRoom(room)}
							>
								<div class="room-image" style="background-image: url({room.image})">
									<span class="room-location-badge">{room.location}</span>
									{#if occupied}
										<span class="occupied-badge">Đã đặt</span>
									{:else if selectedRoom?.id === room.id}
										<span class="selected-check">✓</span>
									{/if}
								</div>
								<div class="room-info">
									<div class="room-name">{room.name}</div>
									<div class="room-address">{room.address}</div>
									<div class="room-details">
										<span>👥 {room.capacity} người</span>
										<span>🏢 Tầng {room.floor}</span>
									</div>
									<div class="room-equipment">
										{#each room.equipment.slice(0, 3) as eq}
											<span class="eq-tag">{translateEquipment(eq)}</span>
										{/each}
										{#if room.equipment.length > 3}
											<span class="eq-more">+{room.equipment.length - 3}</span>
										{/if}
									</div>
								</div>
							</button>
						{/each}
					</div>
					<div class="sidebar-footer">
						<button
							class="confirm-btn {locked || selectedRoom ? 'active' : 'disabled'}"
							disabled={locked || !selectedRoom}
							on:click={confirmRoom}
						>
							{#if locked && selectedRoom}
								<svg
									width="18"
									height="18"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2.5"
								>
									<rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
									<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
								</svg>
								Đã xác nhận: {selectedRoom.name}
							{:else if selectedRoom}
								<svg
									width="18"
									height="18"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2.5"
								>
									<polyline points="20 6 9 17 4 12"></polyline>
								</svg>
								Xác nhận: {selectedRoom.name}
							{:else}
								<svg
									width="18"
									height="18"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2"
								>
									<circle cx="12" cy="12" r="10"></circle>
									<line x1="12" y1="8" x2="12" y2="12"></line>
									<line x1="12" y1="16" x2="12.01" y2="16"></line>
								</svg>
								Chọn phòng để tiếp tục
							{/if}
						</button>
					</div>
				</div>
				<div class="map-area">
					<div bind:this={mapContainer} class="map"></div>
					{#if selectedRoom}
						<div class="room-preview-floating" transition:fly={{ y: 20, duration: 200 }}>
							<div class="preview-badge">Đã chọn</div>
							<div class="preview-content">
								<img src={selectedRoom.image} alt={selectedRoom.name} class="preview-image" />
								<div class="preview-info">
									<h3>{selectedRoom.name}</h3>
									<p>{selectedRoom.address}</p>
									<div class="preview-meta">
										<span>👥 {selectedRoom.capacity} người</span>
										<span>🏢 Tầng {selectedRoom.floor}</span>
									</div>
								</div>
							</div>
						</div>
					{/if}
				</div>
			</div>
		</div>
	{:else}
		<div class="modal-overlay" transition:fade={{ duration: 200 }} on:click={close}>
			<div
				class="modal-container"
				transition:fly={{ y: 20, duration: 300 }}
				on:click|stopPropagation
			>
				<div class="modal-header">
					<h2>Chọn phòng họp</h2>
					<button class="close-btn" on:click={close}>
						<svg
							width="24"
							height="24"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
						>
							<line x1="18" y1="6" x2="6" y2="18"></line>
							<line x1="6" y1="6" x2="18" y2="18"></line>
						</svg>
					</button>
				</div>

				<div class="modal-body">
					<div class="sidebar">
						<div class="filter-section">
							<label class="filter-label">Khu vực</label>
							<div class="location-tabs">
								{#each LOCATIONS as loc}
									<button
										class="location-tab {selectedLocation === loc.id ? 'active' : ''}"
										on:click={() => (selectedLocation = loc.id)}
									>
										{loc.name}
									</button>
								{/each}
							</div>
						</div>

						<div class="room-list">
							{#each filteredRooms as room}
								<button
									class="room-card {selectedRoom?.id === room.id ? 'selected' : ''}"
									on:click={() => selectRoom(room)}
								>
									<div class="room-image" style="background-image: url({room.image})">
										<span class="room-location-badge">{room.location}</span>
									</div>
									<div class="room-info">
										<div class="room-name">{room.name}</div>
										<div class="room-address">{room.address}</div>
										<div class="room-details">
											<span>👥 {room.capacity} người</span>
											<span>🏢 Tầng {room.floor}</span>
										</div>
										<div class="room-equipment">
											{#each room.equipment.slice(0, 4) as eq}
												<span class="eq-tag">{translateEquipment(eq)}</span>
											{/each}
											{#if room.equipment.length > 4}
												<span class="eq-more">+{room.equipment.length - 4}</span>
											{/if}
										</div>
									</div>
								</button>
							{/each}
						</div>
					</div>

					<div class="map-container">
						<div bind:this={mapContainer} class="map"></div>
						{#if selectedRoom}
							<div class="room-preview" transition:fly={{ y: 10, duration: 200 }}>
								<div class="preview-header">
									<img src={selectedRoom.image} alt={selectedRoom.name} class="preview-image" />
									<div class="preview-info">
										<h3>{selectedRoom.name}</h3>
										<p>{selectedRoom.address}</p>
									</div>
								</div>
								<div class="preview-details">
									<div class="detail-item">
										<span class="detail-label">Sức chứa</span>
										<span class="detail-value">{selectedRoom.capacity} người</span>
									</div>
									<div class="detail-item">
										<span class="detail-label">Tầng</span>
										<span class="detail-value">{selectedRoom.floor}</span>
									</div>
									<div class="detail-item">
										<span class="detail-label">Thiết bị</span>
										<span class="detail-value"
											>{selectedRoom.equipment.map((e) => translateEquipment(e)).join(', ')}</span
										>
									</div>
								</div>
								<button class="confirm-btn" on:click={confirmRoom}> Xác nhận chọn phòng </button>
							</div>
						{/if}
					</div>
				</div>
			</div>
		</div>
	{/if}
{/if}

<style>
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		backdrop-filter: blur(4px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 99999;
		padding: 20px;
	}

	.room-selector-embedded {
		display: flex;
		flex-direction: column;
		height: 100%;
		width: 100%;
		background: #f8fafc;
		border-radius: 16px;
		overflow: hidden;
		font-family:
			'Century Gothic',
			'Trebuchet MS',
			'Segoe UI',
			-apple-system,
			sans-serif;
	}

	.embedded-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px;
		background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
		color: white;
	}

	.header-title {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.header-title svg {
		opacity: 0.9;
	}

	.header-title h2 {
		font-size: 18px;
		font-weight: 700;
		margin: 0;
		letter-spacing: 0.3px;
		color: white;
	}

	.embedded-header .close-btn {
		width: 36px;
		height: 36px;
		border-radius: 10px;
		border: none;
		background: rgba(255, 255, 255, 0.15);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		color: white;
		transition: all 0.2s;
	}

	.embedded-header .close-btn:hover {
		background: rgba(255, 255, 255, 0.25);
		transform: scale(1.05);
	}

	.embedded-body {
		display: flex;
		flex: 1;
		min-height: 0;
		gap: 0;
		height: 420px;
	}

	.embedded-body .sidebar {
		width: 280px;
		min-width: 260px;
		background: white;
		border-right: 1px solid #e2e8f0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		box-shadow: 2px 0 10px rgba(0, 0, 0, 0.05);
	}

	.embedded-body .map-area {
		flex: 1;
		position: relative;
		display: flex;
		flex-direction: column;
	}

	.embedded-body .map {
		flex: 1;
		height: 100%;
		width: 100%;
	}

	.embedded-body .room-preview-floating {
		position: absolute;
		top: 16px;
		right: 16px;
		background: white;
		border-radius: 14px;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
		overflow: hidden;
		z-index: 1000;
		max-width: 320px;
	}

	.preview-badge {
		background: linear-gradient(135deg, #10b981 0%, #059669 100%);
		color: white;
		font-size: 10px;
		font-weight: 700;
		padding: 6px 12px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.preview-content {
		padding: 12px;
		display: flex;
		gap: 12px;
	}

	.preview-image {
		width: 80px;
		height: 60px;
		object-fit: cover;
		border-radius: 8px;
	}

	.preview-info h3 {
		font-size: 15px;
		font-weight: 700;
		color: #1e293b;
		margin: 0 0 4px 0;
	}

	.preview-info p {
		font-size: 11px;
		color: #64748b;
		margin: 0 0 6px 0;
	}

	.preview-meta {
		display: flex;
		gap: 10px;
		font-size: 10px;
		color: #475569;
	}

	.sidebar-footer {
		padding: 16px;
		background: white;
		border-top: 1px solid #e2e8f0;
	}

	.confirm-btn {
		width: 100%;
		padding: 14px 20px;
		border: none;
		border-radius: 12px;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.3s;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
	}

	.confirm-btn.disabled {
		background: #e2e8f0;
		color: #94a3b8;
		cursor: not-allowed;
	}

	.confirm-btn.active {
		background: linear-gradient(135deg, #10b981 0%, #059669 100%);
		color: white;
		box-shadow: 0 4px 15px rgba(16, 185, 129, 0.35);
	}

	.confirm-btn.active:hover {
		transform: translateY(-2px);
		box-shadow: 0 6px 20px rgba(16, 185, 129, 0.45);
	}

	.confirm-btn.active:disabled {
		cursor: not-allowed;
		opacity: 0.85;
		transform: none;
		box-shadow: 0 4px 15px rgba(16, 185, 129, 0.35);
	}

	.modal-container {
		background: white;
		border-radius: 20px;
		width: 95vw;
		height: 90vh;
		max-width: 1400px;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
		font-family: 'Century Gothic', 'Trebuchet MS', 'Segoe UI', sans-serif;
		position: relative;
		z-index: 100000;
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 20px 24px;
		border-bottom: 1px solid #e2e8f0;
	}

	.modal-header h2 {
		font-size: 20px;
		font-weight: 700;
		color: #1e293b;
		margin: 0;
	}

	.close-btn {
		width: 40px;
		height: 40px;
		border-radius: 12px;
		border: none;
		background: #f1f5f9;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #64748b;
		transition: all 0.2s;
	}

	.close-btn:hover {
		background: #e2e8f0;
		color: #1e293b;
	}

	.modal-body {
		display: flex;
		flex: 1;
		overflow: hidden;
	}

	.sidebar {
		width: 320px;
		border-right: 1px solid #e2e8f0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.filter-section {
		padding: 16px;
		border-bottom: 1px solid #e2e8f0;
		background: #f8fafc;
	}

	.filter-label {
		display: block;
		font-size: 11px;
		font-weight: 700;
		color: #64748b;
		margin-bottom: 10px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.location-tabs {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.location-tab {
		padding: 8px 14px;
		border-radius: 20px;
		border: 1px solid #e2e8f0;
		background: white;
		font-size: 12px;
		font-weight: 500;
		color: #64748b;
		cursor: pointer;
		transition: all 0.2s;
	}

	.location-tab:hover {
		border-color: #3b82f6;
		color: #3b82f6;
		background: #eff6ff;
	}

	.location-tab.active {
		background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
		border-color: #3b82f6;
		color: white;
		box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
	}

	.room-list {
		flex: 1;
		overflow-y: auto;
		padding: 12px;
		background: #f8fafc;
		max-height: 500px;
	}	

	.room-card {
		width: 100%;
		border: 2px solid transparent;
		border-radius: 12px;
		overflow: hidden;
		margin-bottom: 10px;
		cursor: pointer;
		background: white;
		transition: all 0.25s ease;
		text-align: left;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
	}

	.room-card:hover {
		border-color: #bfdbfe;
		box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
		transform: translateY(-1px);
	}

	.room-card.selected {
		border-color: #3b82f6;
		background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
		box-shadow: 0 4px 15px rgba(59, 130, 246, 0.25);
	}

	.room-card.occupied {
		opacity: 0.45;
		cursor: not-allowed;
		pointer-events: none;
	}

	.occupied-badge {
		position: absolute;
		top: 6px;
		right: 6px;
		background: rgba(220, 38, 38, 0.85);
		color: #fff;
		font-size: 10px;
		font-weight: 700;
		padding: 2px 7px;
		border-radius: 10px;
		letter-spacing: 0.2px;
		backdrop-filter: blur(4px);
	}

	.room-image {
		height: 70px;
		background-size: cover;
		background-position: center;
		position: relative;
	}

	.room-location-badge {
		position: absolute;
		top: 8px;
		left: 8px;
		padding: 4px 10px;
		background: rgba(30, 64, 175, 0.85);
		color: white;
		font-size: 9px;
		font-weight: 700;
		border-radius: 12px;
		text-transform: uppercase;
		letter-spacing: 0.3px;
		backdrop-filter: blur(4px);
	}

	.selected-check {
		position: absolute;
		top: 8px;
		right: 8px;
		width: 22px;
		height: 22px;
		background: #3b82f6;
		color: white;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 12px;
		font-weight: bold;
		box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
	}

	.room-info {
		padding: 10px 12px;
	}

	.room-name {
		font-size: 14px;
		font-weight: 700;
		color: #1e293b;
		margin-bottom: 3px;
	}

	.room-address {
		font-size: 11px;
		color: #64748b;
		margin-bottom: 6px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.room-details {
		display: flex;
		gap: 10px;
		font-size: 10px;
		color: #475569;
		margin-bottom: 6px;
	}

	.room-equipment {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
	}

	.eq-tag {
		padding: 3px 8px;
		background: #f1f5f9;
		color: #475569;
		font-size: 9px;
		font-weight: 500;
		border-radius: 6px;
	}

	.eq-more {
		padding: 3px 8px;
		background: #e2e8f0;
		color: #64748b;
		font-size: 9px;
		font-weight: 500;
		border-radius: 6px;
	}

	.map-container {
		flex: 1;
		position: relative;
		display: flex;
		flex-direction: column;
		min-height: 0;
	}

	.map {
		flex: 1;
		min-height: 400px;
		width: 100%;
	}

	.room-preview {
		background: white;
		border-top: 1px solid #e2e8f0;
		padding: 16px;
		max-height: 200px;
		overflow-y: auto;
	}

	.preview-header {
		display: flex;
		gap: 12px;
		margin-bottom: 12px;
	}

	.preview-image {
		width: 80px;
		height: 60px;
		object-fit: cover;
		border-radius: 10px;
	}

	.preview-info h3 {
		font-size: 16px;
		font-weight: 700;
		color: #1e293b;
		margin: 0 0 4px 0;
	}

	.preview-info p {
		font-size: 12px;
		color: #64748b;
		margin: 0;
	}

	.preview-details {
		display: flex;
		gap: 20px;
		margin-bottom: 12px;
		padding-bottom: 12px;
		border-bottom: 1px solid #e2e8f0;
	}

	.detail-item {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.detail-label {
		font-size: 10px;
		color: #94a3b8;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.detail-value {
		font-size: 12px;
		font-weight: 600;
		color: #1e293b;
	}

	.confirm-btn {
		width: 100%;
		padding: 12px;
		background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
		color: white;
		border: none;
		border-radius: 12px;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
		transition: all 0.2s;
	}

	.confirm-btn:hover {
		transform: translateY(-2px);
		box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
	}

	:global(.leaflet-popup-content-wrapper) {
		border-radius: 12px;
		box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15);
	}

	:global(.leaflet-popup-content) {
		margin: 12px 14px;
	}

	:global(.leaflet-control-zoom) {
		border: none !important;
		box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15) !important;
		border-radius: 10px !important;
		overflow: hidden;
	}

	:global(.leaflet-control-zoom a) {
		background: white !important;
		color: #3b82f6 !important;
		width: 36px !important;
		height: 36px !important;
		line-height: 36px !important;
		font-size: 18px !important;
	}

	:global(.leaflet-control-zoom a:hover) {
		background: #f1f5f9 !important;
	}
</style>
