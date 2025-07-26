import json, ast, textwrap, requests, streamlit as st
from datetime import datetime

# ───────── DEV‑ONLY OPENAI KEY ─────────
API_KEY = "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"

# ───────── Enhanced knowledge base ─────────
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

# ───────── Session state initialization ─────────
if "docs" not in st.session_state:
    st.session_state.docs = DEFAULT_KB
if "messages" not in st.session_state:
    st.session_state.messages = []
if "customer_profile" not in st.session_state:
    st.session_state.customer_profile = {
        "interested_models": [],
        "budget_range": None,
        "priorities": [],
        "stage": "discovery"  # discovery -> comparison -> negotiation -> closing -> completed
    }
if "quote_history" not in st.session_state:
    st.session_state.quote_history = []
if "sale_completed" not in st.session_state:
    st.session_state.sale_completed = False
if "show_balloons" not in st.session_state:
    st.session_state.show_balloons = False

# ───────── Streamlit configuration ─────────
st.set_page_config(page_title="Toyota Sales Specialist", page_icon="🚗")
st.sidebar.title("🎯 Sales Dashboard")

# Customer profile display
if st.session_state.customer_profile["interested_models"]:
    st.sidebar.markdown("### Customer Profile")
    st.sidebar.write(f"Stage: **{st.session_state.customer_profile['stage'].title()}**")
    st.sidebar.write(f"Interested in: {', '.join(st.session_state.customer_profile['interested_models'])}")
    if st.session_state.customer_profile["budget_range"]:
        st.sidebar.write(f"Budget: {st.session_state.customer_profile['budget_range']}")

# Configuration options
st.sidebar.markdown("### Configuration")
model = st.sidebar.selectbox("AI Model", ["gpt-3.5-turbo", "gpt-4o"], index=1)
temp = st.sidebar.slider("Response Style", 0.0, 1.0, 0.3, help="Lower = focused, Higher = creative")
upl = st.sidebar.file_uploader("Upload extra KB", accept_multiple_files=True)
if upl:
    st.session_state.docs += "\n\n" + "\n\n".join(f.read().decode(errors="ignore") for f in upl)[:12000]

# Quote history
if st.session_state.quote_history:
    st.sidebar.markdown("### Recent Quotes")
    for q in st.session_state.quote_history[-3:]:
        st.sidebar.info(f"{q['model']}: ${q['price']:,}")

st.title("🚗 Toyota Sales Specialist")
st.caption("Hi! I'm here to help you find your perfect Toyota. Let's make this easy and enjoyable!")

# ───────── Enhanced JSON schema & actions ─────────
SCHEMA = '''{
  "action": "explore|compare|recommend|quote|negotiate|close|confirm|purchase_confirm|followup|qualify|objection|feature_explain|trade_in|fallback",
  "stage": "discovery|comparison|negotiation|closing|confirmation",
  "data": {
    "models": ["string"],
    "price": "number",
    "discount_percentage": "number",
    "final_price": "number",
    "features": ["string"],
    "competitors": ["string"],
    "trade_in": {"make": "string", "model": "string", "year": "number", "estimate": "string"},
    "transaction_summary": {
      "model": "string",
      "original_price": "number",
      "discount": "number",
      "final_price": "number",
      "incentives": ["string"],
      "total_due": "number"
    }
  },
  "customer_update": {
    "interested_models": ["string"],
    "budget_range": "string",
    "priorities": ["string"],
    "timeline": "string"
  },
  "message": "string",
  "next_steps": ["string", "string"]
}'''

ALLOWED_TOPICS = (
    "vehicle exploration, model comparison, feature details, pricing and discounts, "
    "trade-in evaluation, purchase process, delivery timeline, warranty information, "
    "maintenance plans, and closing the sale"
)

SYSTEM = f"""You are an expert Toyota sales specialist with 15+ years of experience. Your goal is to guide customers smoothly through the buying journey while building trust and excitement.

CORE BEHAVIORS:
• Be conversational, warm, and helpful - like a knowledgeable friend, not a pushy salesperson
• Focus on understanding customer needs before making recommendations
• Use the customer's name when provided
• Address concerns honestly and turn objections into opportunities
• Move systematically through stages: discovery → comparison → negotiation → closing
• NEVER give up on a sale - always find a way to re-engage

SALES PROCESS:
1. DISCOVERY: Understand needs, budget, timeline, and priorities
2. COMPARISON: Show 2-3 relevant models, highlight unique benefits
3. NEGOTIATION: Present pricing, discuss discounts if needed, handle objections
4. CLOSING: After price is established, always push toward purchase completion

ACTION TYPES:
• explore: Initial vehicle discovery and needs assessment
• compare: Side-by-side model comparison with key differentiators
• recommend: Personalized suggestion based on stated needs
• quote: Specific pricing (never mention incentives, financing, or payment terms)
• negotiate: Work through pricing concerns (can offer up to 10% discount for stubborn customers)
• close: Move toward finalizing the sale
• purchase_confirm: Display full transaction details for final approval
• confirm: Final confirmation after purchase_confirm approval
• followup: Check on pending decisions or concerns
• qualify: Assess budget, timeline, and decision authority
• objection: Address specific concerns or hesitations
• feature_explain: Deep dive into specific features/benefits
• trade_in: Evaluate current vehicle and apply value to reduce total price (e.g., "$5,000 trade-in value brings your total to $23,500")
• fallback: Redirect conversations back to Toyota value

PURCHASE CONFIRMATION RULE:
• When customer expresses intent to buy ("ready to buy", "let's purchase", "I'll take it", etc.), ALWAYS use action='purchase_confirm'
• Include complete transaction_summary in data with model, original_price, discount (if any), trade_in_value (if any), final_price, and total_due
• When showing trade-in value in summary, make sure to show it as a negative number (e.g., -$12,000) to indicate it reduces the price
• Message should display formatted transaction details and ask for confirmation
• Next steps: ["Confirm purchase", "Adjust details"]
• When customer confirms the purchase, use action='confirm' with a thank you message and NO next_steps array

FALLBACK STRATEGIES:
• For DISINTEREST ("not interested in Toyota"): Use action='objection', ask "I understand - what's most important to you in your next vehicle?" or "What's holding you back from considering Toyota?"
• For COMPETITOR MENTIONS: Use action='compare', acknowledge and pivot: "Great choice! Let me show you how the Toyota [model] compares - you might be surprised by our advantages"
• For RANDOM/OFF-TOPIC: Use action='fallback', redirect playfully: "That's interesting! Speaking of interesting, have you seen the new Toyota [model]? It's turning heads everywhere"
• For NEGATIVITY: Use action='objection', empathize and probe: "I hear you - what specific concerns do you have? I'd love to address them"
• For PRICE OBJECTIONS: Use action='negotiate', reframe value: "I understand budget is important. Let me see what I can do on the price"
• For TEST DRIVE REQUESTS: Use action='objection', redirect to purchase: "I appreciate your interest! Based on the features we've discussed, are you ready to talk about pricing?"
• For PRE-OWNED/USED REQUESTS: Use action='objection', redirect: "I specialize in new Toyota vehicles which come with full warranty and the latest features. Which new model interests you?"
• NEVER mention financing, incentives, APR, cash back, or payment terms - only discuss total price and discounts

CONVERSATION RULES:
• Always end messages with EXACTLY TWO clear, numbered next steps
• Keep responses concise (3-4 sentences max) but informative
• Use customer profile data to personalize recommendations
• NEVER accept defeat - always provide a path forward
• When customer shows buying signals, move confidently toward closing
• Turn every objection into an opportunity to highlight Toyota value
• NEGOTIATION RULE: If customer is very stubborn on price after 2+ attempts, offer up to 10% discount as "manager's special"
• FORMATTING RULE: Use only plain text for numbers. Write prices and numbers, including trade in values, as simple text like $50,000 or 50,000 without any formatting, latex, italics, or special characters
• CRITICAL: NEVER use these words: financing, incentives, APR, cash back, payment, lease, loan, credit
• Only discuss total price, discounts, and final cost
• SALES PROGRESSION: Once a price is quoted or discount offered, next steps should move toward purchase (e.g., "Move forward with purchase", "Finalize your order") not revisit pricing
• NEVER discuss pre-owned, used, or certified pre-owned vehicles - only sell new Toyota vehicles
• TRADE-IN RULE: When evaluating trade-ins, provide an estimate and apply it directly to reduce the total price. Generate all numbers using plain text, no special formatting.

OUTPUT: Return ONLY valid JSON matching this schema:
{SCHEMA}

Knowledge Base:
{{KB_CONTENT}}"""

def sys_msg():
    kb_with_profile = st.session_state.docs
    if st.session_state.customer_profile["interested_models"]:
        kb_with_profile += f"\n\nCUSTOMER PROFILE:\n{json.dumps(st.session_state.customer_profile, indent=2)}"
    return {"role": "system", "content": SYSTEM.replace("{KB_CONTENT}", kb_with_profile)}

# ───────── Helper functions ─────────
def parse_obj(txt):
    try:
        return json.loads(txt)
    except Exception:
        try:
            return ast.literal_eval(txt)
        except Exception:
            return None

def call_llm(msgs):
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
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
    return r.json()["choices"][0]["message"]["content"].strip()

def update_customer_profile(data):
    """Update customer profile based on AI response"""
    if "customer_update" in data:
        update = data["customer_update"]
        if update.get("interested_models"):
            st.session_state.customer_profile["interested_models"] = update["interested_models"]
        if update.get("budget_range"):
            st.session_state.customer_profile["budget_range"] = update["budget_range"]
        if update.get("priorities"):
            st.session_state.customer_profile["priorities"] = update["priorities"]
    
    if "stage" in data:
        st.session_state.customer_profile["stage"] = data["stage"]
    
    # Check if this is a final confirmation after purchase approval
    if (data.get("action") == "confirm" and 
        ("congratulations" in data.get("message", "").lower() or 
         "purchase is confirmed" in data.get("message", "").lower() or
         "your purchase" in data.get("message", "").lower())):
        st.session_state.sale_completed = True
        st.session_state.show_balloons = True

def render(d):
    """Enhanced message rendering with action-specific formatting"""
    msg = d.get("message", "")
    act = d.get("action", "reply")
    data = d.get("data", {})
    
    # Update customer profile
    update_customer_profile(d)
    
    # Action-specific rendering
    if act == "quote":
        st.success(f"💰 {msg}")
        if data.get("price"):
            st.session_state.quote_history.append({
                "model": data.get("models", ["Unknown"])[0],
                "price": data["price"],
                "timestamp": datetime.now()
            })
    elif act == "purchase_confirm":
        # Display transaction summary
        st.warning("📋 **PURCHASE CONFIRMATION**")
        
        if data.get("transaction_summary"):
            summary = data["transaction_summary"]
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Vehicle Details")
                st.write(f"**Model:** {summary.get('model', 'RAV4')}")
                if summary.get('original_price'):
                    st.write(f"**Original Price:** ${summary.get('original_price', 28500):,}")
                    if summary.get('discount'):
                        st.write(f"**Discount:** -${summary.get('discount', 0):,}")
                    if summary.get('trade_in_value'):
                        st.write(f"**Trade-in Credit:** -${summary.get('trade_in_value', 0):,}")
                st.write(f"**Final Price:** ${summary.get('final_price', summary.get('price', 28500)):,}")
                
            with col2:
                st.markdown("### Payment Details")
                st.write(f"**Total Due at Signing:** ${summary.get('total_due', 2000):,}")
                if summary.get('trade_in_value'):
                    st.write(f"**After Trade-in Applied**")
            
            st.markdown("---")
            
            if summary.get("discount") or summary.get("trade_in_value"):
                st.markdown("### Applied Discounts")
                if summary.get("discount"):
                    st.write(f"✓ Manager's Special: -${summary.get('discount', 0):,}")
                if summary.get("trade_in_value"):
                    st.write(f"✓ Trade-in Value: -${summary.get('trade_in_value', 0):,}")
            
            st.markdown("---")
            st.success(f"**Final Price: ${summary.get('final_price', summary.get('price', 28500)):,}**")
            
        st.write(msg)
    elif act == "compare":
        st.info(f"📊 {msg}")
    elif act == "negotiate":
        st.warning(f"🤝 {msg}")
    elif act == "close":
        st.info(f"✨ {msg}")
    elif act == "confirm":
        if "purchase" in msg.lower() or "thank you" in msg.lower():
            st.balloons()
        st.success(f"🎉 {msg}")
    elif act == "recommend":
        st.info(f"⭐ {msg}")
    elif act == "objection":
        st.warning(f"💡 {msg}")
    elif act == "fallback":
        st.error(f"↩️ {msg}")
    else:
        st.write(msg)
    
    # Show next steps only if present and action is not confirm
    if "next_steps" in d and d["next_steps"] and act != "confirm":
        st.markdown("**Your options:**")
        for i, step in enumerate(d["next_steps"], 1):
            st.markdown(f"{i}. {step}")

# ───────── Display chat history ─────────
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ───────── Sale completed state ─────────
if st.session_state.sale_completed:
    st.markdown("---")
    st.success("### 🎊 Congratulations on your new Toyota!")
    st.info("Thank you for shopping with Toyota! Your sales specialist will contact you within 24 hours to finalize delivery details.")
    
    # Show final summary
    if st.session_state.customer_profile["interested_models"]:
        st.markdown(f"**Your Vehicle:** {st.session_state.customer_profile['interested_models'][-1]}")
    if st.session_state.quote_history:
        latest_quote = st.session_state.quote_history[-1]
        st.markdown(f"**Purchase Price:** ${latest_quote['price']:,}")

# ───────── Main chat interface ─────────
user = st.chat_input("What can I help you find today?")
if user and not st.session_state.sale_completed:  # Only process input if sale not completed
    st.session_state.messages.append({"role": "user", "content": user})
    with st.chat_message("user"):
        st.markdown(user)
    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            raw = call_llm([sys_msg()] + st.session_state.messages)
            data = parse_obj(raw)
            
            if isinstance(data, dict) and "action" in data:
                render(data)
                # Store the full response for context
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data.get("message", raw)
                })
            else:
                # Fallback response
                fallback = "I'd love to help you find the perfect Toyota! Here are your options:\n1. Explore our model lineup\n2. Discuss your specific needs"
                st.write(fallback)
                st.session_state.messages.append({"role": "assistant", "content": fallback})

# Show reset button below chat input if sale is completed
if st.session_state.sale_completed:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Reset Dialogue", type="primary", use_container_width=True):
            # Reset all session state
            st.session_state.messages = []
            st.session_state.customer_profile = {
                "interested_models": [],
                "budget_range": None,
                "priorities": [],
                "stage": "discovery"
            }
            st.session_state.quote_history = []
            st.session_state.sale_completed = False
            st.session_state.show_balloons = False
            st.rerun()

# ───────── Quick action buttons ─────────
if not st.session_state.messages and not st.session_state.sale_completed:
    st.markdown("### Quick Start Options:")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🚙 Browse SUVs"):
            st.session_state.messages.append({"role": "user", "content": "Show me your SUVs"})
            st.rerun()
    with col2:
        if st.button("💰 Best Deals"):
            st.session_state.messages.append({"role": "user", "content": "What are your best deals right now?"})
            st.rerun()
    with col3:
        if st.button("🔍 Help Me Choose"):
            st.session_state.messages.append({"role": "user", "content": "I'm not sure what I need, can you help?"})
            st.rerun()