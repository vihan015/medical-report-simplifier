import streamlit as st


def render():
    return st.file_uploader("Lab report or prescription", type=["pdf", "png", "jpg", "jpeg"],
                            help="PDF, PNG, JPG or JPEG. Maximum 15 MB.")
