# WALT Features Demo

This demo showcases the new WALT features that have been integrated into the codebase.

## Features Demonstrated

1. **`wait_for_element`** - Waits for dynamically loaded elements to appear in the DOM
2. **`scroll_into_view`** - Automatically scrolls to bring off-screen elements into view
3. **Retry Policy** - Automatically retries failed UI interactions with configurable delays
4. **Step-level Logging** - Detailed logging of each step execution with timing and status

## Prerequisites

- Python 3.10+
- WALT dependencies installed (see main README)
- OpenAI API key set in environment (or `.env` file) - optional, demo will use mock LLM if not available
- Playwright browsers installed (`playwright install chromium`)

## Running the Demo

1. **Make sure you're in the project root directory** (where `demo_page.html` is located)

2. **Run the demo script:**
   ```bash
   python run_demo.py
   ```

3. **What happens:**
   - A local HTTP server starts on port 8080
   - A browser window opens showing the demo page
   - The tool executes automatically, demonstrating all features
   - Step-by-step logs appear in the console
   - The browser shows the interactions in real-time

## Demo Flow

The demo performs the following actions:

1. **Navigate** to the demo page
2. **Click** the "Load Dynamic Content" button
3. **Wait for element** - Waits for the dynamically loaded content to appear (demonstrates `wait_for_element`)
4. **Fill form fields** - May require retries if fields are initially disabled (demonstrates retry policy)
5. **Scroll into view** - Scrolls to the submit button at the bottom (demonstrates `scroll_into_view`)
6. **Submit** the form

## Understanding the Logs

When `enable_step_logging=True`, you'll see logs like:

```
2024-01-01 12:00:00 - [STEP] - Step 0: navigation - Starting
2024-01-01 12:00:01 - [STEP] - Step 0: navigation - Success (1.2s) - URL: http://localhost:8080/demo_page.html
2024-01-01 12:00:02 - [STEP] - Step 1: click - Starting
...
```

Each log entry shows:
- **Step index** - The step number in the tool
- **Step type** - The type of action (navigation, click, wait_for_element, etc.)
- **Status** - Success or failure
- **Duration** - How long the step took
- **Current URL** - The page URL at the time of execution

## Customization

You can modify the demo by editing:

- **`demo_page.html`** - Change the demo page content and behavior
- **`run_demo.py`** - Adjust tool steps, retry settings, or logging configuration

### Configuration Options

In `run_demo.py`, you can adjust:

```python
config = ToolExecutionConfig(
    enable_step_logging=True,  # Enable/disable step logging
    max_retries=2,              # Number of retries for failed steps
    retry_delay=1.0,            # Delay between retries (seconds)
    inter_step_delay=0.5,      # Delay between steps (seconds)
)
```

## Troubleshooting

### Browser doesn't open
- Make sure Playwright browsers are installed: `playwright install chromium`
- Check that port 8080 is not in use

### Element hashes not found
- The demo will fall back to using CSS selectors if hashes can't be calculated
- This is normal and the demo will still work, just without the `wait_for_element` and `scroll_into_view` features

### API Key issues
- If you don't have an OpenAI API key, the demo will use a mock LLM
- Some features may not work fully with the mock LLM, but the core functionality will still be demonstrated

## For Video Recording

When recording the demo:

1. **Start the demo** in a terminal with visible logging
2. **Position windows** so both the browser and terminal are visible
3. **The demo runs automatically** - no manual interaction needed
4. **Highlight the console logs** to show step-level logging in action
5. **Point out** the browser interactions as they happen:
   - Async content loading (wait_for_element)
   - Form field interactions (retry policy)
   - Scrolling to submit button (scroll_into_view)

## Technical Details

- The demo uses a local HTTP server to serve `demo_page.html`
- Element hashes are calculated dynamically from the DOM
- The tool execution uses WALT's standard tool execution pipeline
- All new features are integrated seamlessly with existing functionality


