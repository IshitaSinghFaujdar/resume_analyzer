import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import os
import hashlib
import pdfplumber
from io import BytesIO
from dotenv import load_dotenv
load_dotenv()

# --- Initialize Google Gemini AI ---
API_KEY = os.getenv("GEMINI_API_KEY")

# --- Initialize Supabase ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not API_KEY or not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing API keys! Ensure GEMINI_API_KEY, SUPABASE_URL, and SUPABASE_KEY are set in a .env file.")
    st.stop()

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# Configure Gemini AI
genai.configure(api_key=API_KEY)

# --- Helper Functions ---
def hash_file(file_bytes):
    """Generate SHA-256 hash for a file."""
    hasher = hashlib.sha256()
    hasher.update(file_bytes)
    return hasher.hexdigest()

def file_hash_exists(file_hash):
    """Check if a file hash already exists in the database."""
    response = supabase.table("filehashes").select("file_hash").eq("file_hash", file_hash).execute()
    return len(response.data) > 0

def extract_text_from_pdf(uploaded_file):
    """Extract text from a PDF file."""
    with pdfplumber.open(uploaded_file) as pdf:
        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    return text

MAX_FILE_SIZE = 10 * 1024 * 1024 

def upload_file_to_supabase(file_name, file_bytes, email):
    """Upload a file to Supabase storage and debug any errors."""
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

    if len(file_bytes) > MAX_FILE_SIZE:
        st.error(f"File is too large! ({len(file_bytes) / (1024)} KB). Max size: {MAX_FILE_SIZE / (1024)} KB")
        return None

    file_path = f"resumes/{email}/{file_name}"
    try:
        st.write(f"Uploading {file_name} ({len(file_bytes)} bytes) to {file_path}...")
        response = supabase.storage.from_("resumes").upload(file_path, file_bytes)

        st.write(f"Upload response: {response}")  # Print API response for debugging
        return file_path
    except Exception as e:
        st.error(f"Error uploading file: {e}")
        return None



def analyze_resume(file_text, job_description):
    """Analyze resume against job description using Gemini AI."""
    prompt = f"""
    Analyze the following resume in comparison to the job description provided.
    Provide feedback on skill matching, strengths, and improvements.
    
    Resume:
    {file_text}
    
    Job Description:
    {job_description}
    """
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(prompt)
    return response.text if response else "Error generating analysis."

# --- Streamlit UI ---
st.title("📄 AI-Powered Resume Analyzer")

# Sidebar: Authentication
st.sidebar.title("🔐 User Authentication")
if "user" not in st.session_state:
    st.session_state["user"] = None

def login_user(email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response and response.user:
            st.session_state["user"] = response.user
            st.sidebar.success("Login successful!")
        else:
            st.sidebar.error("Invalid credentials.")
    except Exception as e:
        st.sidebar.error(f"Login error: {e}")

def sign_up_user(email, password):
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response and response.user:
            st.sidebar.success("Signup successful! Please check your email for confirmation.")
        else:
            st.sidebar.error("Signup failed.")
    except Exception as e:
        st.sidebar.error(f"Signup error: {e}")

if st.session_state["user"]:
    st.sidebar.write(f"Logged in as: {st.session_state['user'].email}")
    if st.sidebar.button("Logout"):
        st.session_state["user"] = None
else:
    option = st.sidebar.radio("Login or Sign Up", ["Login", "Sign Up"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button(option):
        if option == "Login":
            login_user(email, password)
        else:
            sign_up_user(email, password)

# Main App (Only if logged in)
if st.session_state["user"]:
    email = st.session_state["user"].email
    uploaded_file = st.file_uploader("Upload Resume (PDF)", type="pdf")
    
    if uploaded_file:
        st.subheader("📤 Upload Resume")
        file_bytes = uploaded_file.getvalue()
        file_hash = hash_file(file_bytes)
        
        if file_hash_exists(file_hash):
            st.warning("This resume has already been uploaded.")
        else:
            if st.checkbox("Upload to Supabase"):
                file_path = upload_file_to_supabase(uploaded_file.name, file_bytes, email)
                supabase.table("FileHashes").insert({"email": email, "file_name": uploaded_file.name, "file_hash": file_hash}).execute()
                st.success("Resume uploaded successfully!")

        resume_text = extract_text_from_pdf(BytesIO(file_bytes))
        st.subheader("🔍 Extracted Resume Text")
        st.text_area("Resume Content", resume_text, height=200)
        
        job_description = st.text_area("Paste Job Description", height=200)
        if resume_text and job_description and st.button("Analyze Resume"):
            with st.spinner("Analyzing..."):
                feedback = analyze_resume(resume_text, job_description)
                st.subheader("📝 Analysis & Feedback")
                st.write(feedback)