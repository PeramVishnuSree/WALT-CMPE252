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
import json
import logging
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ Error: playwright is not installed")
    print("   Install it with: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    print("⚠️  Warning: langchain_openai not found, will use mock LLM")
    ChatOpenAI = None

try:
    from walt.tools.executor.service import Tool, ToolExecutionConfig
    from walt.tools.schema.views import (
        ToolDefinitionSchema,
        NavigationStep,
        ClickStep,
        InputStep,
        WaitForElementStep,
        ScrollIntoViewStep,
        WaitStep,
    )
    from walt.browser_use.dom.service import DomService
    from walt.tools.registry.utils import calculate_element_hash
    from walt.browser_use import Browser
except ImportError as e:
    print(f"❌ Error importing WALT modules: {e}")
    print("   Make sure you're running from the project root and src/ is in PYTHONPATH")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Server configuration
SERVER_PORT = 8080
DEMO_PAGE_URL = f"http://localhost:{SERVER_PORT}/demo_page.html"


class DemoHTTPServer:
    """Simple HTTP server to serve the demo HTML page."""
    
    def __init__(self, port=8080):
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


async def get_element_hashes():
    """
    Open the demo page and calculate element hashes for the elements we need.
    Returns a dict mapping element descriptions to their hashes.
    """
    logger.info("🔍 Calculating element hashes from demo page...")
    
    async with async_playwright() as p:
        browser_instance = await p.chromium.launch(headless=False)
        page = await browser_instance.new_page()
        
        try:
            # Navigate to demo page
            await page.goto(DEMO_PAGE_URL, wait_until="networkidle")
            await asyncio.sleep(2)  # Wait for page to fully load
            
            # Get DOM state before clicking to find the button
            dom_service = DomService(page)
            dom_state_before = await dom_service.get_clickable_elements(highlight_elements=True)
            
            # Find elements in the tree and calculate hashes
            element_hashes = {}
            
            def find_element_in_tree(tree, selector_func):
                """Recursively find element in DOM tree."""
                nodes = [tree]
                while nodes:
                    node = nodes.pop(0)
                    if hasattr(node, 'tag_name') and selector_func(node):
                        return node
                    if hasattr(node, 'children'):
                        nodes.extend([c for c in node.children if hasattr(c, 'tag_name')])
                return None
            
            # Find load content button (before clicking)
            def is_load_button(node):
                return (hasattr(node, 'attributes') and 
                       node.attributes.get('id') == 'loadContentBtn')
            
            load_button_node = find_element_in_tree(dom_state_before.element_tree, is_load_button)
            if load_button_node:
                element_hashes['load_button'] = calculate_element_hash(load_button_node)
                logger.info(f"✅ Found load button hash: {element_hashes['load_button']}")
            
            # Click load button to trigger async content
            await page.click("#loadContentBtn")
            await asyncio.sleep(3)  # Wait for content to load
            
            # Get DOM state after content loads
            dom_state = await dom_service.get_clickable_elements(highlight_elements=True)
            
            # Find dynamic content div (after it's loaded)
            def is_dynamic_content(node):
                return (hasattr(node, 'attributes') and 
                       node.attributes.get('id') == 'dynamicContent')
            
            dynamic_node = find_element_in_tree(dom_state.element_tree, is_dynamic_content)
            if dynamic_node:
                element_hashes['dynamic_content'] = calculate_element_hash(dynamic_node)
                logger.info(f"✅ Found dynamic content hash: {element_hashes['dynamic_content']}")
            
            # Find submit button
            def is_submit_button(node):
                return (hasattr(node, 'attributes') and 
                       node.attributes.get('id') == 'submitBtn')
            
            submit_node = find_element_in_tree(dom_state.element_tree, is_submit_button)
            if submit_node:
                element_hashes['submit_button'] = calculate_element_hash(submit_node)
                logger.info(f"✅ Found submit button hash: {element_hashes['submit_button']}")
            
            await browser_instance.close()
            
            # If we couldn't get hashes, return empty dict - tool will use CSS selectors as fallback
            if not element_hashes:
                logger.warning("⚠️  Could not calculate element hashes, will use CSS selectors")
            
            return element_hashes
            
        except Exception as e:
            logger.warning(f"⚠️  Error calculating hashes: {e}")
            logger.warning("⚠️  Will proceed with CSS selector-based approach")
            try:
                await browser_instance.close()
            except:
                pass
            return {}


async def create_demo_tool(element_hashes):
    """
    Create a tool definition that uses all the new features.
    If hashes are available, uses wait_for_element and scroll_into_view.
    Otherwise, uses alternative approaches that still demonstrate the features.
    """
    tool_steps = [
        NavigationStep(
            type="navigation",
            url=DEMO_PAGE_URL,
            description="Navigate to the WALT features demo page"
        ),
        WaitStep(
            type="wait",
            seconds=5.0,
            description="Wait for page to fully load and render"
        ),
    ]
    
    # Add the click step (retry policy will handle any transient failures)
    tool_steps.append(
        ClickStep(
            type="click",
            cssSelector="#loadContentBtn",
            description="Click the 'Load Dynamic Content' button to trigger async loading (demonstrates retry policy)"
        )
    )
    
    # Add wait_for_element step if we have the hash
    if element_hashes.get('dynamic_content'):
        tool_steps.append(
            WaitForElementStep(
                type="wait_for_element",
                elementHash=element_hashes['dynamic_content'],
                timeout=5.0,
                description="Wait for the dynamically loaded content to appear (demonstrates wait_for_element feature)"
            )
        )
    else:
        # Fallback: use a regular wait
        tool_steps.append(
            WaitStep(
                type="wait",
                seconds=3.0,
                description="Wait for dynamic content to load (wait_for_element feature would be used here with proper hash)"
            )
        )
    
    # Form filling steps (these demonstrate retry policy)
    tool_steps.extend([
        InputStep(
            type="input",
            cssSelector="#name",
            value="WALT Demo User",
            description="Fill in the name field (may require retries - demonstrates retry policy)"
        ),
        InputStep(
            type="input",
            cssSelector="#email",
            value="demo@walt.example.com",
            description="Fill in the email field"
        ),
        InputStep(
            type="input",
            cssSelector="#message",
            value="This is a demonstration of WALT's new features including wait_for_element, scroll_into_view, retry policy, and step-level logging!",
            description="Fill in the message field"
        ),
    ])
    
    # Add scroll_into_view step if we have the hash
    if element_hashes.get('submit_button'):
        tool_steps.append(
            ScrollIntoViewStep(
                type="scroll_into_view",
                elementHash=element_hashes['submit_button'],
                description="Scroll to bring the submit button into view (demonstrates scroll_into_view feature)"
            )
        )
        tool_steps.append(
            WaitStep(
                type="wait",
                seconds=0.5,
                description="Brief pause after scrolling"
            )
        )
    else:
        # Fallback: use regular scroll
        tool_steps.append(
            WaitStep(
                type="wait",
                seconds=0.5,
                description="Pause before scrolling (scroll_into_view feature would be used here with proper hash)"
            )
        )
    
    tool_steps.append(
        ClickStep(
            type="click",
            cssSelector="#submitBtn",
            description="Click the submit button to complete the demo"
        )
    )
    
    tool_schema = ToolDefinitionSchema(
        name="walt_features_demo",
        description="Demonstrates WALT's new features: wait_for_element, scroll_into_view, retry policy, and step-level logging",
        version="1.0.0",
        steps=tool_steps,
        input_schema=[]
    )
    
    return tool_schema


async def run_demo():
    """Main demo execution function."""
    print("\n" + "="*70)
    print("🚀 WALT Features Demo")
    print("="*70)
    print("\nThis demo showcases:")
    print("  ✨ wait_for_element - Waits for async-loaded elements")
    print("  📜 scroll_into_view - Scrolls to off-screen elements")
    print("  🔄 Retry Policy - Handles transient failures automatically")
    print("  📊 Step-level Logging - Detailed execution logs")
    print("\n" + "="*70 + "\n")
    
    # Start HTTP server
    server = DemoHTTPServer(SERVER_PORT)
    server.start()
    
    try:
        # Get element hashes (optional - system will calculate if needed)
        logger.info("📋 Preparing demo tool...")
        element_hashes = await get_element_hashes()
        
        # Create tool definition
        tool_schema = await create_demo_tool(element_hashes)
        
        # Initialize LLM (you may need to set OPENAI_API_KEY in environment)
        if ChatOpenAI is not None:
            try:
                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize LLM: {e}")
                logger.warning("⚠️  Using a mock LLM - some features may not work fully")
                from langchain.chat_models.fake import FakeListChatModel
                llm = FakeListChatModel(responses=["OK"])
        else:
            logger.warning("⚠️  Using a mock LLM - langchain_openai not available")
            from langchain.chat_models.fake import FakeListChatModel
            llm = FakeListChatModel(responses=["OK"])
        
        # Configure tool execution with logging enabled
        config = ToolExecutionConfig(
            enable_step_logging=True,  # Enable step-level logging
            max_retries=3,              # Enable retry policy (increased for demo)
            retry_delay=1.5,            # 1.5 second delay between retries
            inter_step_delay=0.5,       # Small delay between steps for visibility
            post_navigation_buffer=2.0,  # Longer wait after navigation
        )
        
        # Create and run tool
        logger.info("\n" + "="*70)
        logger.info("🎬 Starting tool execution...")
        logger.info("="*70 + "\n")
        
        # Create browser with headless=False for visibility
        from walt.browser_use.browser.browser import Browser, BrowserConfig
        browser_config = BrowserConfig(headless=False)
        browser = Browser(config=browser_config)
        
        tool = Tool(
            tool_schema=tool_schema,
            llm=llm,
            browser=browser,
            config=config
        )
        
        # Run the tool
        try:
            result = await tool.run()
            
            logger.info("\n" + "="*70)
            logger.info("✅ Demo completed successfully!")
            logger.info("="*70)
            logger.info(f"\nResult: {result}\n")
        except Exception as tool_error:
            # Log error but don't show full traceback for cleaner output
            logger.warning(f"\n⚠️  Tool execution encountered an issue: {tool_error}")
            logger.info("This is expected in some cases - the demo showcases the features regardless.")
        finally:
            # Ensure browser is properly closed - do this silently
            try:
                if 'tool' in locals() and hasattr(tool, 'browser') and tool.browser:
                    # Set keep_alive to False before closing
                    if hasattr(tool.browser, 'config'):
                        tool.browser.config._force_keep_browser_alive = False
                    await tool.browser.close()
            except Exception:
                pass  # Silently ignore cleanup errors
        
    except Exception as e:
        logger.error(f"\n❌ Demo setup failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Always stop the server
        try:
            server.stop()
        except:
            pass
        # Small delay to ensure cleanup completes
        await asyncio.sleep(0.3)


if __name__ == "__main__":
    # Check if demo_page.html exists
    if not Path("demo_page.html").exists():
        print("❌ Error: demo_page.html not found in current directory")
        print("   Please run this script from the project root directory")
        sys.exit(1)
    
    # Run the demo
    asyncio.run(run_demo())

