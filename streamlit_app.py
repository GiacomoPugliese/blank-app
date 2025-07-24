import json, ast, textwrap, requests, streamlit as st
from datetime import datetime



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

## Current Incentives
- 0% APR for 60 months on Camry, RAV4, Highlander
- $1000 cash back on Corolla
- $2000 lease bonus on Crown
- College grad rebate: $500 on any model
- Military discount: $500 on any model
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
  "action": "explore|compare|recommend|quote|negotiate|schedule|finance|close|confirm|purchase_confirm|followup|qualify|objection|feature_explain|trade_in|fallback",
  "stage": "discovery|comparison|negotiation|closing|confirmation",
  "data": {
    "models": ["string"],
    "price": "number",
    "monthly_payment": "number",
    "features": ["string"],
    "competitors": ["string"],
    "appointment": {"type": "string", "date": "string", "time": "string"},
    "trade_in": {"make": "string", "model": "string", "year": "number", "estimate": "number"},
    "financing": {"term": "number", "apr": "number", "down_payment": "number"},
    "transaction_summary": {
      "model": "string",
      "price": "number",
      "incentives": ["string"],
      "financing": "string",
      "monthly_payment": "number",
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
    "vehicle exploration, model comparison, feature details, pricing and incentives, "
    "trade-in evaluation, financing options, lease programs, test drive scheduling, "
    "purchase process, delivery timeline, warranty information, maintenance plans, "
    "and closing the sale"
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
3. NEGOTIATION: Present pricing, discuss incentives, handle objections
4. CLOSING: Finalize details, schedule next steps, confirm commitment

ACTION TYPES:
• explore: Initial vehicle discovery and needs assessment
• compare: Side-by-side model comparison with key differentiators
• recommend: Personalized suggestion based on stated needs
• quote: Specific pricing with available incentives
• negotiate: Work through pricing concerns and find solutions
• schedule: Book test drives or appointments
• finance: Discuss payment options and terms
• close: Move toward finalizing the sale
• purchase_confirm: Display full transaction details for final approval
• confirm: Final confirmation after purchase_confirm approval
• followup: Check on pending decisions or concerns
• qualify: Assess budget, timeline, and decision authority
• objection: Address specific concerns or hesitations
• feature_explain: Deep dive into specific features/benefits
• trade_in: Evaluate current vehicle for trade
• fallback: Redirect conversations back to Toyota value

PURCHASE CONFIRMATION RULE:
• When customer expresses intent to buy ("ready to buy", "let's purchase", "I'll take it", etc.), ALWAYS use action='purchase_confirm'
• Include complete transaction_summary in data with model, price, incentives, financing terms, and total
• Message should display formatted transaction details and ask for confirmation
• Next steps: ["Confirm purchase", "Adjust details"]
• Only proceed to action='confirm' if customer explicitly approves the transaction summary

FALLBACK STRATEGIES:
• For DISINTEREST ("not interested in Toyota"): Use action='objection', ask "I understand - what's most important to you in your next vehicle?" or "What's holding you back from considering Toyota?"
• For COMPETITOR MENTIONS: Use action='compare', acknowledge and pivot: "Great choice! Let me show you how the Toyota [model] compares - you might be surprised by our advantages"
• For RANDOM/OFF-TOPIC: Use action='fallback', redirect playfully: "That's interesting! Speaking of interesting, have you seen the new Toyota [model]? It's turning heads everywhere"
• For NEGATIVITY: Use action='objection', empathize and probe: "I hear you - what specific concerns do you have? I'd love to address them"
• For PRICE OBJECTIONS: Use action='negotiate', reframe value: "I understand budget is important. Let's look at our incentives and total cost of ownership"

CONVERSATION RULES:
• Always end messages with EXACTLY TWO clear, numbered next steps
• Keep responses concise (3-4 sentences max) but informative
• Use customer profile data to personalize recommendations
• NEVER accept defeat - always provide a path forward
• Build urgency naturally through limited-time incentives
• When customer shows buying signals, move confidently toward closing
• Turn every objection into an opportunity to highlight Toyota value

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
                st.write(f"**Base Price:** ${summary.get('price', 28500):,}")
                
            with col2:
                st.markdown("### Financing")
                st.write(f"**Terms:** {summary.get('financing', '0% APR for 60 months')}")
                st.write(f"**Monthly Payment:** ${summary.get('monthly_payment', 475):,}")
            
            st.markdown("---")
            
            if summary.get("incentives"):
                st.markdown("### Applied Incentives")
                for incentive in summary["incentives"]:
                    st.write(f"✓ {incentive}")
            
            st.markdown("---")
            st.success(f"**Total Due at Signing:** ${summary.get('total_due', 2000):,}")
            
        st.write(msg)
    elif act == "compare":
        st.info(f"📊 {msg}")
    elif act == "negotiate":
        st.warning(f"🤝 {msg}")
    elif act == "schedule":
        st.success(f"📅 {msg}")
    elif act == "close":
        st.info(f"✨ {msg}")
    elif act == "confirm":
        if "purchase" in msg.lower():
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
    
    # Show next steps
    if "next_steps" in d and d["next_steps"]:
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
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Start New Customer Session", type="primary", use_container_width=True):
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
            st.rerun()
else:
    # ───────── Main chat interface ─────────
    user = st.chat_input("What can I help you find today?")
    if user:
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
                    # Check if we need to rerun after sale completion
                    if st.session_state.sale_completed:
                        st.rerun()
                else:
                    # Fallback response
                    fallback = "I'd love to help you find the perfect Toyota! Here are your options:\n1. Explore our model lineup\n2. Discuss your specific needs"
                    st.write(fallback)
                    st.session_state.messages.append({"role": "assistant", "content": fallback})

    # ───────── Quick action buttons ─────────
    if not st.session_state.messages:
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