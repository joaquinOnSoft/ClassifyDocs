import json
import logging
import re

import magic
import ollama
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from pypdf import PdfReader

logging.basicConfig(level=logging.INFO)

# -------------------------------------------------------------
# Extracting text from various file formats
# -------------------------------------------------------------

def extract_text_from_file(file_path: str) -> str:
    """Extract text from a PDF, image or plain text using OCR if necessary."""
    mime = magic.from_file(file_path, mime=True)
    text = ""

    try:
        if mime == "application/pdf":
            # Try direct extraction
            reader = PdfReader(file_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
            # If there is no text, apply OCR
            if not text.strip():
                logging.info("PDF with no detectable text, using OCR")
                images = convert_from_path(file_path)
                for img in images:
                    text += pytesseract.image_to_string(img, lang="spa+eng")
        elif mime.startswith("image/"):
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img, lang="spa+eng")
        elif mime == "text/plain":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            # Fallback: try as an image
            text = pytesseract.image_to_string(Image.open(file_path), lang="spa+eng")
    except Exception as e:
        logging.error(f"Error extracting text: {e}")
        return ""

    return text.strip()

# -------------------------------------------------------------
# Date classification and extraction using LLM
# -------------------------------------------------------------

def classify_text(text: str, categories: list) -> dict:
    """
    Send the text to Ollama (Mistral 7B model) and it returns a dictionary
    with the keys 'category' and 'doc_date'. The model extracts the date from the content.
    """
    # Limitar longitud para evitar sobrecarga del modelo
    #text_limit = text[:3000]
    text_limit = text

    prompt = f"""
        You are an expert document classifier. Your task is:
        1. Assign the following document to ONE of the categories listed.
        2. Extract the DATE from the document (issue date, contract date, invoice date, etc.) in YYYY-MM-DD format.
        
        Categories:
        {chr(10).join(f'- {c}' for c in categories)}
        
        Document:
        \"\"\"{text_limit}\"\"\"
        
        Instructions:
        - Respond ONLY with a valid JSON object,...
        {chr(10).join(f'- {c}' for c in categories)}
        
        Documentt:
        \"\"\"{text_limit}\"\"\"
        
        Instructions:
            - Respond ONLY with a valid JSON object, with no additional text.
            - The JSON must contain exactly two keys: "category" and "doc_date".
            - "category": the exact name of one of the listed categories. If you are unsure, choose the most likely one.
            - "doc_date": the date found in YYYY-MM-DD format. If you cannot find a date, use null.
            - Example response: {{"category": "Factura", "doc_date": "2024-03-15"}}
            - Do not include any explanations; just the JSON.
            - If the category name is included in the file name, use that category for the file.       
        """
    try:
        response = ollama.generate(
            model="mistral:7b-instruct-q4_K_M",
            prompt=prompt,
            format='json'
        )
        raw = response['response'].strip()

        # Extract the first complete JSON block (in case there is noise)
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)

        result = json.loads(raw)

        # Validate and normalise keys
        if 'category' not in result:
            result['categoria'] = "Not classified"
        if 'doc_date' not in result:
            result['doc_date'] = None

        return result
    except Exception as e:
        logging.error(f"Classification error with Ollama: {e}")
        return {"category": "Error", "doc_date": None}