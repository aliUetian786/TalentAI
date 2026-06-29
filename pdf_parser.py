import pdfplumber
import re
import os

def extract_text_from_pdf(pdf_path):
    """
    Extracts raw text from a PDF file.
    """
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        # Fallback using pypdf if pdfplumber fails
        try:
            import pypdf
            reader = pypdf.PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as ex:
            print(f"Fallback pypdf also failed: {ex}")
            
    return clean_text(text)

def clean_text(text):
    """
    Cleans the extracted text by removing multiple whitespaces,
    correcting encoding, and normalizing line endings.
    """
    if not text:
        return ""
    # Normalize whitespaces
    text = re.sub(r'\s+', ' ', text)
    # Remove non-printable characters or fix common encoding issues
    text = text.encode('ascii', 'ignore').decode('ascii')
    return text.strip()

def parse_contact_info_fallback(text):
    """
    A rule-based fallback parser for basic information if the AI model is not available
    or fails. It extracts email, phone, and name.
    """
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    
    email_match = re.search(email_pattern, text)
    phone_match = re.search(phone_pattern, text)
    
    email = email_match.group(0) if email_match else "Unknown"
    phone = phone_match.group(0) if phone_match else "Unknown"
    
    # Simple name extraction heuristic (first 2-3 words, capitalized)
    name = "Unknown"
    words = text.split()
    if len(words) > 2:
        candidate_words = []
        for word in words[:10]:  # Look at first 10 words
            clean_word = re.sub(r'[^a-zA-Z]', '', word)
            if clean_word and clean_word[0].isupper():
                candidate_words.append(clean_word)
                if len(candidate_words) == 2:
                    break
        if len(candidate_words) >= 2:
            name = " ".join(candidate_words)
            
    return {
        "name": name,
        "email": email,
        "phone": phone
    }
