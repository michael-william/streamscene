# Streams Page Redesign Plan

**Created:** November 3, 2025
**Status:** Ready for implementation
**Context:** Streams not displaying on /streams page + UX redesign needed

---

## Current Issues

### 1. Streams Not Appearing After Page Load
**Symptom:** User can create streams (duplicate prevention works), but streams don't show in the UI.

**Root Cause:** Reflex state reactivity issue. The `load_streams()` method populates `self.streams` but the UI doesn't re-render.

**Evidence:**
- Database confirms streams exist (query shows "First" stream for user 314daf51-9126-4fde-990f-0337711ac71f)
- `load_streams()` method correctly queries database and populates `self.streams`
- Manual append in `create_stream()` (line 99-104) works, suggesting state updates need explicit triggers

### 2. Poor UX for Stream Management
- No visual separation between owned and subscribed streams
- Create form always visible (takes up space)
- No search functionality
- No table-based layout (uses cards in foreach loop)

### 3. Missing Features
- Can't see subscribed streams separately
- No way to search/filter streams
- Subscription features implemented in backend but not exposed in UI

---

## Investigation Findings

### Backend Status

**Subscriptions System:** ✅ Fully implemented
- `get_subscribed_streams()` - Returns streams user subscribed to
- `subscribe_to_stream()` - Subscribe to a stream
- `unsubscribe_from_stream()` - Unsubscribe from stream
- `approve_subscription()` - Approve pending subscriptions
- `get_subscription()` - Check subscription status
- `get_stream_subscribers()` - Get all subscribers

**Current Database State:**
- 2 streams exist:
  - "Family Updates" (owner: 53d94bfc-e641-488c-854f-415532394ee1)
  - "First" (owner: 314daf51-9126-4fde-990f-0337711ac71f)
- 0 subscriptions exist (stream_subscriptions table empty)

### Current Code Structure

**File:** `streamscene/pages/streams.py`

**Key sections:**
- Lines 31-37: `on_mount()` - Calls `load_streams()`
- Lines 39-67: `load_streams()` - Queries DB and populates `self.streams`
- Lines 69-111: `create_stream()` - Creates stream with manual append (line 99-104)
- Lines 173-207: `stream_list()` - Renders stream cards using `rx.foreach()`
- Lines 209-237: `create_stream_form()` - Always-visible form
- Lines 281-329: `streams()` - Main layout (2-column grid)

---

## Redesign Specifications

### New Layout Structure

```
┌──────────────────────────────────────────────────────────┐
│ Search Streams...                        [+ Add Stream]  │
├────────────────────────────┬─────────────────────────────┤
│                            │                             │
│ STREAMS I OWN              │                             │
│ ┌────────────────────────┐ │      POST VIEW              │
│ │ Name | Desc | Vis | ▶ │ │      (existing)             │
│ │ First | ... | Priv | ▶ │ │                             │
│ └────────────────────────┘ │                             │
│                            │                             │
│ STREAMS I'M SUBSCRIBED TO  │                             │
│ ┌────────────────────────┐ │                             │
│ │ Name | Owner | Desc | ▶│ │                             │
│ │ (empty state message)  │ │                             │
│ └────────────────────────┘ │                             │
└────────────────────────────┴─────────────────────────────┘

Modal (when Add Stream clicked):
┌────────────────────────┐
│ Create New Stream  [×] │
├────────────────────────┤
│ Stream name:           │
│ [________________]     │
│                        │
│ Description:           │
│ [________________]     │
│ [________________]     │
│                        │
│ ☐ Make public          │
│                        │
│    [Cancel] [Create]   │
└────────────────────────┘
```

### Features

1. **Search Bar**
   - Filters both owned and subscribed streams in real-time
   - Searches by name and description
   - Single input at top of page

2. **Two Separate Tables**
   - "Streams I Own" table with columns: Name, Description, Visibility, Actions
   - "Streams I'm Subscribed To" table with columns: Name, Owner, Description, Actions
   - Modern Reflex table component (`rx.table.root()`)

3. **Add Stream Button**
   - Top-right corner, same row as search
   - Opens modal dialog
   - Modal contains create form
   - Modal closes on successful creation

4. **Actions**
   - Owned streams: "View Posts" button
   - Subscribed streams: "View Posts" + "Unsubscribe" buttons

---

## Implementation Plan

### Part 1: Fix State Reactivity Issue

**File:** `streamscene/pages/streams.py`

**Update `load_streams()` method (lines ~39-67):**

Before:
```python
self.streams = [
    {
        "id": str(stream.id),
        ...
    }
    for stream in user_streams
]
```

After:
```python
streams_data = [
    {
        "id": str(stream.id),
        ...
    }
    for stream in user_streams
]
self.streams = streams_data
yield  # Force state update to trigger UI re-render
```

**Update `on_mount()` method (lines ~31-37):**
```python
def on_mount(self):
    if not self.user_id:
        return rx.redirect("/")

    self.load_streams()
    yield  # Ensure state updates propagate
```

---

### Part 2: Add New State Variables

**File:** `streamscene/pages/streams.py`, in `StreamsState` class (after line 16)

**Add:**
```python
# Separate stream lists for better organization
owned_streams: List[dict] = []
subscribed_streams: List[dict] = []

# Search functionality
search_query: str = ""

# Modal control
is_create_modal_open: bool = False
```

---

### Part 3: Update Loading Methods

**Replace `load_streams()` with three new methods:**

**3A. New method: `load_owned_streams()`**
```python
def load_owned_streams(self):
    """Load streams owned by the user."""
    if not self.user_id:
        return

    try:
        user_uuid = UUID(self.user_id)
    except ValueError:
        return

    try:
        with get_db_session() as session:
            user_streams = stream_ops.get_user_streams(session, user_uuid)

            streams_data = [
                {
                    "id": str(stream.id),
                    "name": stream.name,
                    "description": stream.description,
                    "is_public": stream.is_public,
                }
                for stream in user_streams
            ]
            self.owned_streams = streams_data
            yield  # Force UI update
    except Exception as e:
        self.error_message = f"Error loading owned streams: {str(e)}"
```

**3B. New method: `load_subscribed_streams()`**
```python
def load_subscribed_streams(self):
    """Load streams user is subscribed to."""
    if not self.user_id:
        return

    try:
        user_uuid = UUID(self.user_id)
    except ValueError:
        return

    try:
        with get_db_session() as session:
            subscribed = stream_ops.get_subscribed_streams(session, user_uuid)

            streams_data = [
                {
                    "id": str(stream.id),
                    "name": stream.name,
                    "description": stream.description,
                    "is_public": stream.is_public,
                    "owner_name": "Owner",  # TODO: Get actual owner name
                }
                for stream in subscribed
            ]
            self.subscribed_streams = streams_data
            yield  # Force UI update
    except Exception as e:
        self.error_message = f"Error loading subscribed streams: {str(e)}"
```

**3C. New method: `load_all_streams()`**
```python
def load_all_streams(self):
    """Load both owned and subscribed streams."""
    self.load_owned_streams()
    self.load_subscribed_streams()
```

**Update `on_mount()` to call new method:**
```python
def on_mount(self):
    if not self.user_id:
        return rx.redirect("/")

    self.load_all_streams()
```

---

### Part 4: Add Search Filtering (Computed Vars)

**Add after state variable definitions:**

```python
@rx.var
def filtered_owned_streams(self) -> List[dict]:
    """Filter owned streams based on search query."""
    if not self.search_query:
        return self.owned_streams

    query = self.search_query.lower()
    return [
        stream for stream in self.owned_streams
        if query in stream["name"].lower() or query in stream["description"].lower()
    ]

@rx.var
def filtered_subscribed_streams(self) -> List[dict]:
    """Filter subscribed streams based on search query."""
    if not self.search_query:
        return self.subscribed_streams

    query = self.search_query.lower()
    return [
        stream for stream in self.subscribed_streams
        if query in stream["name"].lower() or query in stream["description"].lower()
    ]
```

---

### Part 5: Add Modal Control Methods

**Add these helper methods:**

```python
def open_create_modal(self):
    """Open the create stream modal."""
    self.is_create_modal_open = True

def close_create_modal(self):
    """Close the create stream modal and clear form."""
    self.is_create_modal_open = False
    self.new_stream_name = ""
    self.new_stream_description = ""
    self.new_stream_is_public = False
    self.error_message = ""
```

---

### Part 6: Update Stream Creation Method

**Modify existing `create_stream()` method (lines ~69-111):**

Change the success block (after session.commit()):

Before:
```python
session.commit()

# Add to state immediately for instant UI update
self.streams.append({
    "id": str(stream.id),
    "name": stream.name,
    "description": stream.description,
    "is_public": stream.is_public,
})

self.success_message = f"Stream '{self.new_stream_name}' created!"
self.new_stream_name = ""
self.new_stream_description = ""
self.new_stream_is_public = False
```

After:
```python
session.commit()

# Add to owned_streams for instant UI update
self.owned_streams.append({
    "id": str(stream.id),
    "name": stream.name,
    "description": stream.description,
    "is_public": stream.is_public,
})

self.success_message = f"Stream '{self.new_stream_name}' created!"
self.close_create_modal()  # Close modal and clear form
yield  # Force UI update
```

---

### Part 7: Build New UI Components

**7A. Search Bar + Add Button Component**

Replace `create_stream_form()` with:

```python
def search_and_add_bar() -> rx.Component:
    """Search bar with Add Stream button."""
    return rx.hstack(
        rx.input(
            placeholder="Search streams...",
            value=StreamsState.search_query,
            on_change=StreamsState.set_search_query,
            size="3",
            width="100%",
        ),
        rx.button(
            "+ Add Stream",
            on_click=StreamsState.open_create_modal,
            color_scheme="blue",
            size="3",
        ),
        spacing="4",
        width="100%",
        justify="between",
        align="center",
    )
```

**7B. Owned Streams Table**

```python
def owned_streams_table() -> rx.Component:
    """Table showing streams owned by the user."""
    return rx.vstack(
        rx.heading("Streams I Own", size="6"),
        rx.cond(
            StreamsState.owned_streams.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Description"),
                        rx.table.column_header_cell("Visibility"),
                        rx.table.column_header_cell("Actions"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        StreamsState.filtered_owned_streams,
                        lambda stream: rx.table.row(
                            rx.table.cell(
                                rx.text(stream["name"], weight="medium")
                            ),
                            rx.table.cell(
                                rx.text(stream["description"], color="gray", size="2")
                            ),
                            rx.table.cell(
                                rx.badge(
                                    rx.cond(stream["is_public"], "Public", "Private"),
                                    color_scheme=rx.cond(stream["is_public"], "green", "gray"),
                                )
                            ),
                            rx.table.cell(
                                rx.button(
                                    "View Posts",
                                    on_click=lambda sid=stream["id"]: StreamsState.select_stream(sid),
                                    size="2",
                                    variant="soft",
                                )
                            ),
                        ),
                    ),
                ),
                variant="surface",
                size="3",
                width="100%",
            ),
            rx.text(
                "No streams yet. Click 'Add Stream' to create your first stream!",
                color="gray",
                size="3",
            ),
        ),
        spacing="3",
        width="100%",
        align="start",
    )
```

**7C. Subscribed Streams Table**

```python
def subscribed_streams_table() -> rx.Component:
    """Table showing streams user is subscribed to."""
    return rx.vstack(
        rx.heading("Streams I'm Subscribed To", size="6"),
        rx.cond(
            StreamsState.subscribed_streams.length() > 0,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Owner"),
                        rx.table.column_header_cell("Description"),
                        rx.table.column_header_cell("Actions"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(
                        StreamsState.filtered_subscribed_streams,
                        lambda stream: rx.table.row(
                            rx.table.cell(
                                rx.text(stream["name"], weight="medium")
                            ),
                            rx.table.cell(
                                rx.text(stream["owner_name"], size="2")
                            ),
                            rx.table.cell(
                                rx.text(stream["description"], color="gray", size="2")
                            ),
                            rx.table.cell(
                                rx.hstack(
                                    rx.button(
                                        "View Posts",
                                        on_click=lambda sid=stream["id"]: StreamsState.select_stream(sid),
                                        size="2",
                                        variant="soft",
                                    ),
                                    rx.button(
                                        "Unsubscribe",
                                        # on_click=lambda sid=stream["id"]: StreamsState.unsubscribe_action(sid),
                                        size="2",
                                        color_scheme="red",
                                        variant="ghost",
                                        disabled=True,  # TODO: Implement unsubscribe
                                    ),
                                    spacing="2",
                                )
                            ),
                        ),
                    ),
                ),
                variant="surface",
                size="3",
                width="100%",
            ),
            rx.text(
                "You haven't subscribed to any streams yet.",
                color="gray",
                size="3",
            ),
        ),
        spacing="3",
        width="100%",
        align="start",
    )
```

**7D. Create Stream Modal**

```python
def create_stream_modal() -> rx.Component:
    """Modal dialog for creating a new stream."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("Create New Stream"),
                rx.dialog.description(
                    "Create a new stream to share messages with family and friends."
                ),
                rx.input(
                    placeholder="Stream name",
                    value=StreamsState.new_stream_name,
                    on_change=StreamsState.set_new_stream_name,
                    size="3",
                ),
                rx.text_area(
                    placeholder="Description (optional)",
                    value=StreamsState.new_stream_description,
                    on_change=StreamsState.set_new_stream_description,
                    size="3",
                    rows="3",
                ),
                rx.checkbox(
                    "Make this stream public",
                    checked=StreamsState.new_stream_is_public,
                    on_change=StreamsState.set_new_stream_is_public,
                    size="3",
                ),
                rx.cond(
                    StreamsState.error_message,
                    rx.callout(
                        StreamsState.error_message,
                        icon="triangle_alert",
                        color_scheme="red",
                        size="1",
                    ),
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                            size="3",
                            on_click=StreamsState.close_create_modal,
                        )
                    ),
                    rx.button(
                        "Create Stream",
                        on_click=StreamsState.create_stream,
                        color_scheme="blue",
                        size="3",
                    ),
                    spacing="3",
                    justify="end",
                    width="100%",
                ),
                spacing="4",
                width="100%",
            ),
            size="3",
            max_width="500px",
        ),
        open=StreamsState.is_create_modal_open,
        on_open_change=StreamsState.set_is_create_modal_open,
    )
```

---

### Part 8: Update Main Layout

**Modify `streams()` function (lines ~281-329):**

Before:
```python
content = rx.container(
    rx.vstack(
        # Messages
        rx.cond(...),
        # Main content in two columns
        rx.grid(
            rx.vstack(
                stream_list(),
                create_stream_form(),
                ...
            ),
            post_view(),
            columns="2",
            ...
        ),
        ...
    ),
    max_width="1200px",
)
```

After:
```python
content = rx.container(
    rx.vstack(
        # Messages
        rx.cond(
            StreamsState.error_message,
            rx.callout(
                StreamsState.error_message,
                icon="triangle_alert",
                color_scheme="red",
            ),
        ),
        rx.cond(
            StreamsState.success_message,
            rx.callout(
                StreamsState.success_message,
                icon="check",
                color_scheme="green",
            ),
        ),

        # Main content in two columns
        rx.grid(
            # Left column: Streams section
            rx.vstack(
                search_and_add_bar(),
                owned_streams_table(),
                subscribed_streams_table(),
                spacing="6",
                width="100%",
            ),

            # Right column: Post view (unchanged)
            post_view(),

            columns="2",
            spacing="6",
            width="100%",
        ),

        # Modal (rendered at root level)
        create_stream_modal(),

        spacing="6",
        padding="4",
        width="100%",
    ),
    max_width="1400px",  # Wider for tables
)

return authenticated_layout(content, current_page="streams")
```

---

## Testing Checklist

After implementation, test:

1. **Page Load:**
   - [ ] Streams appear immediately on page load
   - [ ] Owned streams show in "Streams I Own" table
   - [ ] Empty state shows if no streams

2. **Search:**
   - [ ] Type in search bar → both tables filter in real-time
   - [ ] Clear search → both tables show all streams
   - [ ] Search matches name and description

3. **Create Stream:**
   - [ ] Click "Add Stream" → modal opens
   - [ ] Fill form and click "Create" → modal closes, stream appears in table
   - [ ] Try duplicate name → error shows in modal, modal stays open
   - [ ] Click "Cancel" → modal closes, form clears

4. **Stream Actions:**
   - [ ] Click "View Posts" → post view updates
   - [ ] Posts show for selected stream

5. **Subscriptions:**
   - [ ] "Streams I'm Subscribed To" shows empty state (no subscriptions yet)
   - [ ] (Future: test subscribe/unsubscribe when UI implemented)

---

## Files to Modify

1. **`streamscene/pages/streams.py`** - Complete rewrite of:
   - State variables (add new ones)
   - Loading methods (split into owned/subscribed)
   - UI components (replace cards with tables)
   - Main layout (add modal, search bar)

---

## Optional Future Enhancements

1. **Subscribe to Public Streams:**
   - Add "Discover Streams" section
   - Show public streams user can subscribe to
   - Add "Subscribe" button

2. **Stream Management:**
   - Edit stream details
   - Delete stream (with confirmation)
   - Manage subscribers (approve/reject)

3. **Better Owner Display:**
   - Update backend to include owner email/name in subscribed streams
   - Show avatar or initials

4. **Pagination:**
   - If user has many streams, add pagination or infinite scroll

---

## Notes for Next Session

- Start with Part 1 (fix reactivity) as a quick win
- Test if streams appear before doing full redesign
- If Part 1 fixes the issue, proceed with full redesign (Parts 2-8)
- The modal approach is cleaner than always-visible form
- Tables provide better scanning than card-based layout
- Search is essential for users with many streams

---

**End of Plan**
