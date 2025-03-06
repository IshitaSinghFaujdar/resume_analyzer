import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import os
import hashlib
import pdfplumber
from io import BytesIO
from dotenv import load_dotenv
load_dotenv()
import io

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

def file_exists_in_supabase(file_name, email):
    try:
        response = supabase.storage.from_("resumes").list(f"resumes/{email}/")
        existing_files = [file['name'] for file in response]
        return file_name in existing_files
    except Exception as e:
        st.error(f"Error checking file existence: {e}")
        return False
def get_uploaded_files(email):
    try:
        response = supabase.storage.from_("resumes").list(f"resumes/{email}/")
        return [file["name"] for file in response] if response else []
    except Exception as e:
        st.error(f"Error fetching uploaded files: {e}")
        return []
def delete_file_from_supabase(file_name, email):
    try:
        file_path = f"resumes/{email}/{file_name}"
        supabase.storage.from_("resumes").remove([file_path])

        # Remove the file hash from the database (optional)
        supabase.table("filehashes").delete().eq("file_name", file_name).eq("email", email).execute()
        
        st.success(f"{file_name} deleted successfully!")
    except Exception as e:
        st.error(f"Error deleting {file_name}: {e}")

# Function to store file hash in the database
def store_file_hash_in_database(file_name, file_hash, email):
    try:
        data = {
            "file_name": file_name,
            "file_hash": file_hash,
            "email": email
        }
        response = supabase.table("filehashes").insert(data).execute()
        
        st.success(f"Hash for {file_name} stored successfully in the database!")
    except Exception as e:
        st.error(f"Error storing hash: {e}")

# Function to upload file to Supabase
def upload_file_to_supabase(file, file_name, email):
    try:
        file_content = file.read()  # Read file as bytes
        file_hash = hash_file(file_content)  # Generate hash

        if file_exists_in_supabase(file_name, email):
            st.warning(f"{file_name} already exists in Supabase. Skipping upload.")
        else:
            file_path = f"resumes/{email}/{file_name}"
            response = supabase.storage.from_("resumes").upload(file_path, file_content)
            st.success(f"{file_name} uploaded successfully!")

        # Store file hash in database
        store_file_hash_in_database(file_name, file_hash, email)

    except Exception as e:
        st.error(f"Error uploading {file_name}: {e}")



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
if st.session_state.get("user"):  # Ensure user is logged in
    email = st.session_state["user"].email
    st.sidebar.subheader("📂 Your Uploaded Resumes")

    # Retrieve user's uploaded files
    uploaded_files = get_uploaded_files(email)

    if uploaded_files:
        selected_file = st.sidebar.selectbox("Select a file:", uploaded_files)
        file_path = f"https://your-supabase-url/storage/v1/object/public/resumes/{email}/{selected_file}"
        #st.sidebar.markdown(f"[📥 Download {selected_file}]( {file_path} )", unsafe_allow_html=True)

        if st.sidebar.button("🗑️ Delete File"):
            delete_file_from_supabase(selected_file, email)
            st.rerun()
    else:
        st.sidebar.info("No resumes uploaded yet.")

    # File upload handling
    st.subheader("📤 Upload Resume")
    uploaded_file = st.file_uploader("Upload Resume (PDF)", type="pdf")
    
    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        file_hash = hash_file(file_bytes)

        if file_hash_exists(file_hash):
            st.warning("This resume has already been uploaded.")
        else:
            if st.checkbox("Upload to Supabase"):
                upload_file_to_supabase(uploaded_file, uploaded_file.name, email)
                st.rerun()

    # Resume analysis section
    if uploaded_files:
        st.subheader(f"📜 Selected Resume: {selected_file}")

        # Fetch the file from Supabase
        response = supabase.storage.from_("resumes").download(f"resumes/{email}/{selected_file}")
        
        if response:
            file_bytes = response
            resume_text = extract_text_from_pdf(BytesIO(file_bytes))

            st.subheader("🔍 Extracted Resume Text")
            st.text_area("Resume Content", resume_text, height=200)

            job_description = st.text_area("Paste Job Description", height=200)
            if resume_text and job_description and st.button("Analyze Resume"):
                with st.spinner("Analyzing..."):
                    feedback = analyze_resume(resume_text, job_description)
                    st.subheader("📝 Analysis & Feedback")
                    st.write(feedback)
else:
    st.warning("Please log in to upload or manage resumes.")
