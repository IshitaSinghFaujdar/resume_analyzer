import streamlit as st
import google.generativeai as genai
import fitz  # PyMuPDF to extract text from PDF
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variable
API_KEY = os.getenv("GEMINI_API_KEY")

# Ensure API key is available
if not API_KEY:
    st.error("API key is missing! Please set GEMINI_API_KEY in a .env file.")
    st.stop()

# Set up Gemini API key
genai.configure(api_key=API_KEY)

# Function to extract text from PDF
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    text = "\n".join(page.get_text("text") for page in doc)
    return text

# Function to analyze resume
def analyze_resume(resume_text, job_description):
    prompt = f"""
    Given the following resume text:

    {resume_text}

    And this job description:

    {job_description}

    Analyze the match between the resume and job description.
    - List key skills from the resume.
    - Identify missing skills compared to the job description.
    - Suggest improvements.
    """
    
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(prompt)
    
    return response.text

# Streamlit UI
st.title("📄 AI-Powered Resume Analyzer")
st.write("Upload your resume (PDF) and enter a job description to get feedback.")

# File Upload
uploaded_file = st.file_uploader("Upload Resume (PDF)", type="pdf")
job_description = st.text_area("Paste Job Description", height=200)

if uploaded_file and job_description:
    resume_text = extract_text_from_pdf(uploaded_file)
    st.subheader("🔍 Extracted Resume Text")
    st.text_area("Resume Content", resume_text, height=200)

    if st.button("Analyze Resume"):
        with st.spinner("Analyzing..."):
            feedback = analyze_resume(resume_text, job_description)
            st.subheader("📝 Analysis & Feedback")
            st.write(feedback)
