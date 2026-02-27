<script>
	import { onMount } from 'svelte';

	export let bookings = [];
	export let onSelectDate = null;

	let currentDate = new Date();
	let currentMonth = currentDate.getMonth() + 1;
	let currentYear = currentDate.getFullYear();

	const MONTH_NAMES = [
		'Tháng 1',
		'Tháng 2',
		'Tháng 3',
		'Tháng 4',
		'Tháng 5',
		'Tháng 6',
		'Tháng 7',
		'Tháng 8',
		'Tháng 9',
		'Tháng 10',
		'Tháng 11',
		'Tháng 12'
	];

	const WEEKDAY_NAMES = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];

	$: daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
	$: firstDayOfMonth = new Date(currentYear, currentMonth - 1, 1).getDay();

	$: calendarDays = generateCalendarDays();

	function generateCalendarDays() {
		const days = [];

		// Add empty slots for days before the first day of month
		for (let i = 0; i < firstDayOfMonth; i++) {
			days.push({ day: null, date: null });
		}

		// Add days of the month
		for (let day = 1; day <= daysInMonth; day++) {
			const date = `${currentYear}-${String(currentMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
			const dayBookings = bookings.filter((b) => b.date === date);
			days.push({
				day,
				date,
				bookings: dayBookings,
				hasMeeting: dayBookings.length > 0,
				isToday: isToday(day)
			});
		}

		return days;
	}

	function isToday(day) {
		const today = new Date();
		return (
			day === today.getDate() &&
			currentMonth === today.getMonth() + 1 &&
			currentYear === today.getFullYear()
		);
	}

	function prevMonth() {
		if (currentMonth === 1) {
			currentMonth = 12;
			currentYear--;
		} else {
			currentMonth--;
		}
	}

	function nextMonth() {
		if (currentMonth === 12) {
			currentMonth = 1;
			currentYear++;
		} else {
			currentMonth++;
		}
	}

	function selectDay(dayObj) {
		if (onSelectDate && dayObj.date) {
			onSelectDate(dayObj.date, dayObj.bookings);
		}
	}

	function getStatusColor(status) {
		switch (status) {
			case 'pending':
				return 'bg-yellow-400';
			case 'approved':
				return 'bg-green-400';
			case 'rejected':
				return 'bg-red-400';
			case 'completed':
				return 'bg-blue-400';
			default:
				return 'bg-gray-400';
		}
	}
</script>

<div class="meeting-calendar bg-white rounded-lg shadow-sm border p-4">
	<!-- Header -->
	<div class="flex items-center justify-between mb-4">
		<button on:click={prevMonth} class="p-2 hover:bg-gray-100 rounded-lg transition"> ◀ </button>
		<h3 class="font-semibold text-lg text-gray-800">
			{MONTH_NAMES[currentMonth - 1]}
			{currentYear}
		</h3>
		<button on:click={nextMonth} class="p-2 hover:bg-gray-100 rounded-lg transition"> ▶ </button>
	</div>

	<!-- Weekday Headers -->
	<div class="grid grid-cols-7 gap-1 mb-2">
		{#each WEEKDAY_NAMES as weekday}
			<div class="text-center text-xs font-medium text-gray-500 py-2">
				{weekday}
			</div>
		{/each}
	</div>

	<!-- Calendar Grid -->
	<div class="grid grid-cols-7 gap-1">
		{#each calendarDays as dayObj}
			{#if dayObj.day === null}
				<div class="h-20"></div>
			{:else}
				<button
					on:click={() => selectDay(dayObj)}
					class="h-20 p-1 border rounded-lg transition flex flex-col
						{dayObj.isToday
						? 'border-blue-500 bg-blue-50'
						: 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'}
						{dayObj.hasMeeting ? 'bg-blue-50/50' : ''}"
				>
					<span class="text-sm font-medium {dayObj.isToday ? 'text-blue-600' : 'text-gray-700'}">
						{dayObj.day}
					</span>

					{#if dayObj.hasMeeting}
						<div class="flex-1 flex flex-col gap-0.5 mt-1 overflow-hidden">
							{#each dayObj.bookings.slice(0, 3) as booking}
								<div
									class="h-1.5 rounded-full {getStatusColor(booking.status)}"
									title={booking.title}
								></div>
							{/each}
							{#if dayObj.bookings.length > 3}
								<span class="text-xs text-gray-400">+{dayObj.bookings.length - 3}</span>
							{/if}
						</div>
					{/if}
				</button>
			{/if}
		{/each}
	</div>

	<!-- Legend -->
	<div class="mt-4 pt-3 border-t flex flex-wrap gap-4 justify-center text-xs">
		<div class="flex items-center gap-1">
			<span class="w-3 h-3 rounded-full bg-yellow-400"></span>
			<span class="text-gray-600">Chờ duyệt</span>
		</div>
		<div class="flex items-center gap-1">
			<span class="w-3 h-3 rounded-full bg-green-400"></span>
			<span class="text-gray-600">Đã duyệt</span>
		</div>
		<div class="flex items-center gap-1">
			<span class="w-3 h-3 rounded-full bg-red-400"></span>
			<span class="text-gray-600">Từ chối</span>
		</div>
		<div class="flex items-center gap-1">
			<span class="w-3 h-3 rounded-full bg-blue-400"></span>
			<span class="text-gray-600">Hoàn thành</span>
		</div>
	</div>
</div>

<style>
	.meeting-calendar {
		max-width: 600px;
	}
</style>
