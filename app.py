"""Точка входа приложения: переход к разделу проекта."""

from __future__ import annotations

import streamlit as st

from src import APP_NAME


st.set_page_config(page_title=APP_NAME, page_icon="↕️", layout="wide")
st.switch_page("pages/01_project.py")
