import os, json, requests, streamlit as st

st.set_page_config(page_title="Client Support Chatbot")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "docs" not in st.session_state:
    st.session_state.docs = ""

st.sidebar.title("Configuration")
api_key = st.sidebar.text_input("OpenAI API Key", type="password")
model = st.sidebar.selectbox("Model", ["gpt-3.5-turbo", "gpt-4o"])
system_prompt = st.sidebar.text_area(
    "System Prompt",
    value="You are a helpful client support agent. Answer queries politely and concisely using the knowledge base when relevant."
)
uploads = st.sidebar.file_uploader(
    "Upload Knowledge Base",
    type=["txt", "md", "csv"],
    accept_multiple_files=True
)

if uploads:
    st.session_state.docs = "\n\n".join(
        f.read().decode(errors="ignore") for f in uploads
    )[:12000]

for role, text in st.session_state.messages:
    st.write(f"**{role.capitalize()}:** {text}")

col1, col2 = st.columns([4, 1])
with col1:
    user_input = st.text_input("Ask a question", key="user_input")
with col2:
    send = st.button("Send")

def build_system(msg, docs):
    return f"{msg}\n\nKnowledge Base:\n{docs}" if docs else msg

if send and user_input:
    st.session_state.messages.append(("user", user_input))
    st.write(f"**User:** {user_input}")

    if not api_key:
        answer = "Please add your OpenAI API key."
    else:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": build_system(system_prompt, st.session_state.docs)}] +
                        [{"role": r, "content": c} for r, c in st.session_state.messages],
            "temperature": 0.3
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, data=json.dumps(payload), timeout=60)
        answer = resp.json()["choices"][0]["message"]["content"].strip() if resp.status_code == 200 else f"Error {resp.status_code}: {resp.text}"

    st.session_state.messages.append(("assistant", answer))
    st.write(f"**Assistant:** {answer}")
