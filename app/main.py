import os
import tempfile
import logging

from fastapi import FastAPI, UploadFile, File, HTTPException


from app.utils import extract_text_from_file, classify_text

app = FastAPI(title="Document Classifier API", description="Sort documents and extract dates using a LLM")

CATEGORIES = [
        "Acuerdo marco",
        "Adjudicación de licitación",
        "Albaran",
        "Contrato",
        "Factura",
        "Oferta",
        "Pedido",
        "Pliego"
    ]


@app.post("/classifier/v1/classify")
async def classify_document(file: UploadFile = File(...)):
    """
    POST endpoint to classify a document and extract its date.
    It receives a file and returns the category and the date (extracted by the LLM).

    These are the default categories used:
        - Acuerdo marco
        - Adjudicación de licitación
        - Albaran
        - Contrato
        - Factura
        - Oferta
        - Pedido
        - Pliego
    """
    tmp_path = None
    try:
        # Save the file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Extract text from the file (supports PDF, images and plain text)
        texto = extract_text_from_file(tmp_path)
        if not texto or len(texto.strip()) < 20:
            raise HTTPException(status_code=400, detail="It was not possible to extract enough text from the document")

        # Classify and extract dates using the LLM
        llm_result = classify_text(file.filename, texto, CATEGORIES)

        return {
            "category": llm_result["category"],
            "doc_date": llm_result["doc_date"],
            "filename": file.filename
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Classification error")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clear temporary files
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9191)