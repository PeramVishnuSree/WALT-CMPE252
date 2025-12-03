import logging
import re
import hashlib
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def truncate_selector(selector: str, max_length: int = 35) -> str:
	"""Truncate a CSS selector to a maximum length, adding ellipsis if truncated."""
	return selector if len(selector) <= max_length else f'{selector[:max_length]}...'


async def get_best_element_handle(page, selector, params=None, timeout_ms=2500):
	"""Find element using stability-ranked selector strategies."""
	original_selector = selector

	# Generate stability-ranked fallback selectors
	fallbacks = generate_stable_selectors(selector, params)

	# Try all selectors with exponential backoff for timeouts
	selectors_to_try = [original_selector] + fallbacks

	for try_selector in selectors_to_try:
		try:
			logger.info(f'Trying selector: {truncate_selector(try_selector)}')
			locator = page.locator(try_selector)
			await locator.wait_for(state='visible', timeout=timeout_ms)
			logger.info(f'Found element with selector: {truncate_selector(try_selector)}')
			return locator, try_selector
		except Exception as e:
			logger.error(f'Selector failed: {truncate_selector(try_selector)} with error: {e}')

	# Try XPath as last resort
	if params and getattr(params, 'xpath', None):
		xpath = params.xpath
		try:
			# Generate stable XPath alternatives
			xpath_alternatives = [xpath] + generate_stable_xpaths(xpath, params)

			for try_xpath in xpath_alternatives:
				xpath_selector = f'xpath={try_xpath}'
				logger.info(f'Trying XPath: {truncate_selector(xpath_selector)}')
				locator = page.locator(xpath_selector)
				await locator.wait_for(state='visible', timeout=timeout_ms)
				return locator, xpath_selector
		except Exception as e:
			logger.error(f'All XPaths failed with error: {e}')

	raise Exception(f'Failed to find element. Original: {original_selector}')


def generate_stable_selectors(selector, params=None):
	"""Generate selectors from most to least stable based on selector patterns."""
	fallbacks = []

	# 1. Extract attribute-based selectors (most stable)
	attributes_to_check = [
		'placeholder',
		'aria-label',
		'name',
		'title',
		'role',
		'data-testid',
	]
	for attr in attributes_to_check:
		attr_pattern = rf'\[{attr}\*?=[\'"]([^\'"]*)[\'"]'
		attr_match = re.search(attr_pattern, selector)
		if attr_match:
			attr_value = attr_match.group(1)
			element_tag = extract_element_tag(selector, params)
			if element_tag:
				fallbacks.append(f'{element_tag}[{attr}*="{attr_value}"]')

	# 2. Combine tag + class + one attribute (good stability)
	element_tag = extract_element_tag(selector, params)
	classes = extract_stable_classes(selector)
	for attr in attributes_to_check:
		attr_pattern = rf'\[{attr}\*?=[\'"]([^\'"]*)[\'"]'
		attr_match = re.search(attr_pattern, selector)
		if attr_match and classes and element_tag:
			attr_value = attr_match.group(1)
			class_selector = '.'.join(classes)
			fallbacks.append(f'{element_tag}.{class_selector}[{attr}*="{attr_value}"]')

	# 3. Tag + class combination (less stable but often works)
	if element_tag and classes:
		class_selector = '.'.join(classes)
		fallbacks.append(f'{element_tag}.{class_selector}')

	# 4. Remove dynamic parts (IDs, state classes)
	if '[id=' in selector:
		fallbacks.append(re.sub(r'\[id=[\'"].*?[\'"]\]', '', selector))

	for state in ['.focus-visible', '.hover', '.active', '.focus', ':focus']:
		if state in selector:
			fallbacks.append(selector.replace(state, ''))

	# 5. Use text-based selector if we have element tag and text
	if params and getattr(params, 'elementTag', None) and getattr(params, 'elementText', None) and params.elementText.strip():
		fallbacks.append(f"{params.elementTag}:has-text('{params.elementText}')")

	return list(dict.fromkeys(fallbacks))  # Remove duplicates while preserving order


def extract_element_tag(selector, params=None):
	"""Extract element tag from selector or params."""
	# Try to get from selector first
	tag_match = re.match(r'^([a-zA-Z][a-zA-Z0-9]*)', selector)
	if tag_match:
		return tag_match.group(1).lower()

	# Fall back to params
	if params and getattr(params, 'elementTag', None):
		return params.elementTag.lower()

	return ''


def extract_stable_classes(selector):
	"""Extract classes that appear stable (not state-related)."""
	# If selector is not a string, return empty list
	if not isinstance(selector, str):
		return []

	class_pattern = r'\.([a-zA-Z0-9_-]+)'
	classes = re.findall(class_pattern, selector)

	# Filter out likely unstable classes
	stable_classes = []
	unstable_patterns = [
		r"focus",
		r"hover",
		r"active",
		r"selected",
		r"checked",
		r"disabled",
		r"loading",
		r"error",
		r"success",
		r"^\d+$",  # Pure numbers
		r"^[a-f0-9]{6,}$",  # Hex codes
		r"css-\w+",  # CSS-in-JS generated classes
		r"^[A-Z0-9]{6,}$",  # Random uppercase sequences like B3R4DD
		r"ui-id-\d+",  # jQuery UI generated classes
		r"^x-\w+\d+",  # ExtJS style generated classes
		r"^\w*\d{3,}$",  # Classes ending with 3+ digits
		r"^gen-\w+",  # Generated classes with gen- prefix
		r"^auto-\w+",  # Auto-generated classes
		r"^tmp-\w+",  # Temporary classes
		r"^dyn-\w+",  # Dynamic classes
	]

	for cls in classes:
		is_stable = True
		for pattern in unstable_patterns:
			if re.search(pattern, cls, re.IGNORECASE):
				is_stable = False
				break

		if is_stable and len(cls) > 1:  # Skip single character classes
			stable_classes.append(cls)

	# Return up to 2 most stable classes to avoid over-specification
	return stable_classes[:2]


def generate_stable_xpaths(xpath, params=None):
	"""Generate stable XPath alternatives."""
	alternatives = []

	# Handle "id()" XPath pattern which is brittle
	if 'id(' in xpath:
		element_tag = getattr(params, 'elementTag', '').lower()
		if element_tag:
			# Create XPaths based on attributes from params
			if params and getattr(params, 'cssSelector', None):
				for attr in ['placeholder', 'aria-label', 'title', 'name']:
					attr_pattern = rf'\[{attr}\*?=[\'"]([^\'"]*)[\'"]'
					attr_match = re.search(attr_pattern, params.cssSelector)
					if attr_match:
						attr_value = attr_match.group(1)
						alternatives.append(f"//{element_tag}[contains(@{attr}, '{attr_value}')]")

	return alternatives


# --- Hash Calculation Utils ---

def calculate_element_hash(dom_element: Any) -> str:
	"""
	Calculate the stable hash for a DOM element.
	Handles both DOMHistoryElement (from agent) and DOMElementNode (from DOM service).
	"""
	try:
		stable_selector = generate_stable_selector(dom_element)
		# Use stable selector for hash generation to ensure consistency
		element_hash = hashlib.sha256(
			f"{dom_element.tag_name}_{stable_selector}".encode()
		).hexdigest()[:10]
		logger.debug(
			f"Generated stable hash {element_hash} from selector: {stable_selector}"
		)
		return element_hash
	except Exception as e:
		# Fallback to original method if stable selector generation fails
		logger.warning(
			f"Failed to generate stable selector for hash, using fallback: {e}"
		)
		
		# Handle different element types
		css_selector = getattr(dom_element, 'css_selector', None)
		
		# If coming from DOMElementNode, we might need to calculate css_selector
		if css_selector is None and hasattr(dom_element, 'attributes') and 'class' in dom_element.attributes:
			# Very basic fallback
			css_selector = f"{dom_element.tag_name}.{'.'.join(dom_element.attributes['class'].split())}"
		
		highlight_index = getattr(dom_element, 'highlight_index', '')
		
		element_hash = hashlib.sha256(
			f"{dom_element.tag_name}_{css_selector}_{highlight_index}".encode()
		).hexdigest()[:10]
		logger.debug(
			f"Generated fallback hash {element_hash} from: {css_selector}[{highlight_index}]"
		)
		return element_hash


def generate_stable_selector(dom_element: Any) -> str:
	"""
	Generate a stable CSS selector from DOM element attributes.
	Prioritizes stable attributes over positional selectors.
	"""
	tag_name = dom_element.tag_name.lower()
	attributes = dom_element.attributes or {}

	# Priority 1: Unique ID (if it looks stable, not auto-generated)
	element_id = attributes.get("id", "").strip()
	if element_id and is_stable_id(element_id):
		return f"#{element_id}"

	# Priority 2: Name attribute (very stable for form elements)
	name_attr = attributes.get("name", "").strip()
	if name_attr:
		# For form elements, name is usually very stable
		if tag_name in ["input", "select", "textarea", "button"]:
			type_attr = attributes.get("type", "").strip()
			if type_attr:
				return f'{tag_name}[name="{name_attr}"][type="{type_attr}"]'
			else:
				return f'{tag_name}[name="{name_attr}"]'

	# Priority 3: Stable attribute combinations
	stable_selector = build_attribute_selector(tag_name, attributes)
	if stable_selector:
		return stable_selector

	# Priority 4: Class-based selector (if classes look stable)
	class_attr = attributes.get("class", "").strip()
	if class_attr:
		stable_classes = extract_stable_classes(class_attr)
		if stable_classes:
			class_selector = "." + ".".join(stable_classes)
			return f"{tag_name}{class_selector}"

	# Priority 5: Fallback to simplified positional selector
	# Use the original selector but try to simplify it
	original_selector = getattr(dom_element, 'css_selector', "")
	simplified = simplify_positional_selector(
		original_selector, tag_name, attributes
	)
	if simplified:
		return simplified

	# Last resort: return original selector or basic tag
	return original_selector or tag_name


def is_stable_id(element_id: str) -> bool:
	"""Check if an ID looks stable (not auto-generated)."""
	# Skip IDs that look auto-generated
	unstable_patterns = [
		r"^[a-f0-9]{8,}$",  # Long hex strings
		r"^\d+$",  # Pure numbers
		r"^id\d+$",  # id123, id456
		r"^_\w+\d+$",  # _element123
		r"react-\w+",  # React generated IDs
		r"mui-\d+",  # Material-UI generated IDs
		r"^ui-id-\d+$",  # jQuery UI generated IDs like ui-id-123
		r"^[A-Z0-9]{6,}$",  # Random uppercase sequences like B3R4DD
		r"^\w*\d{3,}$",  # IDs ending with 3+ digits (likely generated)
		r"^gen-\w+",  # Generated IDs with gen- prefix
		r"^auto-\w+",  # Auto-generated IDs with auto- prefix
	]

	for pattern in unstable_patterns:
		if re.match(pattern, element_id, re.IGNORECASE):
			return False

	return True


def is_stable_attribute_value(value: str) -> bool:
	"""Check if an attribute value looks stable (not auto-generated)."""
	# Skip values that look auto-generated
	unstable_value_patterns = [
		r"^[a-f0-9]{8,}$",  # Long hex strings
		r"^\d+$",  # Pure numbers (likely IDs)
		r"^[A-Z0-9]{6,}$",  # Random uppercase sequences
		r"^ui-id-\d+$",  # jQuery UI generated values
		r"^\w*\d{4,}$",  # Values ending with 4+ digits
		r"^tmp-\w+",  # Temporary values
		r"^gen-\w+",  # Generated values
	]

	for pattern in unstable_value_patterns:
		if re.match(pattern, value, re.IGNORECASE):
			return False

	return True


def build_attribute_selector(tag_name: str, attributes: Dict[str, str]) -> Optional[str]:
	"""Build selector using stable attributes."""
	# Priority attributes for different element types
	stable_attrs = []

	# For form elements
	if tag_name in ["input", "select", "textarea", "button"]:
		for attr in ["placeholder", "aria-label", "title", "role"]:
			value = attributes.get(attr, "").strip()
			if value:
				stable_attrs.append(f'{attr}="{value}"')

	# For interactive elements
	if tag_name in ["button", "a", "div"]:
		for attr in ["aria-label", "role", "data-testid", "title"]:
			value = attributes.get(attr, "").strip()
			if value:
				stable_attrs.append(f'{attr}="{value}"')

	# For rating/icon elements (i, span, etc.)
	if tag_name in ["i", "span"]:
		for attr in [
			"data-value",
			"data-rating",
			"aria-label",
			"title",
			"data-testid",
		]:
			value = attributes.get(attr, "").strip()
			if value:
				stable_attrs.append(f'{attr}="{value}"')

	# Generic data attributes for any element type (fallback)
	if not stable_attrs:
		for attr_name, value in attributes.items():
			if attr_name.startswith("data-") and attr_name in [
				"data-value",
				"data-rating",
				"data-testid",
				"data-qa",
				"data-cy",
				"data-id",
				"data-role",
				"data-action",
			]:
				value = value.strip()
				# Skip dynamic-looking data attribute values
				if value and is_stable_attribute_value(value):
					stable_attrs.append(f'{attr_name}="{value}"')

	# Build selector with most stable attributes
	if stable_attrs:
		# Use up to 2 most specific attributes to avoid over-specification
		selected_attrs = stable_attrs[:2]
		attr_selector = "[" + "][".join(selected_attrs) + "]"
		return f"{tag_name}{attr_selector}"

	return None


def simplify_positional_selector(original_selector: str, tag_name: str, attributes: Dict[str, str]) -> Optional[str]:
	"""Simplify a complex positional selector by removing deep nesting."""
	if not original_selector:
		return None

	# Try to extract the meaningful part of the selector
	# Look for the last part that has the tag and attributes
	parts = original_selector.split(">")

	# Find the part with our target element
	for i in range(len(parts) - 1, -1, -1):
		part = parts[i].strip()
		if tag_name in part:
			# Try to build a simpler selector from this part and maybe 1-2 parents
			simplified_parts = []

			# Add up to 2 parent levels for context
			start_idx = max(0, i - 2)
			for j in range(start_idx, len(parts)):
				part_clean = parts[j].strip()
				# Remove nth-of-type selectors that are too specific
				part_clean = re.sub(r":nth-of-type\(\d+\)", "", part_clean)
				part_clean = re.sub(r":nth-child\(\d+\)", "", part_clean)
				if part_clean:
					simplified_parts.append(part_clean)

			if simplified_parts:
				return " > ".join(simplified_parts)

	return None
