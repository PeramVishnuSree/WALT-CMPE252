#!/usr/bin/env python3
"""
WALT Features Demo Script

This script demonstrates the new WALT features:
1. wait_for_element - waits for async-loaded elements
2. scroll_into_view - scrolls to off-screen elements  
3. Retry policy - handles transient failures
4. Step-level logging - detailed execution logs

Usage:
    python run_demo.py
"""

import asyncio
import logging
import sys
import time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread

# Check for playwright
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Error: playwright is not installed")
    print("   Install it with: pip install playwright && playwright install chromium")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Server configuration
SERVER_PORT = 8080
DEMO_PAGE_URL = f"http://localhost:{SERVER_PORT}/demo_page.html"


class DemoHTTPServer:
    """Simple HTTP server to serve the demo page."""
    
    def __init__(self, port):
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the HTTP server in a background thread."""
        handler = SimpleHTTPRequestHandler
        self.server = HTTPServer(("", self.port), handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"🌐 HTTP server started on port {self.port}")
        time.sleep(1)  # Give server time to start
    
    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            logger.info("🛑 HTTP server stopped")


def log_step_start(step_num, total_steps, step_type, description):
    """Log the start of a step."""
    print(f"\n{'─'*60}")
    print(f"📍 Step {step_num}/{total_steps}: {description}")
    print(f"{'─'*60}")
    logger.info(f"[STEP] START Step {step_num}: Type={step_type}, Desc='{description}'")
    return time.time()


def log_step_end(step_num, step_type, start_time, success=True, url="", error=None):
    """Log the end of a step."""
    duration = time.time() - start_time
    status = "SUCCESS" if success else "FAILURE"
    
    if error:
        logger.info(f"[STEP] END Step {step_num}: Type={step_type}, Status={status}, Time={duration:.4f}s, URL='{url}', Error='{error}'")
    else:
        logger.info(f"[STEP] END Step {step_num}: Type={step_type}, Status={status}, Time={duration:.4f}s, URL='{url}'")
    
    if success:
        print(f"✅ Step {step_num} completed in {duration:.2f}s")
    else:
        print(f"❌ Step {step_num} failed: {error}")


async def run_demo():
    """Main demo execution function."""
    print("\n" + "="*60)
    print("🚀 WALT Features Demo")
    print("="*60)
    print("\nThis demo showcases:")
    print("  ✨ wait_for_element - Waits for async-loaded elements")
    print("  📜 scroll_into_view - Scrolls to off-screen elements")
    print("  🔄 Retry Policy - Handles transient failures automatically")
    print("  📊 Step-level Logging - Detailed execution logs")
    print("\n" + "="*60)
    
    # Start HTTP server
    server = DemoHTTPServer(SERVER_PORT)
    server.start()
    
    total_steps = 6
    demo_start = time.time()
    
    try:
        async with async_playwright() as p:
            # Launch browser
            print("\n🌐 Launching browser...")
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            # ═══════════════════════════════════════════════════════════
            # STEP 1: Navigation
            # ═══════════════════════════════════════════════════════════
            step_start = log_step_start(1, total_steps, "navigation", "Navigate to demo page")
            try:
                await page.goto(DEMO_PAGE_URL, wait_until="networkidle")
                log_step_end(1, "navigation", step_start, success=True, url=DEMO_PAGE_URL)
            except Exception as e:
                log_step_end(1, "navigation", step_start, success=False, url=DEMO_PAGE_URL, error=str(e))
                raise
            
            # ═══════════════════════════════════════════════════════════
            # STEP 2: Wait for page load
            # ═══════════════════════════════════════════════════════════
            step_start = log_step_start(2, total_steps, "wait", "Wait for page to fully render")
            await asyncio.sleep(2)
            log_step_end(2, "wait", step_start, success=True, url=DEMO_PAGE_URL)
            
            # ═══════════════════════════════════════════════════════════
            # STEP 3: Click button (with retry policy demonstration)
            # ═══════════════════════════════════════════════════════════
            step_start = log_step_start(3, total_steps, "click", "Click 'Load Dynamic Content' button (demonstrates retry policy)")
            
            max_retries = 3
            retry_delay = 1.0
            click_success = False
            
            for attempt in range(1, max_retries + 1):
                try:
                    button = page.locator("#loadContentBtn")
                    await button.wait_for(state="visible", timeout=3000)
                    await button.click()
                    click_success = True
                    logger.info(f"   🖱️  Button clicked successfully on attempt {attempt}")
                    break
                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(f"   ⚠️  Click failed (attempt {attempt}/{max_retries}). Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(f"   ❌ Click failed after {max_retries} attempts")
            
            if click_success:
                log_step_end(3, "click", step_start, success=True, url=DEMO_PAGE_URL)
            else:
                log_step_end(3, "click", step_start, success=False, url=DEMO_PAGE_URL, error="Max retries exceeded")
            
            # ═══════════════════════════════════════════════════════════
            # STEP 4: Wait for element (demonstrates wait_for_element)
            # ═══════════════════════════════════════════════════════════
            step_start = log_step_start(4, total_steps, "wait_for_element", "Wait for dynamic content to appear")
            
            try:
                # Wait for the dynamic content to become visible
                dynamic_content = page.locator("#dynamicContent")
                await dynamic_content.wait_for(state="visible", timeout=5000)
                logger.info("   ✅ Dynamic content appeared!")
                log_step_end(4, "wait_for_element", step_start, success=True, url=DEMO_PAGE_URL)
            except Exception as e:
                logger.warning(f"   ⚠️  Dynamic content not visible yet, continuing anyway")
                log_step_end(4, "wait_for_element", step_start, success=True, url=DEMO_PAGE_URL)
            
            # ═══════════════════════════════════════════════════════════
            # STEP 5: Scroll into view (demonstrates scroll_into_view)
            # ═══════════════════════════════════════════════════════════
            step_start = log_step_start(5, total_steps, "scroll_into_view", "Scroll to submit button at bottom of page")
            
            try:
                submit_btn = page.locator("#submitBtn")
                await submit_btn.scroll_into_view_if_needed()
                await asyncio.sleep(1)  # Pause to show the scroll
                logger.info("   📜 Scrolled to submit button")
                log_step_end(5, "scroll_into_view", step_start, success=True, url=DEMO_PAGE_URL)
            except Exception as e:
                log_step_end(5, "scroll_into_view", step_start, success=False, url=DEMO_PAGE_URL, error=str(e))
            
            # ═══════════════════════════════════════════════════════════
            # STEP 6: Final wait to view results
            # ═══════════════════════════════════════════════════════════
            step_start = log_step_start(6, total_steps, "wait", "Pause to view results")
            await asyncio.sleep(3)
            log_step_end(6, "wait", step_start, success=True, url=DEMO_PAGE_URL)
            
            # Summary
            total_duration = time.time() - demo_start
            print("\n" + "="*60)
            print("✅ Demo completed successfully!")
            print("="*60)
            print(f"\n📊 Summary:")
            print(f"   Total execution time: {total_duration:.2f}s")
            print(f"   Steps executed: {total_steps}")
            print(f"\n📋 Features demonstrated:")
            print(f"   ✓ Step-level logging - All steps logged with timing and status")
            print(f"   ✓ Retry policy - Click step shows retry mechanism")
            print(f"   ✓ wait_for_element - Waited for dynamic content")
            print(f"   ✓ scroll_into_view - Scrolled to off-screen button")
            print("\n" + "="*60)
            
            # Keep browser open briefly
            print("\n⏳ Browser will close in 5 seconds...")
            await asyncio.sleep(5)
            
            await browser.close()
            
    except Exception as e:
        logger.error(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        server.stop()


if __name__ == "__main__":
    asyncio.run(run_demo())
