import json, ast, textwrap, requests, streamlit as st
from datetime import datetime

# =============================================================================
# BUSINESS-SPECIFIC CONFIGURATION BLOCK
# Replace everything in this block to change to a different type of salesman
# =============================================================================

# Business Information
# TODO: Replace these 4 fields to change your salesperson's identity and business type
BUSINESS_NAME = "Toyota"  # Your company name (appears in messages and titles)
BUSINESS_EMOJI = "🚗"  # Single emoji representing your business (🍕 for pizza, 📚 for books, etc.)
SALESMAN_TITLE = "Toyota Sales Specialist"  # Job title shown at top of page
GREETING = "Hi! I'm here to help you find your perfect Toyota. Let's make this easy and enjoyable!"  # Welcome message customers see

# Product Inventory/Knowledge Base
# TODO: Replace this inventory with your own business products!
# 
# Format explanation (follow this EXACT pattern):
# ProductName | Category | Price | Spec1: value | Features: feature1, feature2, feature3
#
# Field breakdown:
# • ProductName: Short name (no spaces work best, like "iPhone15" or "Camry")
# • Category: What type of product (like "Smartphone", "Sedan", "Laptop") 
# • Price: Just the number, no $ sign or commas (like 21000, not $21,000)
# • Spec1: Any technical spec relevant to your business (MPG for cars, Storage for phones, etc.)
# • Features: List 2-4 key selling points separated by commas
#
# Organize products into ## Categories for better readability.
# The AI will use this data to:
#   - Answer questions about products and prices  
#   - Make recommendations based on customer needs
#   - Compare different options
#   - Quote accurate prices during sales process
#
# Example for different businesses:
# Pizza Shop: "Margherita | Classic Pizza | 12 | Size: 14-inch | Features: Fresh mozzarella, basil, tomato sauce"
# Bookstore: "HarryPotter1 | Fantasy Novel | 15 | Pages: 309 | Features: Bestseller, Young Adult, Magic adventure"

DEFAULT_KB = textwrap.dedent("""
# TOYOTA VEHICLE INVENTORY

## Sedans
Corolla | Compact Sedan | 21000 | MPG: 32/41 | Features: TSS 2.0, 8" touchscreen, Apple CarPlay
Camry   | Midsize Sedan | 26000 | MPG: 28/39 | Features: TSS 2.5+, 9" touchscreen, Leather available
Crown   | Premium Sedan | 40000 | MPG: 41/41 | Features: Hybrid standard, AWD, Premium audio

## SUVs
RAV4       | Compact SUV   | 28500 | MPG: 27/35 | Features: AWD available, 8.1" ground clearance
Highlander | 3-Row SUV     | 38000 | MPG: 24/32 | Features: 8 seats, 5000lb towing capacity
4Runner    | Off-Road SUV  | 40000 | MPG: 16/19 | Features: 4WD, Crawl Control, Locking rear diff
Venza      | Luxury SUV    | 35000 | MPG: 40/37 | Features: Hybrid only, Star Gaze roof available

## Trucks
Tacoma  | Midsize Truck | 32000 | MPG: 20/23 | Features: 6400lb towing, Multi-terrain select
Tundra  | Full-Size     | 40000 | MPG: 18/24 | Features: 12000lb towing, CrewMax available

## Hybrids/Electric
Prius      | Hybrid Hatch  | 28000 | MPG: 57/56 | Features: AWD available, Solar roof option
Sienna     | Hybrid Minivan| 38000 | MPG: 36/36 | Features: AWD standard, 8 passengers
bZ4X       | Electric SUV  | 43000 | Range: 252mi | Features: X-MODE AWD, 10yr battery warranty
""").strip()

# Customer Profile Fields
# TODO: Customize what info to track about customers (these become variables the AI can reference)
CUSTOMER_PROFILE_FIELDS = {
    "interested_items": [],      # What products they're interested in
    "budget_range": None,        # Their budget range
    "preferences": [],           # What features/qualities they want
    "stage": "discovery"         # Where they are in the sales process (discovery/comparison/negotiation/closing)
}

# Sales Topics
# TODO: Define what your salesperson can discuss (keeps conversations focused)
ALLOWED_TOPICS = (
    "product exploration, product comparison, feature details, pricing and discounts, "
    "trade-in evaluation, purchase process, delivery timeline, warranty information, "
    "and closing the sale"
)

# TODO: List topics to redirect away from (prevents complex discussions your AI can't handle)
FORBIDDEN_TOPICS = (
    "financing, loans, interest rates, monthly payments, credit checks, lease terms, "
    "APR, payment plans, down payments, payment method discussions, contact details, "
    "scheduling test drives, delivery arrangements, paperwork, insurance, registration, "
    "service appointments, or any post-purchase logistics"
)


# Predefined Action Responses
# TODO: Customize scripted responses for consistent handling of common situations
# Why use these? Some conversations need predictable, professional responses rather than 
# unpredictable AI creativity. These ensure your salesperson always handles difficult 
# situations the same way (like when customers go off-topic or ask forbidden questions).
# 
# The AI decides when to use these based on SYSTEM_PROMPT instructions below. When the AI
# returns action="fallback" (for example), the render() function shows the exact scripted
# message instead of whatever the AI wrote.
#
# Format: Each action needs "message" (what to say) and "next_steps" (2 options for customer)
PREDEFINED_ACTIONS = {
    "fallback": {
        "message": f"That's interesting! Speaking of interesting, have you seen our latest {BUSINESS_NAME} products? They're really turning heads!",
        "next_steps": ["Explore our product lineup", "Tell me what you're looking for"]
    },
    "forbidden_topic": {
        "message": f"I focus on helping you find the right product and pricing. Let's discuss which {BUSINESS_NAME} features matter most to you!",
        "next_steps": ["Explore product features", "Discuss pricing options"]
    },
    "not_interested": {
        "message": f"I understand! What's most important to you in your next purchase? I'd love to address any concerns about {BUSINESS_NAME}.",
        "next_steps": ["Share your priorities", "Address specific concerns"]
    },
    "negotiation_limit": {
        "message": f"I understand your budget concerns, but this is the lowest we can go. At this price, you're getting incredible value with all the premium features, quality, and {BUSINESS_NAME} reliability included. This really is an exceptional deal.",
        "next_steps": ["Move forward with purchase", "Explore other options"]
    }
}

# Hybrid Actions (use predefined intro + custom AI response)
# TODO: Hybrid actions combine scripted intro with custom AI response (best of both worlds)
HYBRID_ACTIONS = {
    "competitor_mention": f"Great choice to consider! Let me show you how {BUSINESS_NAME} compares - you might be surprised by our advantages. "
}

# Salesman Persona and Behavior
# TODO: This is the SYSTEM_PROMPT - the "personality instructions" sent to the AI with every message
# Think of this as training your AI employee. Everything here determines how your salesperson acts,
# what they can discuss, and how they handle different situations.
#
# Key sections to customize for your business:
# • CORE BEHAVIORS: Change personality traits (friendly vs professional, pushy vs helpful, etc.)
# • SALES PROCESS: Modify the 4-step process for different business types
# • CONVERSATION RULES: Adjust response style and length
# • PREDEFINED RESPONSES: Lists when to use your scripted actions from above (like "fallback", "forbidden_topic"; must match EXACTLY)
# • HYBRID RESPONSES: When to combine scripted intro + custom AI response (like competitor_mention; must match EXACTLY)
# • OUTPUT section: This tells AI what JSON format to return (don't change this part)
#
# The AI uses your ALLOWED_TOPICS, FORBIDDEN_TOPICS, and PREDEFINED_ACTIONS from above to
# know when to switch from creative responses to scripted ones. The render() function then
# displays whatever action the AI chooses.
#
# Important: The {BUSINESS_NAME} and {ALLOWED_TOPICS} get automatically filled in from your
# variables above, so if you change "Toyota" to "Pizza Palace" up top, it updates here too!
SYSTEM_PROMPT = f"""You are an expert {BUSINESS_NAME} sales specialist with 15+ years of experience. Your goal is to guide customers smoothly through the buying journey while building trust and excitement.

IMPORTANT SCOPE RESTRICTIONS:
ALLOWED TOPICS ONLY: {ALLOWED_TOPICS}
FORBIDDEN TOPICS (redirect immediately): {FORBIDDEN_TOPICS}

PREDEFINED RESPONSES: For these situations, use the exact predefined response:
- Off-topic/random questions → Use action="fallback" 
- Financing/payment questions → Use action="forbidden_topic"
- "Not interested" responses → Use action="not_interested"
- After 3+ price objections → Use action="negotiation_limit" (final offer)

NEGOTIATION FLOW: For price objections, follow this sequence:
- 1st price objection → Immediately offer 10% discount with new price
- 2nd price objection → Offer small additional discount (2-3%) 
- 3rd+ price objection → Use action="negotiation_limit" (no more discounts)

HYBRID RESPONSES: For these situations, start with the predefined intro then add your custom response:
- Competitor mentions → Use action="competitor_mention" + add specific comparison details

For all other situations, respond naturally but always within allowed topics.

CORE BEHAVIORS:
• Be conversational, warm, and helpful - like a knowledgeable friend, not a pushy salesperson
• Focus on understanding customer needs before making recommendations
• Use the customer's name when provided
• Address concerns honestly and turn objections into opportunities
• Move systematically through stages: discovery → comparison → negotiation → closing
• NEVER give up on a sale - always find a way to re-engage
• STAY WITHIN ALLOWED TOPICS - redirect forbidden topic discussions immediately

SALES PROCESS:
1. DISCOVERY: Understand needs, budget, timeline, and priorities
2. COMPARISON: Show 2-3 relevant products, highlight unique benefits
3. NEGOTIATION: Present pricing, discuss discounts if needed, handle objections
4. CLOSING: When customer says "I'll take it", "let's buy it", "confirm purchase" or similar → Use action="confirm" immediately

PURCHASE COMPLETION RULE:
When customer expresses clear intent to buy (words like "confirm", "purchase", "buy it", "I'll take it"), use action="purchase_confirm" first to show purchase summary, then wait for final confirmation.

PURCHASE CONFIRMATION FLOW:
1. Customer shows interest in product → MUST use action="quote" with specific price first
2. After price is quoted, customer says "I'll take it" → Use action="purchase_confirm" with summary and ask "Ready to complete your purchase?" Include data with "product" and "price" fields
3. Customer confirms → Use action="confirm" with: "Congratulations on your purchase of [PRODUCT] for $[PRICE]! We are glad you chose {BUSINESS_NAME} and know you'll love your new [PRODUCT]. Your purchase is complete!"
Then include NO next_steps array to end the conversation.

CONVERSATION RULES:
• Always end messages with EXACTLY TWO clear, numbered next steps (do NOT number them yourself)
• Keep responses concise (3-4 sentences max) but informative
• Use customer profile data to personalize recommendations
• NEVER accept defeat - always provide a path forward
• When customer shows buying signals, move confidently toward closing
• Turn every objection into an opportunity to highlight {BUSINESS_NAME} value
• NEGOTIATION FLOW: 1st price objection → offer 10% discount immediately, 2nd objection → offer additional small discount, 3rd+ objection → use action="negotiation_limit"
• FORMATTING RULE: Use only plain text for numbers. Write prices and numbers as simple text like $50,000 or 50,000 without any formatting, commas, latex, italics, or special characters
• CRITICAL: Only discuss total price, discounts, and final cost - NEVER financing, payments, loans, or payment methods
• Redirect financing/payment questions immediately back to product features and total pricing

Knowledge Base:
{{KB_CONTENT}}

OUTPUT: Return ONLY valid JSON with these fields:
- "action": the type of response (explore, compare, recommend, quote, negotiate, close, confirm, purchase_confirm, etc.)
- "stage": current sales stage (discovery, comparison, negotiation, closing, confirmation)
- "message": your response to the customer
- "next_steps": array of exactly 2 options for the customer
- "customer_update": object with any updates to customer profile (interested_items, budget_range, preferences)
- "data": object with relevant data like prices, product names, etc.
"""

# Success Messages
PURCHASE_SUCCESS_TITLE = f"🎊 Sale Complete!"
PURCHASE_SUCCESS_MESSAGE = f"Thank you for choosing {BUSINESS_NAME}! We appreciate your business and hope you enjoy your new purchase."

# Chat Input Placeholders
CHAT_PLACEHOLDER_READY = "What can I help you find today?"
CHAT_PLACEHOLDER_NO_API = "Please enter a valid API key to start chatting..."

# Button Labels
RESET_BUTTON_LABEL = "🔄 Reset Conversation"
FINAL_RESET_BUTTON_LABEL = "Start New Sale"

# =============================================================================
# END BUSINESS-SPECIFIC CONFIGURATION BLOCK
# =============================================================================

# Initialize session state
if "docs" not in st.session_state:
    st.session_state.docs = DEFAULT_KB
if "messages" not in st.session_state:
    st.session_state.messages = []
if "customer_profile" not in st.session_state:
    st.session_state.customer_profile = CUSTOMER_PROFILE_FIELDS.copy()
if "quote_history" not in st.session_state:
    st.session_state.quote_history = []
if "sale_completed" not in st.session_state:
    st.session_state.sale_completed = False
if "api_key_valid" not in st.session_state:
    st.session_state.api_key_valid = None
if "saved_api_key" not in st.session_state:
    st.session_state.saved_api_key = ""

# Page configuration
st.set_page_config(page_title=SALESMAN_TITLE, page_icon=BUSINESS_EMOJI)
st.sidebar.title("Configuration")

# API Key input with validation
api_key = st.sidebar.text_input("OpenAI API Key", 
                                value=st.session_state.saved_api_key,
                                type="password", 
                                help="Enter your OpenAI API key")

# Save API key to session state when changed
if api_key != st.session_state.saved_api_key:
    st.session_state.saved_api_key = api_key

# Reset Dialogue Button in sidebar
st.sidebar.markdown("---")
if st.sidebar.button(RESET_BUTTON_LABEL, type="secondary", use_container_width=True, help="Start a fresh conversation while keeping your API key"):
    # Save API key before reset
    saved_key = st.session_state.saved_api_key
    # Reset conversation state
    st.session_state.messages = []
    st.session_state.customer_profile = CUSTOMER_PROFILE_FIELDS.copy()
    st.session_state.quote_history = []
    st.session_state.sale_completed = False
    # Restore API key
    st.session_state.saved_api_key = saved_key
    st.rerun()

# API Key validation
def validate_api_key(key):
    """Validate OpenAI API key format and basic structure"""
    if not key:
        return False, "Please enter your OpenAI API key"
    
    expected_prefix = "sk" + "-"  
    if not key.startswith(expected_prefix):
        return False, f"Invalid API key format. OpenAI keys start with '{expected_prefix}'"
    
    if len(key) < 20:
        return False, "API key appears too short. Please check your key"
    
    return True, "Key format looks valid"

# Check API key validity
if api_key:
    is_valid, message = validate_api_key(api_key)
    if not is_valid:
        st.sidebar.error(f"❌ {message}")
        st.session_state.api_key_valid = False
    else:
        st.sidebar.success("✅ API key format valid")
        st.session_state.api_key_valid = True
else:
    st.sidebar.warning("⚠️ API key required")
    st.session_state.api_key_valid = False

# Show customer profile in sidebar
if st.session_state.customer_profile.get("interested_items"):
    st.sidebar.markdown("### Customer Profile")
    st.sidebar.write(f"Stage: **{st.session_state.customer_profile['stage'].title()}**")
    st.sidebar.write(f"Interested in: {', '.join(st.session_state.customer_profile['interested_items'])}")
    if st.session_state.customer_profile.get("budget_range"):
        st.sidebar.write(f"Budget: {st.session_state.customer_profile['budget_range']}")

# Show recent quotes in sidebar
if st.session_state.quote_history:
    st.sidebar.markdown("### Recent Quotes")
    for q in st.session_state.quote_history[-3:]:
        st.sidebar.info(f"{q.get('item', 'Item')}: ${q.get('price', 0)}")

# Main page header
st.title(f"{BUSINESS_EMOJI} {SALESMAN_TITLE}")
st.caption(GREETING)

# Show API key requirement message if not valid
if not st.session_state.api_key_valid:
    st.warning(f"🔑 **API Key Required**: Please enter a valid OpenAI API key in the sidebar to start chatting with your {BUSINESS_NAME} sales specialist.")

# AI Configuration
model = "gpt-4o"
temp = 0.3

def sys_msg():
    kb_with_profile = st.session_state.docs
    if st.session_state.customer_profile.get("interested_items"):
        kb_with_profile += f"\n\nCUSTOMER PROFILE:\n{json.dumps(st.session_state.customer_profile, indent=2)}"
    return {"role": "system", "content": SYSTEM_PROMPT.replace("{KB_CONTENT}", kb_with_profile)}

def parse_obj(txt):
    try:
        return json.loads(txt)
    except Exception:
        try:
            return ast.literal_eval(txt)
        except Exception:
            return None

def call_llm(msgs):
    """Enhanced LLM call function with comprehensive error handling"""
    if not api_key:
        st.error("❌ **API Key Missing**: Please enter your OpenAI API key in the sidebar to continue.")
        return None
    
    if not st.session_state.api_key_valid:
        st.error("❌ **Invalid API Key**: Please check your OpenAI API key format and try again.")
        return None
    
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "response_format": {"type": "json_object"},
                "messages": msgs,
                "temperature": temp
            },
            timeout=60
        )
        r.raise_for_status()
        
    except requests.exceptions.HTTPError as e:
        if hasattr(e.response, 'status_code'):
            if e.response.status_code == 401:
                st.error("🔐 **Authentication Failed**: Your API key is invalid or expired. Please check your OpenAI API key.")
                st.session_state.api_key_valid = False
            elif e.response.status_code == 429:
                st.error("⏱️ **Rate Limited**: Too many requests. Please wait a moment and try again.")
            else:
                st.error(f"🌐 **API Error**: HTTP {e.response.status_code} - Please try again later.")
        else:
            st.error(f"🌐 **API Request Failed**: {str(e)}")
        return None
        
    except requests.exceptions.RequestException as e:
        st.error(f"🔗 **Network Error**: {str(e)}")
        return None

    try:
        response_data = r.json()
        if 'choices' not in response_data or not response_data['choices']:
            st.error("❌ **Invalid Response**: No response from AI model.")
            return None
        return response_data["choices"][0]["message"]["content"].strip()
        
    except Exception as e:
        st.error(f"❌ **Unexpected Error**: {str(e)}")
        return None
    
def update_customer_profile(data):
    if "customer_update" in data:
        update = data["customer_update"]
        for key, value in update.items():
            if key in st.session_state.customer_profile and value:
                st.session_state.customer_profile[key] = value
    
    if "stage" in data:
        st.session_state.customer_profile["stage"] = data["stage"]
    
    # Check for sale completion (more specific triggers)
    if (data.get("action") == "confirm" and 
        ("congratulations" in data.get("message", "").lower() and
         "purchase" in data.get("message", "").lower() and
         "complete" in data.get("message", "").lower())):
        st.session_state.sale_completed = True
        # Force rerun to immediately update UI
        st.rerun()

def render(d):
    msg = d.get("message", "")
    act = d.get("action", "reply")
    data = d.get("data", {})
    
    update_customer_profile(d)
    
    # Check for hybrid actions first (predefined intro + custom AI response)
    if act in HYBRID_ACTIONS:
        intro = HYBRID_ACTIONS[act]
        # Combine predefined intro with AI's custom response
        full_message = intro + msg
        st.info(f"📊 {full_message}")
        
        # Show AI's custom next steps
        if "next_steps" in d and d["next_steps"]:
            st.markdown("**Your options:**")
            for i, step in enumerate(d["next_steps"], 1):
                st.markdown(f"{i}. {step}")
        return
    
    # Check for fully predefined actions
    if act in PREDEFINED_ACTIONS:
        predefined = PREDEFINED_ACTIONS[act]
        msg = predefined["message"]
        # Show predefined message with special styling
        if act == "fallback":
            st.error(f"↩️ {msg}")
        elif act == "forbidden_topic":
            st.warning(f"🔄 {msg}")
        elif act == "negotiation_limit":
            st.warning(f"⛔ {msg}")
        elif act in ["not_interested"]:
            st.info(f"💡 {msg}")
        
        # Show predefined next steps
        st.markdown("**Your options:**")
        for i, step in enumerate(predefined["next_steps"], 1):
            st.markdown(f"{i}. {step}")
        return
    
    # Default action-based styling for custom responses
    if act == "purchase_confirm":
        st.warning("📋 **PURCHASE CONFIRMATION**")
        st.write(msg)
        # Add purchase summary if available
        if data.get("product") and data.get("price"):
            st.success(f"**Product:** {data['product']}")
            st.success(f"**Final Price:** ${data['price']}")
    elif act in ["quote"]:
        st.success(f"💰 {msg}")
    elif act == "compare":
        st.info(f"📊 {msg}")
    elif act == "negotiate":
        st.warning(f"🤝 {msg}")
    elif act in ["close", "confirm"]:
        st.success(f"✨ {msg}")
        if act == "confirm":
            st.balloons()
    elif act == "recommend":
        st.info(f"⭐ {msg}")
    elif act in ["objection"]:
        st.warning(f"💡 {msg}")
    else:
        st.write(msg)
    
    # Save quote information - fix data extraction
    if act in ["quote", "purchase_confirm"] and data.get("price"):
        # Extract product name from various possible fields
        product_name = "Item"
        if data.get("product"):
            product_name = data["product"]
        elif data.get("models") and isinstance(data["models"], list) and data["models"]:
            product_name = data["models"][0]
        elif data.get("items") and isinstance(data["items"], list) and data["items"]:
            product_name = data["items"][0]
        
        st.session_state.quote_history.append({
            "item": product_name,
            "price": data["price"],
            "timestamp": datetime.now()
        })
    
    # Show next steps (only if not predefined action)
    if "next_steps" in d and d["next_steps"] and act != "confirm":
        st.markdown("**Your options:**")
        for i, step in enumerate(d["next_steps"], 1):
            st.markdown(f"{i}. {step}")

# Display conversation history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Show completion message
if st.session_state.sale_completed:
    st.markdown("---")
    st.success(f"### {PURCHASE_SUCCESS_TITLE}")
    st.info(PURCHASE_SUCCESS_MESSAGE)
    if st.session_state.customer_profile.get("interested_items"):
        st.markdown(f"**Your Purchase:** {st.session_state.customer_profile['interested_items'][-1]}")
    if st.session_state.quote_history:
        latest_quote = st.session_state.quote_history[-1]
        st.markdown(f"**Purchase Price:** ${latest_quote['price']}")

# Chat input
user = st.chat_input(
    CHAT_PLACEHOLDER_READY if st.session_state.api_key_valid else CHAT_PLACEHOLDER_NO_API, 
    disabled=not st.session_state.api_key_valid
)

if user and not st.session_state.sale_completed and st.session_state.api_key_valid:
    st.session_state.messages.append({"role": "user", "content": user})
    with st.chat_message("user"):
        st.markdown(user)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            raw = call_llm([sys_msg()] + st.session_state.messages)
            if raw:
                data = parse_obj(raw)
                if isinstance(data, dict) and "action" in data:
                    render(data)
                    st.session_state.messages.append({"role": "assistant", "content": data.get("message", raw)})
                else:
                    fallback = f"I'd love to help you find the perfect {BUSINESS_NAME} product! How can I assist you today?"
                    st.write(fallback)
                    st.session_state.messages.append({"role": "assistant", "content": fallback})

# Reset button (only show when sale is completed)
if st.session_state.sale_completed:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button(FINAL_RESET_BUTTON_LABEL, type="primary", use_container_width=True):
            # Save API key before reset
            saved_key = st.session_state.saved_api_key
            # Reset conversation state
            st.session_state.messages = []
            st.session_state.customer_profile = CUSTOMER_PROFILE_FIELDS.copy()
            st.session_state.quote_history = []
            st.session_state.sale_completed = False
            # Restore API key
            st.session_state.saved_api_key = saved_key
            st.rerun()