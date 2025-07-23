import os, json, requests, streamlit as st

st.set_page_config(page_title="Client Support Chatbot")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "docs" not in st.session_state:
    st.session_state.docs = ""

st.sidebar.title("Configuration")
title = st.sidebar.text_input("Chat Title", value="Client Support Chat")
api_key = st.sidebar.text_input("OpenAI API Key", type="password")
model = st.sidebar.selectbox("Model", ["gpt-3.5-turbo", "gpt-4o"])
system_prompt = st.sidebar.text_area(
    "System Prompt",
    value="You are a helpful client support agent. Answer queries politely and concisely using the knowledge base when relevant."
)
uploaded = st.sidebar.file_uploader(
    "Upload Knowledge Base",
    type=["txt", "md", "csv"],
    accept_multiple_files=True
)

st.title(title)

if uploaded:
    st.session_state.docs = "\n\n".join(f.read().decode(errors="ignore") for f in uploaded)[:12000]

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

user_input = st.chat_input("Ask a question")

def build_system(prompt, docs):
    return f"{prompt}\n\nKnowledge Base:\n{docs}" if docs else prompt

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        if not api_key:
            st.markdown("Please add your OpenAI API key.")
        else:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": build_system(system_prompt, st.session_state.docs)}
                ] + st.session_state.messages,
                "temperature": 0.3
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload),
                timeout=60
            )
            content = resp.json()["choices"][0]["message"]["content"].strip() \
                     if resp.status_code == 200 else f"Error {resp.status_code}: {resp.text}"
            st.markdown(content)
            st.session_state.messages.append({"role": "assistant", "content": content})
