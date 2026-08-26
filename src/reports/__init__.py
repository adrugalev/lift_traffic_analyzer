"""Генераторы DOCX, PDF, XLSX и интерактивных графиков."""

from .docx_report import build_docx_report
from .excel_report import build_excel_report
from .pdf_report import build_pdf_report

__all__ = ["build_docx_report", "build_excel_report", "build_pdf_report"]

