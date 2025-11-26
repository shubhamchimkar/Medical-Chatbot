# Deployment Guide

**RECOMMENDED: Use Option 2 (Hugging Face Spaces)**. 
Render's free tier (512MB RAM) is often insufficient for this application's AI models, causing "Out of Memory" errors. Hugging Face provides 16GB RAM for free.

## Prerequisites

You will need your API keys ready:
- `PINECONE_API_KEY`
- `OPENAI_API_KEY`

## Option 1: Render (May run out of memory)

Render is very easy to use and connects directly to your GitHub repository.

1.  **Sign up** at [render.com](https://render.com/).
2.  Click **New +** and select **Web Service**.
3.  Connect your GitHub account and select this repository (`Medical-Chatbot`).
4.  **Configure the service**:
    - **Name**: `medical-chatbot` (or any name)
    - **Region**: Choose one close to you.
    - **Branch**: `main`
    - **Runtime**: `Docker` (Render should auto-detect the Dockerfile).
    - **Instance Type**: `Free`
5.  **Environment Variables**:
    - Scroll down to the "Environment Variables" section.
    - Add `PINECONE_API_KEY` and your key.
    - Add `OPENAI_API_KEY` and your key.
6.  Click **Create Web Service**.

Render will build your Docker image and deploy it. It might take a few minutes.

## Option 2: Hugging Face Spaces (Recommended for AI Apps)

Hugging Face Spaces provides generous free resources (16GB RAM), which is great if the application uses heavy AI models.

1.  **Sign up** at [huggingface.co](https://huggingface.co/).
2.  Click **New Space**.
3.  **Name**: `medical-chatbot`.
4.  **License**: `MIT` (or your choice).
5.  **SDK**: Select **Docker**.
6.  **Create Space**.
7.  Once created, go to **Settings** -> **Variables and secrets**.
    - Add `PINECONE_API_KEY` as a Secret.
    - Add `OPENAI_API_KEY` as a Secret.
8.  The Space will build automatically from your Dockerfile.

## Important: Data Ingestion

Before deploying, ensure your Pinecone index is populated with data. The application reads from an **existing** index named `medical-chatbot`.

1.  Ensure you have your PDF data in the `data/` folder.
2.  Run the ingestion script locally:
    ```bash
    python store_index.py
    ```
    (Make sure your `.env` file has the API keys).

## Note on Port

The application is configured to listen on the port specified by the `PORT` environment variable.
- **Hugging Face Spaces** defaults to port `7860`. The Dockerfile has been updated to set this as the default.
- **Render** automatically sets the `PORT` variable, so it will still work if you choose to try it (though memory may be an issue).
