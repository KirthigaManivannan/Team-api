OCR Processing Workflow
Overview
The Intelligent Email and Document Extraction System extracts text and structured information from emails and documents.
Supported Input Types
Digital PDF files
Scanned PDF files
PNG images
JPG and JPEG images
Email subject and body
OCR Processing Steps

1.User uploads a document.
2.The application identifies the document format.
3.Digital PDFs are processed using PyMuPDF.
4.Scanned PDFs and images are processed using Tesseract OCR.
5.Extracted text is passed for information extraction.
6.Extracted information is validated.
7.Structured results are returned to the user.

Expected Output
The system provides extracted text, document classification, structured fields, and validation details.
 
