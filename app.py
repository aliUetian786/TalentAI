import streamlit as st
import os
import json
import re
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from fpdf import FPDF

# Import custom modules
from utils.pdf_parser import extract_text_from_pdf
from utils.database import (
    load_db, save_resume, save_jd, save_evaluation,
    get_resumes, get_jds, get_evaluations_for_jd,
    delete_resume, delete_jd, get_evaluation, clear_db
)
from utils.ai_engine import (
    extract_candidate_info, analyze_job_description,
    match_candidate, generate_interview_questions,
    generate_resume_suggestions, chat_about_candidate
)

# Page configuration
st.set_page_config(
    page_title="TalentAI - Resume Screening & Ranking Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper to load CSS
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def clean_html(html_str):
    """
    Cleans leading whitespace from HTML strings to prevent Streamlit
    from rendering them inside code or pre blocks.
    """
    return "\n".join([line.strip() for line in html_str.split("\n")])

# Load custom styles
local_css("styles/custom.css")

# Ensure directories exist
os.makedirs("data/uploaded_resumes", exist_ok=True)

# Session state initialization
if "gemini_api_key" not in st.session_state:
    st.session_state["gemini_api_key"] = ""
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "Screening Dashboard"
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = {}
if "selected_candidate_id" not in st.session_state:
    st.session_state["selected_candidate_id"] = None
if "selected_jd_id" not in st.session_state:
    st.session_state["selected_jd_id"] = None

# ==========================================
# AUTO-LOAD SAMPLE DATA IF DB IS EMPTY
# ==========================================
def load_sample_data_if_empty():
    db = load_db()
    # If no JDs or Resumes, generate and load them
    if not db.get("job_descriptions") or not db.get("resumes"):
        st.info("Initializing sample dataset for immediate demonstration...")
        
        # Check if sample files exist; if not, run the generator script
        if not os.path.exists("data/sample_resumes/john_doe_software_engineer.pdf"):
            try:
                import subprocess
                subprocess.run(["python", "generate_sample_data.py"], check=True)
            except Exception as e:
                st.error(f"Failed to generate sample data: {e}")
                return

        # 1. Load Job Descriptions
        jds_to_load = [
            ("software_engineer_jd", "data/sample_job_descriptions/software_engineer_jd.txt"),
            ("data_scientist_jd", "data/sample_job_descriptions/data_scientist_jd.txt")
        ]
        for jd_id, path in jds_to_load:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                # Run local analysis for instant loading (fast and no API key required)
                from utils.ai_engine import run_local_jd_analysis
                jd_data = run_local_jd_analysis(text)
                jd_data["raw_text"] = text
                save_jd(jd_id, jd_data)

        # 2. Load Resumes
        resumes_to_load = [
            ("john_doe", "data/sample_resumes/john_doe_software_engineer.pdf"),
            ("jane_smith", "data/sample_resumes/jane_smith_data_scientist.pdf"),
            ("alex_johnson", "data/sample_resumes/alex_johnson_product_manager.pdf")
        ]
        
        from utils.ai_engine import run_local_resume_extraction, run_local_matching
        for r_id, path in resumes_to_load:
            if os.path.exists(path):
                text = extract_text_from_pdf(path)
                resume_data = run_local_resume_extraction(text)
                resume_data["raw_text"] = text
                resume_data["file_path"] = path
                save_resume(r_id, resume_data)
                
                # Match against appropriate JD
                if r_id == "john_doe":
                    jd_id = "software_engineer_jd"
                elif r_id == "jane_smith":
                    jd_id = "data_scientist_jd"
                else:
                    # PM matches Software Engineer JD as a low/med fit for demo
                    jd_id = "software_engineer_jd"
                
                jd_data = db.get("job_descriptions", {}).get(jd_id) or run_local_jd_analysis(
                    open(f"data/sample_job_descriptions/{jd_id.split('_jd')[0]}_jd.txt", "r").read()
                )
                eval_data = run_local_matching(resume_data, jd_data)
                save_evaluation(r_id, jd_id, eval_data)
        
        # 3. Auto-import any previously uploaded resumes in data/uploaded_resumes/
        uploaded_dir = "data/uploaded_resumes"
        if os.path.exists(uploaded_dir):
            for filename in os.listdir(uploaded_dir):
                if filename.lower().endswith(".pdf"):
                    path = os.path.join(uploaded_dir, filename)
                    # Create a clean, deterministic candidate ID
                    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', filename.split(".")[0]).lower()
                    r_id = f"cand_{clean_name}"
                    
                    text = extract_text_from_pdf(path)
                    resume_data = run_local_resume_extraction(text)
                    resume_data["raw_text"] = text
                    resume_data["file_path"] = path
                    save_resume(r_id, resume_data)
                    
                    # Match against software_engineer_jd by default (can be re-evaluated in UI)
                    jd_id = "software_engineer_jd"
                    jd_data = get_jds().get(jd_id)
                    if jd_data:
                        eval_data = run_local_matching(resume_data, jd_data)
                        save_evaluation(r_id, jd_id, eval_data)
        
        st.success("Sample dataset loaded successfully! (John Doe, Jane Smith, Alex Johnson)")

# Run the loader
load_sample_data_if_empty()

# Refresh DB references
db = load_db()
jds = get_jds()
resumes = get_resumes()

# Self-healing / Migration: Auto-import uploaded resumes & fix incorrect names
migrated = False

# 1. Import any resumes in data/uploaded_resumes/ that aren't in the database
uploaded_dir = "data/uploaded_resumes"
if os.path.exists(uploaded_dir):
    for filename in os.listdir(uploaded_dir):
        if filename.lower().endswith(".pdf"):
            path = os.path.join(uploaded_dir, filename)
            clean_name = re.sub(r'[^a-zA-Z0-9]', '_', filename.split(".")[0]).lower()
            r_id = f"cand_{clean_name}"
            if r_id not in resumes:
                text = extract_text_from_pdf(path)
                from utils.ai_engine import run_local_resume_extraction, run_local_matching
                resume_data = run_local_resume_extraction(text)
                resume_data["raw_text"] = text
                resume_data["file_path"] = path
                save_resume(r_id, resume_data)
                
                # Match against software_engineer_jd by default
                jd_id = "software_engineer_jd"
                jd_data = jds.get(jd_id)
                if jd_data:
                    eval_data = run_local_matching(resume_data, jd_data)
                    save_evaluation(r_id, jd_id, eval_data)
                migrated = True

# 2. Correct any names parsed as "Computer Engineering"
for r_id, resume_data in list(resumes.items()):
    if resume_data.get("name") == "Computer Engineering":
        from utils.ai_engine import run_local_resume_extraction
        new_extracted = run_local_resume_extraction(resume_data.get("raw_text", ""))
        if new_extracted["name"] != "Computer Engineering":
            resume_data["name"] = new_extracted["name"]
            save_resume(r_id, resume_data)
            migrated = True

if migrated:
    resumes = get_resumes()

# Set default active JD if not set
if not st.session_state["selected_jd_id"] and jds:
    st.session_state["selected_jd_id"] = list(jds.keys())[0]

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("<h2>🎯 TalentAI Screen</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Gemini API Key Section
    st.markdown("### 🔑 API Configuration")
    api_key_input = st.text_input(
        "Gemini API Key (Optional)",
        value=st.session_state["gemini_api_key"],
        type="password",
        help="Paste your Google Gemini API Key here. If empty, the system runs in high-performance local mode."
    )
    if api_key_input != st.session_state["gemini_api_key"]:
        st.session_state["gemini_api_key"] = api_key_input
        st.success("API Key updated!")
        
    if st.session_state["gemini_api_key"]:
        st.info("🤖 Gemini AI Mode: Active")
    else:
        st.warning("⚡ Local Mode: Active (No API Key)")

    st.markdown("---")
    st.markdown("### 🧭 Navigation")
    
    # Custom Navigation Buttons
    nav_options = [
        ("📊 Screening Dashboard", "Screening Dashboard"),
        ("📋 Job Descriptions", "Job Descriptions"),
        ("📥 Upload Resumes", "Upload Resumes"),
        ("👥 Candidate Comparison", "Candidate Comparison"),
        ("💬 AI Recruiter Chat", "AI Recruiter Chat")
    ]
    
    for label, tab_name in nav_options:
        if st.button(
            label, 
            key=f"nav_{tab_name}", 
            use_container_width=True,
            type="secondary" if st.session_state["active_tab"] != tab_name else "primary"
        ):
            st.session_state["active_tab"] = tab_name
            st.rerun()

    st.markdown("---")
    st.markdown("### 🛠️ System Actions")
    if st.button("♻️ Reset Database", key="reset_db", use_container_width=True):
        clear_db()
        # Delete all files in data/uploaded_resumes/
        uploaded_dir = "data/uploaded_resumes"
        if os.path.exists(uploaded_dir):
            for filename in os.listdir(uploaded_dir):
                file_path = os.path.join(uploaded_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f"Error deleting file {file_path}: {e}")
        # Re-create empty structures
        os.makedirs("data/uploaded_resumes", exist_ok=True)
        st.success("Database cleared and all uploaded files deleted!")
        st.session_state["selected_candidate_id"] = None
        st.session_state["selected_jd_id"] = None
        st.rerun()

# ==========================================
# MAIN PAGE HEADER
# ==========================================
st.markdown(
    clean_html("""
    <div class='main-header'>
        <h1>TalentAI: Advanced Resume Screening</h1>
        <p>AI-Powered Applicant Tracking, Semantic Candidate Ranking & Tailored Interview Insights</p>
    </div>
    """), 
    unsafe_allow_html=True
)

# Active Tab Selection
active_tab = st.session_state["active_tab"]

# ==========================================
# VIEW 1: SCREENING DASHBOARD
# ==========================================
if active_tab == "Screening Dashboard":
    st.markdown("### 📊 Screening Dashboard")
    
    if not jds:
        st.info("No Job Descriptions found. Please go to the **Job Descriptions** tab to create one.")
    else:
        # JD Selector
        jd_options = {v["title"]: k for k, v in jds.items()}
        selected_jd_title = st.selectbox(
            "Select Job Description to Evaluate Candidates",
            options=list(jd_options.keys()),
            index=list(jd_options.keys()).index(jds[st.session_state["selected_jd_id"]]["title"]) if st.session_state["selected_jd_id"] in jds.values() else 0
        )
        active_jd_id = jd_options[selected_jd_title]
        st.session_state["selected_jd_id"] = active_jd_id
        
        active_jd = jds[active_jd_id]
        
        # Get evaluations for this JD
        evaluations = get_evaluations_for_jd(active_jd_id)
        
        # Display JD Summary card
        st.markdown(
            clean_html(f"""
            <div class='glass-card'>
                <h4 style='margin:0; color:#818cf8;'>📋 Active Job Description: {active_jd['title']}</h4>
                <p style='margin:0.5rem 0 0 0; font-size:0.95rem; color:#94a3b8;'>
                    <strong>Required Skills:</strong> {", ".join([f"<span class='badge badge-blue'>{s}</span>" for s in active_jd['required_skills']])}
                </p>
                <p style='margin:0.5rem 0 0 0; font-size:0.95rem; color:#94a3b8;'>
                    <strong>Required Experience:</strong> {active_jd.get('experience_years', 'N/A')}
                </p>
            </div>
            """),
            unsafe_allow_html=True
        )
        
        if not evaluations:
            st.warning("No candidates have been evaluated for this Job Description yet. Go to the **Upload Resumes** tab to add candidates.")
        else:
            # Prepare rankings data
            rankings_list = []
            for r_id, eval_data in evaluations.items():
                cand_info = resumes.get(r_id)
                if cand_info:
                    # Self-healing: Upgrade old evaluations with missing questions or suggestions
                    from utils.ai_engine import generate_interview_questions, generate_resume_suggestions
                    updated = False
                    if "interview_questions" not in eval_data or not eval_data["interview_questions"]:
                        eval_data["interview_questions"] = generate_interview_questions(
                            cand_info, active_jd, eval_data, st.session_state["gemini_api_key"]
                        )
                        updated = True
                    if "resume_suggestions" not in eval_data or not eval_data["resume_suggestions"]:
                        eval_data["resume_suggestions"] = generate_resume_suggestions(
                            cand_info, active_jd, eval_data, st.session_state["gemini_api_key"]
                        )
                        updated = True
                    if updated:
                        save_evaluation(r_id, active_jd_id, eval_data)
                        
                    rankings_list.append({
                        "id": r_id,
                        "name": cand_info["name"],
                        "email": cand_info["email"],
                        "score": eval_data["matching_score"],
                        "recommendation": eval_data["recommendation"],
                        "skills_score": eval_data["breakdown"]["skills_score"],
                        "experience_score": eval_data["breakdown"]["experience_score"],
                        "education_score": eval_data["breakdown"]["education_score"],
                        "projects_score": eval_data["breakdown"]["projects_score"],
                        "eval_data": eval_data,
                        "resume_data": cand_info
                    })
            
            # Sort by score descending
            rankings_list = sorted(rankings_list, key=lambda x: x["score"], reverse=True)
            
            # Top Stats
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(
                    clean_html(f"""
                    <div class='glass-card' style='text-align:center; padding:1rem;'>
                        <span style='color:#94a3b8; font-size:0.9rem; font-weight:500;'>Total Applicants</span>
                        <h2 style='margin:0.5rem 0 0 0; color:#818cf8; font-weight:700;'>{len(rankings_list)}</h2>
                    </div>
                    """),
                    unsafe_allow_html=True
                )
            with c2:
                high_fit = sum(1 for x in rankings_list if x["score"] >= 80)
                st.markdown(
                    clean_html(f"""
                    <div class='glass-card' style='text-align:center; padding:1rem;'>
                        <span style='color:#94a3b8; font-size:0.9rem; font-weight:500;'>High Fit (>= 80%)</span>
                        <h2 style='margin:0.5rem 0 0 0; color:#34d399; font-weight:700;'>{high_fit}</h2>
                    </div>
                    """),
                    unsafe_allow_html=True
                )
            with c3:
                avg_score = int(sum(x["score"] for x in rankings_list) / len(rankings_list))
                st.markdown(
                    clean_html(f"""
                    <div class='glass-card' style='text-align:center; padding:1rem;'>
                        <span style='color:#94a3b8; font-size:0.9rem; font-weight:500;'>Average Match Score</span>
                        <h2 style='margin:0.5rem 0 0 0; color:#f59e0b; font-weight:700;'>{avg_score}%</h2>
                    </div>
                    """),
                    unsafe_allow_html=True
                )
            with c4:
                top_cand = rankings_list[0]["name"] if rankings_list else "N/A"
                st.markdown(
                    clean_html(f"""
                    <div class='glass-card' style='text-align:center; padding:1rem;'>
                        <span style='color:#94a3b8; font-size:0.9rem; font-weight:500;'>Top Candidate</span>
                        <h2 style='margin:0.5rem 0 0 0; color:#f472b6; font-weight:700; font-size:1.5rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{top_cand}</h2>
                    </div>
                    """),
                    unsafe_allow_html=True
                )
            
            # Leaderboard table
            st.markdown("<h4 style='color:#f1f5f9; margin-top:1.5rem;'>🏆 Candidate Rankings</h4>", unsafe_allow_html=True)
            
            # Build Table HTML
            table_html = """
            <table style='width:100%; border-collapse:collapse; text-align:left; background:rgba(20, 21, 33, 0.4); border-radius:12px; overflow:hidden;'>
                <thead>
                    <tr style='background:rgba(99, 102, 241, 0.1); border-bottom:1px solid rgba(255,255,255,0.08);'>
                        <th style='padding:1rem; color:#818cf8; font-weight:600;'>Rank</th>
                        <th style='padding:1rem; color:#818cf8; font-weight:600;'>Candidate Name</th>
                        <th style='padding:1rem; color:#818cf8; font-weight:600;'>Email</th>
                        <th style='padding:1rem; color:#818cf8; font-weight:600; text-align:center;'>Match Score</th>
                        <th style='padding:1rem; color:#818cf8; font-weight:600;'>Recommendation</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for idx, cand in enumerate(rankings_list):
                rank = idx + 1
                score = cand["score"]
                if score >= 80:
                    score_class = "score-high"
                    badge_class = "badge-green"
                elif score >= 60:
                    score_class = "score-medium"
                    badge_class = "badge-yellow"
                else:
                    score_class = "score-low"
                    badge_class = "badge-pink"
                
                table_html += f"""
                    <tr style='border-bottom:1px solid rgba(255,255,255,0.05); transition: background-color 0.2s;'>
                        <td style='padding:1rem; font-weight:700; color:#94a3b8;'>#{rank}</td>
                        <td style='padding:1rem; font-weight:600; color:#f1f5f9;'>{cand['name']}</td>
                        <td style='padding:1rem; color:#94a3b8;'>{cand['email']}</td>
                        <td style='padding:1rem; text-align:center;'>
                            <span style='padding: 0.35rem 0.8rem; border-radius: 6px; font-weight:700; font-size:1rem; color:#fff;' class='{score_class}'>{score}%</span>
                        </td>
                        <td style='padding:1rem;'>
                            <span class='badge {badge_class}'>{cand['recommendation'].split(' - ')[0]}</span>
                        </td>
                    </tr>
                """
            table_html += "</tbody></table>"
            st.markdown(clean_html(table_html), unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Detailed Candidate View
            st.markdown("<h4 style='color:#f1f5f9;'>🔍 Detailed Candidate Insights</h4>", unsafe_allow_html=True)
            
            # Select candidate
            cand_dict = {c["name"]: c["id"] for c in rankings_list}
            if st.session_state["selected_candidate_id"] not in [c["id"] for c in rankings_list]:
                st.session_state["selected_candidate_id"] = rankings_list[0]["id"]
                
            selected_cand_name = st.selectbox(
                "Select Candidate to View Profile & Detailed AI Evaluation",
                options=list(cand_dict.keys()),
                index=list(cand_dict.values()).index(st.session_state["selected_candidate_id"])
            )
            
            active_cand_id = cand_dict[selected_cand_name]
            st.session_state["selected_candidate_id"] = active_cand_id
            
            # Find candidate in list
            active_cand = next(c for c in rankings_list if c["id"] == active_cand_id)
            
            # Display Candidate Profile
            c_left, c_right = st.columns([1, 2])
            
            with c_left:
                # Score Visualizer (Gauge Chart)
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = active_cand["score"],
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "Match Score", 'font': {'size': 20, 'color': '#f1f5f9', 'family': 'Outfit'}},
                    number = {'font': {'size': 44, 'color': '#f1f5f9', 'family': 'Outfit'}, 'suffix': '%'},
                    gauge = {
                        'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "#94a3b8"},
                        'bar': {'color': "#6366f1"},
                        'bgcolor': "rgba(255, 255, 255, 0.05)",
                        'borderwidth': 1,
                        'bordercolor': "rgba(255, 255, 255, 0.1)",
                        'steps': [
                            {'range': [0, 50], 'color': 'rgba(239, 68, 68, 0.1)'},
                            {'range': [50, 75], 'color': 'rgba(245, 158, 11, 0.1)'},
                            {'range': [75, 100], 'color': 'rgba(16, 185, 129, 0.1)'}
                        ],
                    }
                ))
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font={'color': "#f1f5f9", 'family': "Outfit"},
                    height=240,
                    margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Breakdown Bar Chart
                breakdown_data = {
                    "Metric": ["Skills", "Experience", "Education", "Projects"],
                    "Score": [
                        active_cand["skills_score"],
                        active_cand["experience_score"],
                        active_cand["education_score"],
                        active_cand["projects_score"]
                    ]
                }
                fig_bar = px.bar(
                    breakdown_data, 
                    x="Score", 
                    y="Metric", 
                    orientation='h',
                    color="Score",
                    color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                    range_color=[40, 100]
                )
                fig_bar.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font={'color': "#f1f5f9", 'family': "Outfit"},
                    height=200,
                    xaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                    margin=dict(l=10, r=10, t=10, b=10),
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            with c_right:
                st.markdown(
                    clean_html(f"""
                    <div class='glass-card'>
                        <h3 style='margin:0; color:#f1f5f9;'>👤 {active_cand['name']}</h3>
                        <p style='color:#94a3b8; font-size:0.9rem; margin:0.25rem 0 0.75rem 0;'>
                            📧 {active_cand['email']} | 📱 {active_cand['resume_data'].get('phone', 'N/A')}
                        </p>
                        <p style='margin:0; line-height:1.5;'>{active_cand['resume_data'].get('summary', '')}</p>
                    </div>
                    """),
                    unsafe_allow_html=True
                )
                
                # Strengths & Weaknesses side by side
                col_st, col_wk = st.columns(2)
                with col_st:
                    st.markdown("<h5 style='color:#34d399;'>💪 Key Strengths</h5>", unsafe_allow_html=True)
                    for stg in active_cand["eval_data"].get("strengths", []):
                        st.markdown(f"- {stg}")
                with col_wk:
                    st.markdown("<h5 style='color:#f472b6;'>⚠️ Skill Gaps / Areas to Explore</h5>", unsafe_allow_html=True)
                    for wk in active_cand["eval_data"].get("weaknesses", []):
                        st.markdown(f"- {wk}")
            
            # Tabs for Skill Gap, Interview Questions, Resume Suggestions
            tab_gap, tab_q, tab_sug, tab_raw = st.tabs([
                "🧩 Skill Gap Analysis", 
                "❓ Tailored Interview Questions", 
                "💡 Resume Improvement Suggestions",
                "📄 Raw Resume Text"
            ])
            
            with tab_gap:
                st.markdown("##### Required Skill Match Breakdown")
                gap_analysis = active_cand["eval_data"].get("skill_gap_analysis", [])
                if not gap_analysis:
                    st.info("No detailed skill gap analysis available.")
                else:
                    gap_table = """
                    <table style='width:100%; border-collapse:collapse; text-align:left; background:rgba(20, 21, 33, 0.2); border-radius:8px; overflow:hidden;'>
                        <thead>
                            <tr style='background:rgba(255,255,255,0.03); border-bottom:1px solid rgba(255,255,255,0.08);'>
                                <th style='padding:0.75rem; color:#818cf8; font-weight:600;'>Skill</th>
                                <th style='padding:0.75rem; color:#818cf8; font-weight:600; text-align:center;'>Core Required</th>
                                <th style='padding:0.75rem; color:#818cf8; font-weight:600; text-align:center;'>Candidate Has</th>
                                <th style='padding:0.75rem; color:#818cf8; font-weight:600;'>Notes</th>
                            </tr>
                        </thead>
                        <tbody>
                    """
                    for item in gap_analysis:
                        has_status = item.get("candidate_has", "no")
                        if has_status == "yes":
                            badge = "<span class='badge badge-green'>Yes</span>"
                        elif has_status == "partial":
                            badge = "<span class='badge badge-yellow'>Partial</span>"
                        else:
                            badge = "<span class='badge badge-pink'>No</span>"
                            
                        req_badge = "Yes" if item.get("required", True) else "Preferred"
                        
                        gap_table += f"""
                            <tr style='border-bottom:1px solid rgba(255,255,255,0.05);'>
                                <td style='padding:0.75rem; font-weight:600; color:#f1f5f9;'>{item['skill']}</td>
                                <td style='padding:0.75rem; text-align:center; color:#94a3b8;'>{req_badge}</td>
                                <td style='padding:0.75rem; text-align:center;'>{badge}</td>
                                <td style='padding:0.75rem; color:#94a3b8; font-size:0.9rem;'>{item.get('notes', '')}</td>
                            </tr>
                        """
                    gap_table += "</tbody></table>"
                    st.markdown(clean_html(gap_table), unsafe_allow_html=True)
            
            with tab_q:
                st.markdown("##### AI-Generated Interview Questions")
                st.caption("Custom questions to probe the candidate's experience and explore identified skill gaps.")
                
                questions = active_cand["eval_data"].get("interview_questions")
                
                if questions:
                    for i, q in enumerate(questions):
                        st.markdown(
                            clean_html(f"""
                            <div style='background:rgba(255, 255, 255, 0.03); border:1px solid rgba(255,255,255,0.05); padding:1rem; border-radius:8px; margin-bottom:0.75rem;'>
                                <strong style='color:#818cf8;'>Question {i+1}:</strong><br/>
                                <span style='font-size:1.05rem; color:#f1f5f9;'>"{q}"</span>
                            </div>
                            """), 
                            unsafe_allow_html=True
                        )
                else:
                    st.info("No interview questions available.")
                    
            with tab_sug:
                st.markdown("##### Resume Improvement Suggestions")
                st.caption("Actionable suggestions for the candidate to improve their resume for this role.")
                
                suggestions = active_cand["eval_data"].get("resume_suggestions")
                
                if suggestions:
                    for sug in suggestions:
                        st.markdown(f"- {sug}")
                else:
                    st.info("No resume improvement suggestions available.")
                    
            with tab_raw:
                st.text_area(
                    "Raw Extracted Text", 
                    value=active_cand["resume_data"].get("raw_text", ""), 
                    height=400, 
                    disabled=True
                )
            
            # Export Report PDF Button
            st.markdown("---")
            st.markdown("#### 📤 Export Evaluation Report")
            
            # Build PDF
            def generate_pdf_report(candidate, jd, evaluation):
                pdf = FPDF()
                pdf.add_page()
                
                # Header Banner
                pdf.set_fill_color(20, 21, 33)
                pdf.rect(0, 0, 210, 40, 'F')
                
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("helvetica", "B", 18)
                pdf.text(15, 18, "TALENTAI EVALUATION REPORT")
                pdf.set_font("helvetica", "", 10)
                pdf.text(15, 28, f"Role: {jd['title']}  |  Generated on: {datetime.now().strftime('%Y-%m-%d')}")
                
                pdf.ln(35)
                
                # Candidate Details
                pdf.set_text_color(45, 55, 72)
                pdf.set_font("helvetica", "B", 14)
                pdf.cell(0, 10, f"Candidate: {candidate['name']}", 0, 1)
                
                pdf.set_font("helvetica", "", 10)
                pdf.cell(100, 6, f"Email: {candidate['email']}", 0, 0)
                pdf.cell(100, 6, f"Phone: {candidate.get('phone', 'N/A')}", 0, 1)
                
                pdf.ln(5)
                pdf.set_draw_color(226, 232, 240)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(5)
                
                # Match Score Callout
                pdf.set_font("helvetica", "B", 12)
                pdf.cell(50, 10, "MATCHING SCORE:", 0, 0)
                pdf.set_font("helvetica", "B", 16)
                score = evaluation['matching_score']
                if score >= 80:
                    pdf.set_text_color(16, 185, 129) # Green
                elif score >= 60:
                    pdf.set_text_color(245, 158, 11) # Orange
                else:
                    pdf.set_text_color(239, 68, 68) # Red
                pdf.cell(40, 10, f"{score}%", 0, 0)
                
                pdf.set_text_color(74, 85, 104)
                pdf.set_font("helvetica", "I", 11)
                pdf.cell(0, 10, f"Recommendation: {evaluation.get('recommendation', 'N/A')}", 0, 1, "R")
                
                # Breakdown
                pdf.ln(2)
                pdf.set_text_color(45, 55, 72)
                pdf.set_font("helvetica", "B", 10)
                pdf.cell(0, 6, f"Score Breakdown: Skills ({evaluation['breakdown']['skills_score']}%) | Experience ({evaluation['breakdown']['experience_score']}%) | Education ({evaluation['breakdown']['education_score']}%) | Projects ({evaluation['breakdown']['projects_score']}%)", 0, 1)
                
                pdf.ln(5)
                
                # Summary
                pdf.set_font("helvetica", "B", 12)
                pdf.cell(0, 8, "Suitability Summary", 0, 1)
                pdf.set_font("helvetica", "", 10)
                # Clean summary text
                summary_text = evaluation.get('suitability_summary', '').replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
                pdf.multi_cell(0, 5, summary_text)
                pdf.ln(4)
                
                # Strengths & Weaknesses
                pdf.set_font("helvetica", "B", 12)
                pdf.cell(95, 8, "Key Strengths", 0, 0)
                pdf.cell(95, 8, "Skill Gaps & Weaknesses", 0, 1)
                
                pdf.set_font("helvetica", "", 9)
                y_before = pdf.get_y()
                
                # Strengths Col
                pdf.set_x(10)
                strengths_text = "\n".join([f"- {s.replace('–', '-').replace('—', '-').replace('“', '\"').replace('”', '\"').replace('‘', '\'').replace('’', '\'')}" for s in evaluation.get('strengths', [])])
                pdf.multi_cell(90, 4.5, strengths_text)
                y_after_str = pdf.get_y()
                
                # Weaknesses Col
                pdf.set_y(y_before)
                pdf.set_x(105)
                weaknesses_text = "\n".join([f"- {w.replace('–', '-').replace('—', '-').replace('“', '\"').replace('”', '\"').replace('‘', '\'').replace('’', '\'')}" for w in evaluation.get('weaknesses', [])])
                pdf.multi_cell(90, 4.5, weaknesses_text)
                y_after_wk = pdf.get_y()
                
                max_y = max(y_after_str, y_after_wk)
                pdf.set_y(max_y + 6)
                
                # Skill Gap Table
                pdf.set_font("helvetica", "B", 12)
                pdf.cell(0, 8, "Skill Gap Details", 0, 1)
                
                pdf.set_font("helvetica", "B", 9)
                pdf.set_fill_color(241, 245, 249)
                pdf.cell(50, 6, "Skill", 1, 0, 'L', True)
                pdf.cell(30, 6, "Required", 1, 0, 'C', True)
                pdf.cell(30, 6, "Candidate Has", 1, 0, 'C', True)
                pdf.cell(80, 6, "Notes", 1, 1, 'L', True)
                
                pdf.set_font("helvetica", "", 8.5)
                for item in evaluation.get('skill_gap_analysis', [])[:12]: # Limit for page fit
                    note = item.get('notes', '')
                    note = note.replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
                    pdf.cell(50, 6, item['skill'].replace("–", "-").replace("—", "-"), 1, 0, 'L')
                    pdf.cell(30, 6, "Yes" if item.get('required', True) else "Preferred", 1, 0, 'C')
                    pdf.cell(30, 6, item.get('candidate_has', 'no').upper(), 1, 0, 'C')
                    pdf.cell(80, 6, note[:50], 1, 1, 'L')
                    
                # New Page for Interview Questions & Resume Suggestions
                pdf.add_page()
                
                # Questions if present
                pdf.set_font("helvetica", "B", 14)
                pdf.cell(0, 8, "Tailored Interview Questions", 0, 1)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)
                
                questions_list = evaluation.get('interview_questions', [])
                if not questions_list:
                    pdf.set_font("helvetica", "I", 10)
                    pdf.cell(0, 6, "No tailored interview questions generated.", 0, 1)
                else:
                    for i, q in enumerate(questions_list):
                        q_clean = q.replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
                        pdf.set_font("helvetica", "B", 10)
                        pdf.cell(0, 6, f"Question {i+1}:", 0, 1)
                        pdf.set_font("helvetica", "", 10)
                        pdf.multi_cell(0, 5, f'"{q_clean}"')
                        pdf.ln(2)
                
                pdf.ln(5)
                
                # Resume Suggestions
                pdf.set_font("helvetica", "B", 14)
                pdf.cell(0, 8, "Resume Improvement Suggestions", 0, 1)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)
                
                suggestions_list = evaluation.get('resume_suggestions', [])
                if not suggestions_list:
                    pdf.set_font("helvetica", "I", 10)
                    pdf.cell(0, 6, "No resume improvement suggestions generated.", 0, 1)
                else:
                    for sug in suggestions_list:
                        sug_clean = sug.replace("–", "-").replace("—", "-").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
                        pdf.set_font("helvetica", "", 10)
                        pdf.set_x(15)
                        pdf.cell(5, 5, "-", 0, 0, "C")
                        pdf.multi_cell(180, 5, sug_clean)
                        pdf.ln(1)
                
                # New Page for Raw Resume Text (Appendix)
                pdf.add_page()
                pdf.set_font("helvetica", "B", 14)
                pdf.cell(0, 8, "Appendix: Raw Resume Text", 0, 1)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                pdf.ln(4)
                
                pdf.set_font("helvetica", "", 7.5)
                raw_text = candidate.get("raw_text", "")
                cleaned_raw_text = raw_text.encode('latin-1', 'replace').decode('latin-1')
                pdf.multi_cell(0, 4, cleaned_raw_text[:4000] + "\n\n[... Truncated for PDF length ...]" if len(cleaned_raw_text) > 4000 else cleaned_raw_text)
                
                return pdf.output()
            
            pdf_data = generate_pdf_report(active_cand["resume_data"], active_jd, active_cand["eval_data"])
            
            st.download_button(
                label=f"📥 Download PDF Evaluation Report for {active_cand['name']}",
                data=bytes(pdf_data),
                file_name=f"TalentAI_Evaluation_{active_cand['name'].replace(' ', '_')}.pdf",
                mime="application/pdf"
            )

# ==========================================
# VIEW 2: JOB DESCRIPTIONS
# ==========================================
elif active_tab == "Job Descriptions":
    st.markdown("### 📋 Job Description Management")
    
    col_list, col_add = st.columns([1, 1])
    
    with col_list:
        st.markdown("##### Existing Job Descriptions")
        if not jds:
            st.info("No Job Descriptions added yet.")
        else:
            for jd_id, jd_data in jds.items():
                with st.expander(f"💼 {jd_data['title']}"):
                    st.markdown(f"**Experience Requirement:** {jd_data.get('experience_years', 'N/A')}")
                    st.markdown("**Required Skills:**")
                    st.markdown(" ".join([f"<span class='badge badge-blue'>{s}</span>" for s in jd_data['required_skills']]), unsafe_allow_html=True)
                    if jd_data.get('preferred_qualifications'):
                        st.markdown("**Preferred Qualifications:**")
                        for q in jd_data['preferred_qualifications']:
                            st.markdown(f"- {q}")
                    
                    st.markdown("---")
                    if st.button("🗑️ Delete Position", key=f"del_jd_{jd_id}"):
                        delete_jd(jd_id)
                        st.success(f"Position '{jd_data['title']}' deleted.")
                        st.rerun()
                        
    with col_add:
        st.markdown("##### Create / Analyze New Job Position")
        
        jd_title_input = st.text_input("Job Title", placeholder="e.g. Senior Backend Engineer")
        jd_text_input = st.text_area("Paste Job Description Text", placeholder="Paste the full JD requirements here...", height=250)
        
        # Templates
        st.markdown("**Or load a pre-configured template:**")
        t_col1, t_col2 = st.columns(2)
        with t_col1:
            if st.button("Backend Engineer Template", use_container_width=True):
                with open("data/sample_job_descriptions/software_engineer_jd.txt", "r", encoding="utf-8") as f:
                    st.session_state["jd_template_text"] = f.read()
                    st.session_state["jd_template_title"] = "Senior Python / Full-Stack Developer"
                    st.rerun()
        with t_col2:
            if st.button("Data Scientist Template", use_container_width=True):
                with open("data/sample_job_descriptions/data_scientist_jd.txt", "r", encoding="utf-8") as f:
                    st.session_state["jd_template_text"] = f.read()
                    st.session_state["jd_template_title"] = "Senior Data Scientist / Machine Learning Engineer"
                    st.rerun()
                    
        if "jd_template_text" in st.session_state:
            jd_text_input = st.session_state["jd_template_text"]
            jd_title_input = st.session_state["jd_template_title"]
            # Clean template from state
            del st.session_state["jd_template_text"]
            del st.session_state["jd_template_title"]
            st.rerun()
            
        if st.button("🔍 Analyze & Save Position", type="primary"):
            if not jd_title_input or not jd_text_input:
                st.error("Please provide both Job Title and Job Description text.")
            else:
                with st.spinner("Analyzing Job Description with AI..."):
                    # Analyze using AI or fallback
                    analyzed_data = analyze_job_description(jd_text_input, st.session_state["gemini_api_key"])
                    analyzed_data["raw_text"] = jd_text_input
                    
                    # Generate a unique ID
                    jd_id = "jd_" + re.sub(r'[^a-z0-9]', '_', jd_title_input.lower()) + "_" + datetime.now().strftime("%M%S")
                    
                    save_jd(jd_id, analyzed_data)
                    st.success(f"Position '{analyzed_data['title']}' analyzed and saved!")
                    st.session_state["selected_jd_id"] = jd_id
                    st.rerun()

# ==========================================
# VIEW 3: UPLOAD RESUMES
# ==========================================
elif active_tab == "Upload Resumes":
    st.markdown("### 📥 Upload Candidate Resumes")
    
    if not jds:
        st.info("Please create a **Job Description** first before uploading resumes.")
    else:
        # JD Selector
        jd_options = {v["title"]: k for k, v in jds.items()}
        selected_jd_title = st.selectbox(
            "Select Target Job Description for Screening",
            options=list(jd_options.keys()),
            index=list(jd_options.keys()).index(jds[st.session_state["selected_jd_id"]]["title"]) if st.session_state["selected_jd_id"] in jds.values() else 0
        )
        active_jd_id = jd_options[selected_jd_title]
        st.session_state["selected_jd_id"] = active_jd_id
        active_jd = jds[active_jd_id]
        
        # File uploader
        uploaded_files = st.file_uploader(
            "Upload Resumes (PDF Format)",
            type=["pdf"],
            accept_multiple_files=True,
            help="You can upload multiple candidate resumes in PDF format simultaneously."
        )
        
        if uploaded_files:
            st.markdown(f"**Selected Files ({len(uploaded_files)}):**")
            for f in uploaded_files:
                st.write(f"📄 {f.name} ({round(f.size/1024, 1)} KB)")
                
            if st.button("🚀 Process & Screen Resumes", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                num_files = len(uploaded_files)
                for idx, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Processing {uploaded_file.name} ({idx+1}/{num_files})...")
                    
                    # Save file locally
                    safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', uploaded_file.name)
                    file_path = os.path.join("data/uploaded_resumes", safe_filename)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                        
                    # 1. Extract raw text
                    resume_text = extract_text_from_pdf(file_path)
                    
                    # Generate candidate ID based on filename
                    cand_id = "cand_" + re.sub(r'[^a-z0-9]', '_', uploaded_file.name.lower().split('.pdf')[0]) + "_" + datetime.now().strftime("%H%M%S")
                    
                    # 2. Extract candidate structured info
                    status_text.text(f"Extracting candidate profile from {uploaded_file.name} using AI...")
                    resume_data = extract_candidate_info(resume_text, st.session_state["gemini_api_key"])
                    resume_data["raw_text"] = resume_text
                    resume_data["file_path"] = file_path
                    
                    # Save resume
                    save_resume(cand_id, resume_data)
                    
                    # 3. Match against selected JD
                    status_text.text(f"Evaluating and ranking {resume_data.get('name', uploaded_file.name)} against {active_jd['title']}...")
                    eval_data = match_candidate(resume_data, active_jd, st.session_state["gemini_api_key"])
                    
                    # Save evaluation
                    save_evaluation(cand_id, active_jd_id, eval_data)
                    
                    # Update progress
                    progress_bar.progress((idx + 1) / num_files)
                    
                status_text.text("Screening completed successfully!")
                st.success(f"Successfully processed and ranked {num_files} candidates against '{active_jd['title']}'.")
                
                # Navigate to dashboard
                st.session_state["active_tab"] = "Screening Dashboard"
                st.rerun()

# ==========================================
# VIEW 4: CANDIDATE COMPARISON
# ==========================================
elif active_tab == "Candidate Comparison":
    st.markdown("### 👥 Side-by-Side Candidate Comparison")
    
    if not jds:
        st.info("No Job Descriptions found.")
    else:
        # JD Selector
        jd_options = {v["title"]: k for k, v in jds.items()}
        selected_jd_title = st.selectbox(
            "Select Job Description to Compare Candidates",
            options=list(jd_options.keys()),
            index=list(jd_options.keys()).index(jds[st.session_state["selected_jd_id"]]["title"]) if st.session_state["selected_jd_id"] in jds.values() else 0
        )
        active_jd_id = jd_options[selected_jd_title]
        st.session_state["selected_jd_id"] = active_jd_id
        
        evaluations = get_evaluations_for_jd(active_jd_id)
        
        if not evaluations or len(evaluations) < 2:
            st.warning("You need at least 2 candidates evaluated for this Job Description to perform a comparison. Currently there are " + str(len(evaluations)) + " candidates.")
        else:
            # Multi-select candidates
            cand_names = [resumes[r_id]["name"] for r_id in evaluations.keys() if r_id in resumes]
            selected_cands = st.multiselect(
                "Select Candidates to Compare (Max 3)",
                options=cand_names,
                default=cand_names[:min(3, len(cand_names))]
            )
            
            if len(selected_cands) < 2:
                st.info("Please select at least 2 candidates to compare.")
            elif len(selected_cands) > 3:
                st.error("Please select a maximum of 3 candidates for optimal side-by-side comparison.")
            else:
                # Load selected candidates' data
                comparison_list = []
                for name in selected_cands:
                    # Find candidate ID
                    r_id = next(rid for rid, rdata in resumes.items() if rdata["name"] == name)
                    eval_data = evaluations[r_id]
                    comparison_list.append({
                        "id": r_id,
                        "name": name,
                        "resume": resumes[r_id],
                        "evaluation": eval_data
                    })
                
                # Visual Comparison Chart (Radar Chart or Grouped Bar Chart)
                fig_comp = go.Figure()
                
                categories = ['Skills', 'Experience', 'Education', 'Projects', 'Overall Match']
                colors = ["#6366f1", "#f472b6", "#34d399"]
                
                for idx, item in enumerate(comparison_list):
                    eval_data = item["evaluation"]
                    scores = [
                        eval_data["breakdown"]["skills_score"],
                        eval_data["breakdown"]["experience_score"],
                        eval_data["breakdown"]["education_score"],
                        eval_data["breakdown"]["projects_score"],
                        eval_data["matching_score"]
                    ]
                    
                    fig_comp.add_trace(go.Bar(
                        x=categories,
                        y=scores,
                        name=item["name"],
                        marker_color=colors[idx]
                    ))
                    
                fig_comp.update_layout(
                    title=dict(text="Score Comparison", font={'size': 16, 'color': '#f1f5f9', 'family': 'Outfit'}),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font={'color': "#f1f5f9", 'family': "Outfit"},
                    height=350,
                    barmode='group',
                    yaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,0.05)"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                
                st.plotly_chart(fig_comp, use_container_width=True)
                
                # Side-by-side Cards
                cols = st.columns(len(comparison_list))
                
                for idx, col in enumerate(cols):
                    item = comparison_list[idx]
                    resume = item["resume"]
                    eval_data = item["evaluation"]
                    score = eval_data["matching_score"]
                    
                    if score >= 80:
                        score_class = "score-high"
                    elif score >= 60:
                        score_class = "score-medium"
                    else:
                        score_class = "score-low"
                        
                    with col:
                        st.markdown(
                            clean_html(f"""
                            <div class='glass-card' style='height: 100%;'>
                                <div style='text-align:center; margin-bottom:1rem;'>
                                    <span class='score-badge {score_class}'>{score}%</span>
                                    <h3 style='margin:0.75rem 0 0 0; color:#f1f5f9;'>{item['name']}</h3>
                                    <span class='badge badge-blue'>{eval_data['recommendation'].split(' - ')[0]}</span>
                                </div>
                                <hr style='border-color:rgba(255,255,255,0.05);'/>
                                <p><strong>Education:</strong> {resume['education'][0]['degree']} from {resume['education'][0]['institution']}</p>
                                <p><strong>Primary Skills:</strong> {", ".join(resume['skills'][:8])}</p>
                                <h5 style='color:#34d399; margin-top:1rem;'>💪 Core Strengths:</h5>
                                <ul>
                                    {"".join([f"<li>{s}</li>" for s in eval_data['strengths'][:3]])}
                                </ul>
                                <h5 style='color:#f472b6; margin-top:1rem;'>⚠️ Key Gaps:</h5>
                                <ul>
                                    {"".join([f"<li>{w}</li>" for w in eval_data['weaknesses'][:3]])}
                                </ul>
                            </div>
                            """),
                            unsafe_allow_html=True
                        )

# ==========================================
# VIEW 5: AI RECRUITER CHAT
# ==========================================
elif active_tab == "AI Recruiter Chat":
    st.markdown("### 💬 AI Recruiter Chat Assistant")
    st.caption("Ask specific questions about any candidate, draft outreach emails, or compare qualifications interactively.")
    
    if not resumes:
        st.info("No candidates available. Please upload resumes first.")
    elif not jds:
        st.info("No Job Descriptions available.")
    else:
        # Select active candidate to chat about
        cand_options = {v["name"]: k for k, v in resumes.items()}
        selected_cand_name = st.selectbox(
            "Select Candidate to discuss:",
            options=list(cand_options.keys())
        )
        active_cand_id = cand_options[selected_cand_name]
        active_resume = resumes[active_cand_id]
        
        # Select active JD
        jd_options = {v["title"]: k for k, v in jds.items()}
        selected_jd_title = st.selectbox(
            "Select Job Position context:",
            options=list(jd_options.keys()),
            index=list(jd_options.keys()).index(jds[st.session_state["selected_jd_id"]]["title"]) if st.session_state["selected_jd_id"] in jds.values() else 0
        )
        active_jd_id = jd_options[selected_jd_title]
        active_jd = jds[active_jd_id]
        
        # Fetch evaluation
        eval_data = get_evaluation(active_cand_id, active_jd_id)
        if not eval_data:
            # If no evaluation exists, compute a quick local one
            from utils.ai_engine import run_local_matching
            eval_data = run_local_matching(active_resume, active_jd)
            save_evaluation(active_cand_id, active_jd_id, eval_data)
            
        # Chat history for this candidate-job pair
        chat_key = f"{active_cand_id}#{active_jd_id}"
        if chat_key not in st.session_state["chat_history"]:
            st.session_state["chat_history"][chat_key] = [
                {
                    "is_user": False,
                    "message": f"Hi! I've analyzed **{selected_cand_name}** for the **{selected_jd_title}** role. Their overall match score is **{eval_data['matching_score']}%**. Ask me anything about their skills, experience, or suitability!"
                }
            ]
            
        # Clear chat button
        if st.button("🧹 Clear Chat History", key="clear_chat_btn"):
            st.session_state["chat_history"][chat_key] = [
                {
                    "is_user": False,
                    "message": f"Hi! I've analyzed **{selected_cand_name}** for the **{selected_jd_title}** role. Their overall match score is **{eval_data['matching_score']}%**. Ask me anything about their skills, experience, or suitability!"
                }
            ]
            st.rerun()
            
        # Render Chat Container
        chat_container_html = "<div class='chat-container'>"
        for chat in st.session_state["chat_history"][chat_key]:
            bubble_class = "chat-bubble-user" if chat["is_user"] else "chat-bubble-ai"
            chat_container_html += f"""
                <div class='chat-bubble {bubble_class}'>
                    {chat['message']}
                </div>
            """
        chat_container_html += "</div>"
        st.markdown(clean_html(chat_container_html), unsafe_allow_html=True)
        
        # Chat Input Form
        with st.form("chat_form", clear_on_submit=True):
            user_msg = st.text_input("Message the AI Recruiter...", placeholder=f"e.g., Does {selected_cand_name.split(' ')[0]} have experience with AWS?")
            submit_chat = st.form_submit_button("Send")
            
            if submit_chat and user_msg:
                # Add user message
                st.session_state["chat_history"][chat_key].append({
                    "is_user": True,
                    "message": user_msg
                })
                
                # Get AI Response
                with st.spinner("AI Recruiter is thinking..."):
                    ai_response = chat_about_candidate(
                        active_resume,
                        active_jd,
                        eval_data,
                        st.session_state["chat_history"][chat_key][:-1], # exclude current msg for context to avoid loop
                        user_msg,
                        st.session_state["gemini_api_key"]
                    )
                    
                # Add AI response
                st.session_state["chat_history"][chat_key].append({
                    "is_user": False,
                    "message": ai_response
                })
                st.rerun()
