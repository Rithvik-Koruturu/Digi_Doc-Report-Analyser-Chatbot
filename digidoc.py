from dotenv import load_dotenv
import os
import streamlit as st
import google.generativeai as genai
from google.generativeai import types as generation_types
from PIL import Image
import pdfplumber
import time

# Load environment variables (like your Google API key)
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Check if the API key is set; if not, display an error message
if not api_key:
    st.error("API key is not set. Please check your .env file.")
else:
    # Configure the generative AI models with the provided API key
    genai.configure(api_key=api_key)


def analyze_content_with_flash(content, retries=3):
    """
    Analyzes content using Gemini Flash and provides details.

    Args:
        content (str): Text or image content extracted from uploaded files.
        retries (int): Number of retries in case of failure.

    Returns:
        str: Analyzed content with details or error message.
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    for attempt in range(retries):
        try:
            response = model.generate_content([{"mime_type": "text/plain", "data": content}])
            return response.text
        except generation_types.StopCandidateException:
            st.error("The model did not provide a valid response. Please try again.")
            return ""
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return ""


def extract_text_from_pdf(uploaded_file):
    """
    Extracts text from all pages of a PDF file.

    Args:
        uploaded_file (streamlit.UploadedFile): Uploaded PDF file.

    Returns:
        str: Extracted text from the PDF file.
    """
    extracted_text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page_number, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text and page_text.strip():
                extracted_text += f"\n\nPage {page_number + 1}:\n{page_text}"
    return extracted_text


def handle_image_uploads(uploaded_files):
    """
    Processes uploaded images and analyzes them using Gemini Flash.

    Args:
        uploaded_files (list): List of uploaded images.

    Returns:
        str: Image analysis context from the Gemini Flash model.
    """
    image_context = ""
    for uploaded_file in uploaded_files:
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_column_width=True)

            image_data = input_image_setup(uploaded_file)
            image_context += get_gemini_flash_response("Analyze the image content", image_data)
    return image_context


def input_image_setup(uploaded_file):
    """
    Processes the uploaded image for sending to the Gemini Flash model.

    Args:
        uploaded_file (streamlit.UploadedFile): Uploaded image file.

    Returns:
        list: List containing image data in the required format.
    """
    if uploaded_file is not None:
        bytes_data = uploaded_file.getvalue()
        mime_type = uploaded_file.type
        image_parts = [{"mime_type": mime_type, "data": bytes_data}]
        return image_parts
    else:
        raise FileNotFoundError("No file uploaded")


def get_gemini_flash_response(input_prompt, image_data=None):
    """
    Gets response from the Gemini Flash model for images.

    Args:
        input_prompt (str): Prompt for the Gemini Flash model.
        image_data (list, optional): Image data to be analyzed. Default is None.

    Returns:
        str: Response from the Gemini Flash model.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    if image_data:
        response = model.generate_content([{"mime_type": image_data[0]["mime_type"], "data": image_data[0]["data"]}, {"mime_type": "text/plain", "data": input_prompt}])
        return response.text
    else:
        return "No image data provided."


def get_response_with_context(question, report_text=None, image_context=None):
    """
    Handles user queries with context from reports using Gemini Pro.

    Args:
        question (str): User's query.
        report_text (str, optional): Text extracted from the report. Default is None.
        image_context (str, optional): Image analysis context. Default is None.

    Returns:
        str: Response from the Gemini Pro model.
    """
    combined_context = ""
    if report_text:
        combined_context += f"Report Data: {report_text}\n"
    if image_context:
        combined_context += f"Image Analysis: {image_context}\n"

    final_prompt = f"""
    You are an advanced AI medical assistant. Use the following data extracted from the reports and images 
    to answer the user's question comprehensively. Provide relevant information, possible diagnoses, 
    and suggest specialist doctors if needed.

    {combined_context}

    Question: {question}
    """
    model = genai.GenerativeModel("gemini-pro")
    chat = model.start_chat(history=[])
    response = chat.send_message(final_prompt)
    return response.text


# Streamlit UI
st.header("Report Analyzer Chatbot")

# Add gender input field
gender = st.selectbox("Select the patient's gender:", ("Male", "Female", "Other"))

# Allow multiple images and PDF upload
uploaded_files = st.file_uploader("Upload images or a PDF report...", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)

report_text = ""
image_context = ""
if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.type == "application/pdf":
            report_text += extract_text_from_pdf(uploaded_file)
        else:
            image_context += handle_image_uploads([uploaded_file])

# Process the report content if available
if report_text:
    analysis_response = analyze_content_with_flash(report_text)
    st.subheader("Report Analysis:")
    st.write(analysis_response)

# Process image context if available
if image_context:
    st.subheader("Image Analysis:")
    st.write(image_context)

# Unified input field for additional queries
user_input = st.text_input("Ask a question related to the report or health:")

# Button to get a response
if st.button("Get Response"):
    if user_input:
        response = get_response_with_context(user_input, report_text, image_context)
        st.write(response)
