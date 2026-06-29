# TalentAI: AI-Powered Resume Screening & Candidate Ranking System

TalentAI is an intelligent, enterprise-grade recruitment assistant designed to streamline the hiring workflow. It automatically parses candidate resumes, extracts structured information, evaluates candidates against job descriptions, ranks them based on semantic suitability, identifies skill gaps, generates tailored interview questions, and provides interactive recruiter chat support.

This project was built as part of the **Teyzix Core Internship (June Batch)** under the **AI-2 Task ID**.

---

## 🌟 Key Features

### 1. Resume Processing & Extraction
*   **Multi-Format PDF Parsing:** Extract and clean text from resumes of various layouts using `pdfplumber`.
*   **Structured Information Extraction:** Uses Gemini to extract **Name, Email, Phone, Skills, Education, Work Experience, Projects, Certifications, and a Professional Summary**.

### 2. Job Description Analysis
*   **Requirement Structuring:** Analyzes job descriptions to extract required skills, preferred qualifications, experience requirements, and core responsibilities.

### 3. Candidate Matching & Ranking Engine
*   **Explainable Scoring Methodology:** Computes an overall match score (0-100%) based on weighted criteria:
    *   **Skills Alignment (40%)**
    *   **Experience Suitability (30%)**
    *   **Education Relevance (20%)**
    *   **Projects & Portfolio (10%)**
*   **Strengths & Weaknesses Profiling:** Identifies specific areas of alignment and critical gaps for each candidate.
*   **Detailed Skill Gap Analysis:** Maps candidate skills against job requirements in an interactive matrix (Matching Status: Yes / No / Partial).

### 4. Advanced AI Features (Bonus)
*   **Tailored Interview Question Generator:** Generates 5 highly specific technical and behavioral questions to probe candidate gaps during interviews.
*   **Resume Improvement Suggestions:** Actionable feedback to help candidates tailor their resumes for the target position.
*   **AI Recruiter Chat Assistant:** A sidebar chatbot that allows recruiters to ask natural language questions about a candidate's background and suitability.
*   **PDF Report Export:** Downloadable, professionally designed PDF evaluation reports for sharing with hiring managers.
*   **Candidate Comparison:** Side-by-side comparison of up to 3 candidates with an interactive grouped bar chart.

### 5. Dual Execution Modes
*   **🤖 Gemini AI Mode:** Powered by `gemini-1.5-flash` for advanced semantic understanding and reasoning.
*   **⚡ Local Fallback Mode:** Uses rule-based regex, keyword matching, and Jaccard similarity. The application is **fully functional out-of-the-box** without requiring an external API key.

---

## 📁 Project Structure

```text
Task_2/
│
├── app.py                     # Main Streamlit Dashboard Application
├── generate_sample_data.py    # Script to generate sample PDFs & JDs for testing
│
├── utils/                     # Utility Modules
│   ├── pdf_parser.py          # PDF text extraction and cleaning
│   ├── ai_engine.py           # Gemini API integration and local fallback matching
│   └── database.py            # Local JSON-based database operations
│
├── styles/                    # UI Stylesheets
│   └── custom.css             # Premium glassmorphism dark-mode styles
│
├── data/                      # Data Storage
│   ├── db.json                # Local JSON database (auto-generated)
│   ├── sample_resumes/        # Pre-loaded PDF resumes (auto-generated)
│   ├── sample_job_descriptions/# Pre-loaded JD text files (auto-generated)
│   └── uploaded_resumes/      # Directory for user-uploaded resumes
│
└── README.md                  # Project documentation (this file)
```

---

## 🛠️ Installation & Setup

### Prerequisites
Ensure you have **Python 3.8+** installed on your system.

### 1. Install Dependencies
Run the following command to install the required libraries:
```bash
pip install streamlit google-generativeai plotly fpdf2 pdfplumber python-dotenv
```

### 2. Run the Application
Start the Streamlit server from the project directory:
```bash
streamlit run app.py
```

The application will open automatically in your web browser (usually at `http://localhost:8501`).

---

## 🚀 How to Use

1.  **Launch the App:** On the first run, the app will automatically generate and load a **sample dataset** (John Doe - Software Engineer, Jane Smith - Data Scientist, Alex Johnson - Product Manager) so you can explore all features immediately.
2.  **Toggle Execution Modes:**
    *   *Local Mode:* By default, the app runs locally. You can view rankings, comparison charts, and chat with a rule-based engine.
    *   *Gemini AI Mode:* Paste your **Google Gemini API Key** in the sidebar. This unlocks deep semantic analysis, custom interview question generation, resume suggestions, and intelligent chat answers.
3.  **Screen Candidates:**
    *   Go to **Upload Resumes**, select a target Job Description, and upload candidate PDFs.
    *   Click **Process & Screen Resumes** to parse, analyze, and rank them.
4.  **Compare & Export:**
    *   Use the **Candidate Comparison** tab to view candidates side-by-side.
    *   In the **Screening Dashboard**, select a candidate and click **Download PDF Evaluation Report** to save a professional summary.
