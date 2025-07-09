# AI-Enhanced PDF Scholar

An intelligent platform to streamline academic literature review.

## 📖 Project Goal & Motivation

This project aims to create an intelligent platform that streamlines the laborious process of academic literature review. It was conceived to eliminate the constant context-switching and manual copy-pasting required when analyzing academic papers with AI, providing a unified and efficient research environment.

## 🏗️ Architecture & Technical Highlights

*   **Decoupled System**: Architected as a highly decoupled system, it serves both a **PyQt6** desktop application and a **FastAPI** web user interface from a single core backend logic layer.
*   **Retrieval-Augmented Generation (RAG)**: Features a robust RAG pipeline, powered by **LlamaIndex**, enabling intelligent and context-aware interactions with PDF documents.
*   **Asynchronous Processing**: Utilizes asynchronous `QThreads` for handling long-running AI tasks, ensuring a fluid and responsive user experience in the desktop application.
*   **Iterative Development**: The project is a product of multiple refactoring cycles, emphasizing the importance of thorough requirements analysis and flexible architectural planning for robust software development.

## 🛠️ Tech Stack

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![PyQt6](https://img.io/badge/PyQt6-41CD52?style=for-the-badge&logo=qt)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-6B45BC?style=for-the-badge)
![Pytest](https://img.shields.io/badge/pytest-0A9B71?style=for-the-badge&logo=pytest)

## 🚀 Installation & Usage

Follow these steps to set up and run the project:

### 1. Clone the Repository

```bash
git clone https://github.com/Jackela/ai_enhanced_pdf_scholar.git
cd ai_enhanced_pdf_scholar
```

### 2. Create and Activate a Virtual Environment

*   **On Windows:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```
*   **On macOS/Linux:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up API Keys

Refer to `API_KEY_SETUP.md` for instructions on configuring your API keys.

### 5. Run the Application

*   **PyQt6 Desktop App:**
    ```bash
    python main.py
    ```
*   **FastAPI Web App:**
    ```bash
    uvicorn web_main:app --reload
    ```

## 📄 License

This project is licensed under the MIT License.

---

**MIT License**

Copyright (c) 2024 Weixuan Kong

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.