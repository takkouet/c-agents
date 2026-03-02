# Meeting Booking UI Components — Overview

> Generated: 2026-02-26
> Location: `src/lib/components/chat/`

---

## 1. `ResponseMessage.svelte`

**Path:** `src/lib/components/chat/Messages/ResponseMessage.svelte`

### Purpose
The main wrapper component for rendering an AI assistant's response in a chat thread. It is a large, feature-rich component that handles the full lifecycle of a response message.

### Key Responsibilities
- **Renders message content** via `ContentRenderer` (markdown, code blocks, files, embeds)
- **Status/loading states:** Skeleton loader while waiting, `StatusHistory` for in-progress tool calls
- **Inline editing:** Users can edit the raw message content, with pre/post-processing to preserve `<details>` blocks
- **Copy to clipboard:** Strips details tags, optionally appends a watermark from config
- **Text-to-speech (TTS):** Supports browser `SpeechSynthesis`, OpenAI TTS API, and Kokoro (browser-side neural TTS)
- **Feedback/rating:** Thumbs up/down → creates or updates a `Feedback` record via API; auto-generates tags on rating
- **Sibling navigation:** Prev/next arrows to switch between regenerated variants of the same message
- **Action buttons:** Edit, Copy, Read Aloud, Info (usage stats tooltip), Good/Bad response, Continue, Regenerate, Delete, custom model actions
- **Follow-up prompts:** Renders `FollowUps` component after the last message if `followUps` are present
- **Citations & code executions:** Delegates to `Citations` and `CodeExecutions` sub-components

### Key Props
| Prop | Type | Description |
|------|------|-------------|
| `chatId` | string | Parent chat ID |
| `history` | object | Full message history tree |
| `messageId` | string | ID of this message |
| `siblings` | array | Sibling message IDs (for regenerated variants) |
| `isLastMessage` | boolean | Controls button visibility |
| `readOnly` | boolean | Hides edit/rate/regenerate actions |
| `editCodeBlock` | boolean | Enables code block inline editing |

### Notable Internal Logic
- `GEMINI_PROXY_URL = 'http://localhost:4000'` — hardcoded proxy URL constant (currently unused in the visible template but imported at the top)
- `preprocessForEditing / postprocessAfterEditing` — replaces `<details>` blocks with placeholders so the textarea doesn't corrupt them
- `speak()` — routes TTS to the appropriate engine based on config: browser → OpenAI → Kokoro
- `feedbackHandler()` — creates or updates feedback, then attempts to auto-tag using `generateTags`

---

## 2. `MeetingBookingCard.svelte`

**Path:** `src/lib/components/chat/MeetingBookingCard.svelte`

### Purpose
A self-contained card UI that displays a **meeting room booking request** in detail. It is an earlier/simpler version of `MeetingCard.svelte` with inline CSS (no embedded room selector).

### Key Responsibilities
- Displays booking metadata: title, date, time, capacity, location, room, floor
- Shows equipment tags (projector, whiteboard, video conf, etc.) with English labels
- Allows catering selection (toggle checkboxes for food/beverage items) with running total
- Admin note textarea (saves on blur)
- Renders a **5-step approval workflow timeline**: Book Request → User Confirmation → Admin Approval → Catering Approval → Send Calendar Invite
- Shows email confirmation summary when status is `sent`

### Status Values
| Status | Label | Color |
|--------|-------|-------|
| `draft` | Chờ xác nhận | slate |
| `pending` | Chờ duyệt | amber |
| `approved` | Đã duyệt | emerald |
| `rejected` | Từ chối | red |
| `cancelled` | Đã hủy | slate |
| `sent` | Đã gửi | blue |

### Key Props
| Prop | Description |
|------|-------------|
| `booking` | Booking data object |
| `onConfirm(id)` | Called when user confirms a draft booking |
| `onCancel(id)` | Called when user cancels |
| `onApprove(id)` | Admin approves |
| `onReject(id)` | Admin rejects |
| `onAddNote(id, note)` | Admin adds note |
| `onOrderCatering(id, items, total)` | Order catering |
| `onApproveCatering(id)` | Approve catering |
| `onRejectCatering(id)` | Reject catering |
| `onSendCalendar(id)` | Send calendar invite |

### Catering Options (hardcoded)
- Trà + Cà phê + Bánh — 35,000 VNĐ
- Cà phê + Bánh — 30,000 VNĐ
- Nước suối — 10,000 VNĐ
- Buffet Trưa — 150,000 VNĐ
- Cơm hộp — 50,000 VNĐ
- Trái cây — 25,000 VNĐ

---

## 3. `MeetingCalendar.svelte`

**Path:** `src/lib/components/chat/MeetingCalendar.svelte`

### Purpose
A **monthly calendar view** that shows which days have bookings and their approval statuses via color-coded dots.

### Key Responsibilities
- Renders a standard grid calendar for the current month
- Navigates prev/next month
- Marks today's date with a blue highlight
- Shows up to 3 colored dots per day cell (one per booking), with a `+N` overflow indicator
- Status color legend at the bottom
- Calls `onSelectDate(date, bookings)` when a day is clicked

### Status Colors
| Status | Color |
|--------|-------|
| `pending` | yellow-400 |
| `approved` | green-400 |
| `rejected` | red-400 |
| `completed` | blue-400 |
| default | gray-400 |

### Key Props
| Prop | Description |
|------|-------------|
| `bookings` | Array of booking objects (must have `.date` in `YYYY-MM-DD` format and `.status`) |
| `onSelectDate` | Callback `(date: string, bookings: array) => void` |

### Localization
Labels are in Vietnamese (`MONTH_NAMES`, `WEEKDAY_NAMES`). The calendar week starts on Sunday (CN).

---

## 4. `MeetingCard.svelte`

**Path:** `src/lib/components/chat/MeetingCard.svelte`

### Purpose
The **polished, production-quality version** of `MeetingBookingCard.svelte`. It shares the same overall structure but adds:
- A gradient header with CMC Global branding
- Animated fly-in on mount
- **Embedded room selector** — clicking the room field opens `RoomList.svelte` inline (no modal)
- Expandable catering section (collapsed by default)
- Vietnamese equipment labels (via `EQUIPMENT_VI` map)
- More refined CSS (glassmorphism card, animated workflow pulse)

### Key Responsibilities
All the same as `MeetingBookingCard` plus:
- **Room selection:** Renders `<RoomList embedded={true}>` inside the card body, handles `select` and `close` events to update `activeBooking`
- **Collapsible sections:** Catering section toggles open/closed via `expandedSection`
- Uses `$: activeBooking = booking` reactive binding so room selection updates the displayed data without a full re-render

### Key Props
Same signature as `MeetingBookingCard.svelte` (identical prop names and callbacks).

### Differences from `MeetingBookingCard.svelte`
| Feature | MeetingBookingCard | MeetingCard |
|---------|-------------------|-------------|
| Styling | Plain border/bg | Glassmorphism gradient |
| Room selector | None | Embedded `RoomList` |
| Equipment labels | English | Vietnamese |
| Catering section | Always expanded | Collapsible |
| Branding | None | CMC Global logo |
| Animation | None | `fly` transition on mount |

---

## 5. `RoomList.svelte`

**Path:** `src/lib/components/chat/RoomList.svelte`

### Purpose
A **room selection UI** that displays available meeting rooms on a Leaflet map alongside a filterable list. Can be used either as a full-screen modal overlay or embedded inline inside another component (e.g., `MeetingCard`).

### Key Responsibilities
- Displays 8 hardcoded mock rooms across 3 locations (HCM, HN, DN)
- Filters rooms by location via tab buttons
- Shows each room with: photo thumbnail, name, address, capacity, floor, equipment tags
- Renders an **interactive Leaflet map** (OpenStreetMap tiles) with markers for each room
- Clicking a map marker selects the room and scrolls to it in the list
- Clicking a room in the list focuses its marker on the map
- Floating preview card over the map shows the selected room's details
- Dispatches `select` event with `{ room, booking }` when confirmed
- Dispatches `close` event when dismissed

### Display Modes
| Mode | Trigger | Behavior |
|------|---------|----------|
| **Modal** | `show={true}` | Full-screen overlay with backdrop blur |
| **Embedded** | `embedded={true}` | Renders inline in parent, no overlay |

### Key Props
| Prop | Description |
|------|-------------|
| `show` | Boolean, controls modal visibility |
| `booking` | Current booking context (passed through with `select` event) |
| `embedded` | Boolean, switches to embedded layout |

### Mock Room Data
Rooms are statically defined in `MOCK_ROOMS`. Each room has: `id`, `name`, `location` (HCM/HN/DN), `address`, `lat`/`lng`, `floor`, `capacity`, `equipment[]`, `image` (Unsplash URL).

### Map Implementation
- Uses `leaflet` (imported dynamically client-side only)
- Waits for `mapContainer` DOM element before initializing
- In embedded mode, polls with `waitForMapContainer()` since the element may not exist immediately
- Map popups are HTML strings with inline styles

---

## Component Relationships

```
ResponseMessage.svelte
│
└── (renders custom HTML content from AI)
    └── MeetingCard.svelte          ← rendered when AI returns booking data
        ├── RoomList.svelte         ← embedded room picker (toggled by user)
        └── (callbacks: onConfirm, onApprove, etc. → to parent/AI)

MeetingBookingCard.svelte           ← older/simpler alternative to MeetingCard

MeetingCalendar.svelte              ← standalone calendar, used separately
```

---

## Data Flow Summary

1. AI generates a booking object and returns it in message content
2. `ResponseMessage` renders the content (likely via `ContentRenderer` or a custom component slot)
3. `MeetingCard` displays the booking with full detail and interactive controls
4. User clicks "Select Room" → `RoomList` opens embedded, dispatches `select` → `MeetingCard` updates `activeBooking`
5. User clicks "Confirm/Approve/etc." → callback prop is called → parent sends action back to AI or updates booking state
6. `MeetingCalendar` provides a separate overview of all bookings by date

---

## Localization Notes
- All status labels and UI text in `MeetingBookingCard` / `MeetingCard` / `MeetingCalendar` / `RoomList` are in **Vietnamese**
- `ResponseMessage` uses `$i18n.t()` for full i18n support
- Catering prices are in VNĐ (Vietnamese Dong)
- Dates are displayed as `DD/MM/YYYY`
