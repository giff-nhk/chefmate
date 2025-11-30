import streamlit as st
import google.generativeai as genai
from gtts import gTTS
from PIL import Image
import io
import re

# --- CONFIGURATION & SETUP ---
st.set_page_config(
    page_title="ChefMate AI",
    page_icon="🍳",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- API KEY MANAGEMENT (SECRETS) ---
# Instead of hardcoding, we fetch the key from Streamlit secrets
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except (FileNotFoundError, KeyError):
    st.error("⚠️ API Key not found! Please set `GEMINI_API_KEY` in your `.streamlit/secrets.toml` file or Streamlit Cloud Secrets.")
    st.stop()

# Configure Gemini
try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')
except Exception as e:
    st.error(f"Error configuring API: {e}")

# --- SESSION STATE INITIALIZATION ---
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "👋 Hi! I'm ChefMate. I can see ingredients, hear your questions, and speak any language. What are we cooking?"}
    ]

if "latest_audio_text" not in st.session_state:
    st.session_state.latest_audio_text = None
    st.session_state.latest_audio_lang = 'en'

if "input_id" not in st.session_state:
    st.session_state.input_id = 0

if "editing_index" not in st.session_state:
    st.session_state.editing_index = None

if "trigger_generation" not in st.session_state:
    st.session_state.trigger_generation = False

if "current_audio" not in st.session_state:
    st.session_state.current_audio = None
    
if "current_images" not in st.session_state:
    st.session_state.current_images = None

# --- THEME CSS GENERATOR ---
def get_css(theme):
    if theme == "dark":
        return """
        <style>
            /* Dark Theme Colors */
            .stApp { background-color: #212121; color: #ffffff; }
            .stChatMessage { background-color: #2f2f2f; border-radius: 15px; padding: 10px; margin-bottom: 10px; border: none; }
            .stChatMessage[data-testid="stChatMessageUser"] { background-color: #2f2f2f; }
            .stChatMessage[data-testid="stChatMessageAvatarAssistant"] { background-color: #2f2f2f; }
            .stTextInput input, .stTextArea textarea, .stChatInput textarea { background-color: #2f2f2f !important; color: white !important; border: 1px solid #444 !important; border-radius: 25px !important; }
            [data-testid="stSidebar"] { background-color: #171717; }
            h1, h2, h3 { color: #ECECEC !important; }
            
            /* Custom Buttons (Dark - Minimalist) */
            [data-testid="stPopover"] > button { 
                border: none; background-color: transparent; color: #b4b4b4; 
            }
            [data-testid="stPopover"] > button:hover { 
                background-color: #2f2f2f; color: white;
            }
            [data-testid="stAudioInput"] { 
                background-color: transparent; border: none; color: #b4b4b4; 
            }
            [data-testid="stAudioInput"]:hover { 
                background-color: #2f2f2f; color: white;
            }
            /* Edit Button Style */
            .edit-btn { color: #888; border: none; background: transparent; cursor: pointer; }
            .edit-btn:hover { color: white; }
        </style>
        """
    else:
        return """
        <style>
            /* Light Theme Colors */
            .stApp { background-color: #ffffff; color: #000000; }
            .stChatMessage { background-color: #f7f7f8; border-radius: 15px; padding: 10px; margin-bottom: 10px; border: none; }
            .stChatMessage[data-testid="stChatMessageUser"] { background-color: #f7f7f8; }
            .stTextInput input, .stTextArea textarea, .stChatInput textarea { background-color: #ffffff !important; color: black !important; border: 1px solid #ccc !important; border-radius: 25px !important; }
            [data-testid="stSidebar"] { background-color: #f9f9f9; }
            h1, h2, h3 { color: #333 !important; }
            
            /* Custom Buttons (Light - Minimalist) */
            [data-testid="stPopover"] > button { 
                border: none; background-color: transparent; color: #666; 
            }
            [data-testid="stPopover"] > button:hover { 
                background-color: #f0f0f0; color: black;
            }
            [data-testid="stAudioInput"] { 
                background-color: transparent; border: none; color: #666; 
            }
            [data-testid="stAudioInput"]:hover { 
                background-color: #f0f0f0; color: black;
            }
        </style>
        """

# Shared CSS for Layout & Alignment
st.markdown("""
    <style>
        audio { width: 100%; height: 40px; margin-top: 10px; }
        
        /* GENERAL BUTTON SIZING */
        [data-testid="stPopover"] > button {
            height: 50px; 
            width: 50px; 
            font-size: 24px; 
            border-radius: 50%; /* Circle shape like icons */
            padding: 0;
            display: flex; 
            align-items: center; 
            justify-content: center; 
            transition: all 0.2s ease;
        }

        /* MIC BUTTON TWEAKS */
        .stAudioInput { 
            margin-top: 0px !important; 
            width: 50px !important; 
            height: 50px !important;
        }
        
        [data-testid="stAudioInput"] {
            height: 50px !important; 
            width: 50px !important; 
            border-radius: 50% !important; /* Circle */
            padding: 0 !important;
            display: flex; 
            align-items: center; 
            justify-content: center; 
            transition: all 0.2s ease;
        }

        /* HIDE TIMER & TEXT IN MIC */
        [data-testid="stAudioInput"] p, 
        [data-testid="stAudioInput"] div[data-testid="stMarkdownContainer"] {
            display: none !important;
        }
        
        /* ICON SIZES */
        [data-testid="stAudioInput"] svg {
            width: 22px !important;
            height: 22px !important;
        }
        
        /* CHAT INPUT PADDING FIX */
        .stChatInput {
            padding-bottom: 5px;
        }
        
    </style>
""", unsafe_allow_html=True)

st.markdown(get_css(st.session_state.theme), unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---

def text_to_speech_autoplay(text, lang='en'):
    try:
        tld_map = {'en': 'com', 'hi': 'co.in', 'kn': 'co.in', 'fr': 'fr', 'es': 'es'}
        tld = tld_map.get(lang, 'com')
        audio_buffer = io.BytesIO()
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        tts.write_to_fp(audio_buffer)
        st.audio(audio_buffer, format='audio/mp3', autoplay=True)
    except Exception as e:
        pass

def get_history_text():
    history_str = "Here is the conversation so far:\n"
    for msg in st.session_state.messages[-6:]:
        role = "User" if msg["role"] == "user" else "Chef"
        content = msg["content"].replace("[Image Uploaded]", "").replace("🎤 [Voice Message Sent]", "")
        history_str += f"{role}: {content}\n"
    return history_str

def stream_gemini_response(current_prompt=None, images=None, audio_bytes=None):
    """
    Generator function for streaming responses
    """
    content_parts = []
    history_context = get_history_text()
    
    system_instruction = """
    You are ChefMate, an expert culinary assistant. 
    1. Detect the language of the user's input.
    2. Respond helpfully in that SAME language.
    3. At the very end of your response, strictly append the ISO-639-1 language code in this format: [[LANG:xx]]
    """
    
    final_prompt = f"{system_instruction}\n\n{history_context}\nUser's Latest Input: "
    if current_prompt: final_prompt += current_prompt
    elif audio_bytes: final_prompt += " (User sent audio, please listen)"
    
    content_parts.append(final_prompt)
    if images:
        for img in images: content_parts.append(img)
    if audio_bytes:
        content_parts.append({"mime_type": "audio/wav", "data": audio_bytes})

    try:
        # Enable streaming
        response_stream = model.generate_content(content_parts, stream=True)
        return response_stream
    except Exception as e:
        return [f"Error: {str(e)}"]

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.title("🍳 Settings")
    
    if st.button("🌞 Light Mode" if st.session_state.theme == "dark" else "🌙 Dark Mode"):
        st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
        st.rerun()
        
    st.divider()
    
    st.info("ℹ️ Language is auto-detected!")
    enable_audio = st.toggle("Enable Voice Response", value=True)
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.session_state.latest_audio_text = None
        st.rerun()

# --- MAIN UI ---
col1, col2 = st.columns([1, 5])
with col1:
    st.markdown("# 🍳")
with col2:
    st.title("ChefMate AI")

# --- CHAT HISTORY WITH EDIT FUNCTION ---
chat_container = st.container()
with chat_container:
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            # Layout: Message Content + Edit Button (if User)
            if msg["role"] == "user":
                # Check if this specific message is being edited
                if st.session_state.editing_index == i:
                    with st.form(key=f"edit_form_{i}"):
                        new_text = st.text_area("Edit your message", value=msg["content"])
                        col_save, col_cancel = st.columns([1, 4])
                        with col_save:
                            if st.form_submit_button("Update"):
                                # Update logic
                                st.session_state.messages[i]["content"] = new_text
                                # Truncate history after this edit
                                st.session_state.messages = st.session_state.messages[:i+1]
                                st.session_state.editing_index = None
                                st.session_state.trigger_generation = True
                                st.rerun()
                        with col_cancel:
                            if st.form_submit_button("Cancel"):
                                st.session_state.editing_index = None
                                st.rerun()
                else:
                    # Normal display with Edit icon
                    # Increased the width of the edit button column to prevent overlap
                    col_txt, col_edit = st.columns([0.85, 0.15])
                    with col_txt:
                        st.markdown(msg["content"])
                    with col_edit:
                        if st.button("✏️", key=f"edit_btn_{i}", help="Edit this message"):
                            st.session_state.editing_index = i
                            st.rerun()
            else:
                # Assistant Message
                st.markdown(msg["content"])

# --- AUDIO PLAYER ---
if enable_audio and st.session_state.latest_audio_text:
    text_to_speech_autoplay(st.session_state.latest_audio_text, lang=st.session_state.latest_audio_lang)
    st.session_state.latest_audio_text = None

# --- PROCESSING & GENERATION LOGIC ---
# We handle generation here so it works for both new inputs AND edits
if st.session_state.trigger_generation:
    # Get the last user message to use as context/prompt trigger
    last_user_msg = st.session_state.messages[-1]
    
    # Placeholder for streaming
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        detected_lang = 'en'
        
        # Call Streaming API
        stream = stream_gemini_response(
            audio_bytes=st.session_state.current_audio,
            images=st.session_state.current_images
        )
        
        for chunk in stream:
            if chunk.text:
                full_response += chunk.text
                response_placeholder.markdown(full_response + "▌")
        
        # Clean up final text
        match = re.search(r'\[\[LANG:([a-zA-Z]+)\]\]', full_response)
        if match:
            detected_lang = match.group(1).lower()
            full_response = full_response.replace(match.group(0), "").strip()
        
        response_placeholder.markdown(full_response)
    
    # Save to history
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.session_state.latest_audio_text = full_response
    st.session_state.latest_audio_lang = detected_lang
    st.session_state.trigger_generation = False
    
    # Clear temp media data after usage
    st.session_state.current_audio = None
    st.session_state.current_images = None
    
    st.rerun()

# --- INPUT AREA ---
# Sticking to bottom logic with columns
st.divider()

# Layout: [ + Button ] [ Chat Input ] [ Mic Button ]
input_cols = st.columns([1, 15, 1], vertical_alignment="bottom") 

uploaded_files = []
audio_input = None

with input_cols[0]:
    # Plus button for Upload
    with st.popover("➕", use_container_width=True):
        uploaded_files = st.file_uploader("Upload", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key=f"img_upload_{st.session_state.input_id}")

with input_cols[1]:
    # Main Chat Input
    text_input = st.chat_input("Ask anything...")

with input_cols[2]:
    # Mic Button
    audio_input = st.audio_input("Mic", label_visibility="collapsed", key=f"audio_input_{st.session_state.input_id}")

# --- NEW INPUT HANDLER ---
if text_input or audio_input:
    user_msg_content = ""
    
    # Store media in session state for this turn
    if uploaded_files:
        user_msg_content += f"📸 [{len(uploaded_files)} Images] "
        st.session_state.current_images = [Image.open(f) for f in uploaded_files]
    else:
        st.session_state.current_images = None

    if text_input:
        user_msg_content += text_input
    
    # Capture audio data immediately
    if audio_input:
        user_msg_content += "🎤 [Voice Message]"
        st.session_state.current_audio = audio_input.read()
    else:
        st.session_state.current_audio = None

    st.session_state.messages.append({"role": "user", "content": user_msg_content})
    st.session_state.trigger_generation = True
    st.session_state.input_id += 1
    st.rerun()