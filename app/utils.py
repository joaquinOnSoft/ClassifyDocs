import json
import logging
import re
from typing import Optional, Literal

import magic
import ollama
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from pypdf import PdfReader
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.DEBUG)

# Define the permitted categories exactly as specified in the question
CategoriaType = Literal[
    "Acuerdo marco",
    "Adjudicación de licitación",
    "Albaran / Nota de entrega",
    "Contrato",
    "Factura",
    "Oferta",
    "Pedido",
    "Pliego"
]


class ClassificationResult(BaseModel):
    category: CategoriaType
    # The date is optional and must follow the YYYY-MM-DD format
    doc_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')


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
# Helper to clean Markdown code blocks from model responses
# -------------------------------------------------------------

def clean_model_response(raw_response: str) -> str:
    """
    Extract JSON from a model response that may be wrapped in markdown code blocks.
    Handles ```json, ```, and plain text with embedded JSON.
    """
    cleaned = raw_response.strip()

    # Pattern to match Markdown code blocks: ```json ... ``` or ``` ... ```
    code_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?```"
    match = re.search(code_block_pattern, cleaned, re.DOTALL)

    if match:
        # Extract the content inside the code block
        return match.group(1).strip()

    # If no code block found, try to find the first JSON object directly
    json_pattern = r"\{.*\}"
    match = re.search(json_pattern, cleaned, re.DOTALL)
    if match:
        return match.group(0).strip()

    # If all else fails, return the original response
    return cleaned


# -------------------------------------------------------------
# Date classification and extraction using LLM
# -------------------------------------------------------------

def classify_text(filename: str, text: str, categories: list) -> dict:
    """
    Send the text to Ollama (Mistral 7B model) and it returns a dictionary
    with the keys 'category' and 'doc_date'. The model extracts the date from the content.
    """
    # Limit the length to prevent the model from becoming overloaded
    #text_limit = text[:3000]
    text_limit = text

    prompt = f"""
    You are an expert document classifier specialized in Spanish business documents. Your task is:
        1. Classify the document into one of the predefined categories.
        2. Extract the most relevant date (issue date, contract date, invoice date, etc.) in YYYY-MM-DD format.

    **Document context:**
        - Filename: {filename}
        - Content: {text_limit}

    **Categories with descriptions:**
        - "Acuerdo marco": Framework agreement, a long-term contract establishing general terms.
        - "Adjudicación de licitación": Tender award, official notification of a winning bid.
        - "Albaran": Delivery note, accompanies goods shipment. It can be also called "Nota de entrega" in Spanish.
        - "Contrato": Contract, a formal agreement between parties.
        - "Factura": Invoice, a bill for goods/services provided.
        - "Oferta": Quotation or offer, a price proposal.        
        - "Pedido": Purchase order, a request to buy goods/services.
        - "Pliego": Tender specifications, document outlining requirements for a bid.

    **Instructions:**
    - First, analyze the document content to determine the category and date.
    - Use the filename only as a hint; the content is more authoritative.
    - For date extraction:
      - Look for explicit date indicators: "Fecha", "Fecha de emisión", "Fecha de pedido", "Fecha de factura", "Fecha de contrato", etc.
      - Also look for dates in common Spanish formats: dd/mm/yyyy, dd.mm.yyyy, dd-mm-yyyy, dd de [month] de yyyy.
      - If the document contains multiple dates, choose the one that best corresponds to the document's type (e.g., for "Factura" use the invoice date, for "Contrato" use the signing date).
      - If no date is found in the content, check the filename for dates (patterns like yyyy-mm-dd, dd.mm.yyyy, etc.) and use that.
      - Convert all dates to YYYY-MM-DD (e.g., "04.03.2025" -> "2025-03-04", "5 de marzo de 2025" -> "2025-03-05").
      - If a date is ambiguous (e.g., 04/03/2025), assume day/month/year (Spanish convention) unless context suggests otherwise.
      - If absolutely no date can be found, set doc_date to null.

    **Response format:**
    - Respond only with a JSON object containing exactly two keys: "category" and "doc_date".
    - The "category" MUST match one of the categories provided in the "Categories with descriptions" section. 
    - **CRITICAL:** The "doc_date" MUST be a string in the exact format 'YYYY-MM-DD'.
    - For example, if the document shows "04.03.2025", you MUST respond with "2025-03-04".
    - If the document shows "5 de marzo de 2025", you MUST respond with "2025-03-05".
    - Do not use any other format like 'dd.mm.yyyy', 'dd/mm/yyyy', or 'dd-mm-yyyy'.
    - If absolutely no date can be found, set doc_date to null.
    - Example: {{"category": "Factura", "doc_date": "2025-03-04"}}
    - Do not include any extra text or explanations.

    **Examples:**
    - Input: Filename "Factura 27391763 - 04.03.2025.pdf", content mentions "Fecha de emisión: 04/03/2025". Output: {{"category": "Factura", "doc_date": "2025-03-04"}}
    - Input: Filename "Contrato 2025-03-05 ABC.pdf", content has "Firma: 5 de marzo de 2025". Output: {{"category": "Contrato", "doc_date": "2025-03-05"}}
    - Input: Filename "Pedido 12345.pdf", content has no date but mentions "Fecha pedido: 2025-01-15". Output: {{"category": "Pedido", "doc_date": "2025-01-15"}}
    - Input: Filename "Albarán 2025-03-05 51350855.pdf", content has "Fecha de entrega: 05-03-2025". Output: {{"category": "Albaran / Nota de entrega", "doc_date": "2025-03-05"}}

    **Now classify the following document:**
    """

    try:
        # Call Ollama with JSON format forced via Pydantic schema
        response = ollama.generate(
            model="mistral:7b-instruct-q4_K_M",
            prompt=prompt,
            format=ClassificationResult.model_json_schema(),
            options={"temperature": 0.0}
        )

        raw = response.get('response', '').strip()
        if not raw:
            logging.error("The model response is empty")
            return {"category": "Error", "doc_date": None}

        # Clean the response to remove Markdown code blocks
        cleaned_raw = clean_model_response(raw)
        logging.info(f"Cleaned response: {cleaned_raw[:200]}...")

        # Validate with Pydantic using the cleaned response
        result = ClassificationResult.model_validate_json(json_data=cleaned_raw)
        return result.model_dump()

    except Exception as e:
        logging.error(f"Classification error with Ollama: {e}")
        return {"category": "Error", "doc_date": None}