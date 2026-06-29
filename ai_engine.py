import os
import json
import re

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False
    genai = None


def clean_and_parse_json(text):
    """
    Cleans up markdown code blocks from LLM output and parses the JSON.
    """
    # Remove markdown code blocks if present
    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = text.strip()
    
    # Try to find a JSON object or list within the text if there is trailing garbage
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first '{' or '[' and last '}' or ']'
        start_obj = text.find('{')
        end_obj = text.rfind('}')
        start_arr = text.find('[')
        end_arr = text.rfind(']')
        
        # Decide which one is outer
        if start_obj != -1 and (start_arr == -1 or start_obj < start_arr):
            if end_obj != -1:
                try:
                    return json.loads(text[start_obj:end_obj+1])
                except json.JSONDecodeError:
                    pass
        elif start_arr != -1:
            if end_arr != -1:
                try:
                    return json.loads(text[start_arr:end_arr+1])
                except json.JSONDecodeError:
                    pass
        raise

def get_gemini_model(api_key):
    """
    Initializes and returns the Gemini model.
    """
    if not HAS_GEMINI:
        return None
        
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        return None

        
    try:
        genai.configure(api_key=api_key)
        # Use gemini-1.5-flash as it is highly efficient and supports structured output
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        return None

def extract_candidate_info(resume_text, api_key=None):
    """
    Extracts structured candidate information from resume text using Gemini,
    with a local rule-based fallback if Gemini is not available.
    """
    model = get_gemini_model(api_key)
    
    if model:
        prompt = f"""
        You are an expert HR assistant. Extract the candidate information from the following resume text.
        Respond ONLY with a valid JSON object matching this schema. Do not add any conversational text or markdown formatting outside of the JSON.
        
        {{
          "name": "Candidate Name",
          "email": "email@example.com",
          "phone": "Phone Number",
          "skills": ["Skill1", "Skill2", "Skill3"],
          "education": [
            {{
              "degree": "Degree Name (e.g., B.S. in Computer Science)",
              "institution": "University/Institution Name",
              "year": "Year or Range (e.g., 2016 - 2020)"
            }}
          ],
          "work_experience": [
            {{
              "role": "Job Title",
              "company": "Company Name",
              "duration": "Duration (e.g., 2022 - Present)",
              "bullets": ["Responsibility or accomplishment 1", "Responsibility or accomplishment 2"]
            }}
          ],
          "projects": [
            {{
              "name": "Project Name",
              "description": "Short description of the project and technologies used"
            }}
          ],
          "certifications": ["Certification 1", "Certification 2"],
          "summary": "A short, professional summary of the candidate's background."
        }}

        Resume Text:
        {resume_text}
        """
        try:
            response = model.generate_content(prompt)
            return clean_and_parse_json(response.text)
        except Exception as e:
            print(f"Gemini extraction failed, using fallback: {e}")
            
    # Fallback Mechanism
    return run_local_resume_extraction(resume_text)

def analyze_job_description(jd_text, api_key=None):
    """
    Analyzes the job description and extracts requirements.
    """
    model = get_gemini_model(api_key)
    
    if model:
        prompt = f"""
        You are an expert technical recruiter. Analyze the following job description and extract structured requirements.
        Respond ONLY with a valid JSON object matching this schema. Do not add any conversational text or markdown formatting outside of the JSON.
        
        {{
          "title": "Job Title",
          "required_skills": ["Skill1", "Skill2", "Skill3"],
          "preferred_qualifications": ["Qualification1", "Qualification2"],
          "experience_years": "e.g., 5+ years",
          "requirements_summary": "A brief summary of the ideal candidate and core responsibilities."
        }}

        Job Description:
        {jd_text}
        """
        try:
            response = model.generate_content(prompt)
            return clean_and_parse_json(response.text)
        except Exception as e:
            print(f"Gemini JD analysis failed, using fallback: {e}")
            
    # Fallback Mechanism
    return run_local_jd_analysis(jd_text)

def match_candidate(resume_data, jd_data, api_key=None):
    """
    Matches the candidate resume data against the job description requirements.
    """
    model = get_gemini_model(api_key)
    
    if model:
        prompt = f"""
        You are an expert AI talent acquisition specialist. Compare the candidate's resume data against the job description requirements.
        Provide an objective and thorough evaluation.
        Respond ONLY with a valid JSON object matching this schema. Do not add any conversational text or markdown formatting outside of the JSON.
        
        {{
          "matching_score": 85, // An integer between 0 and 100 representing overall suitability
          "breakdown": {{
            "skills_score": 90, // score 0-100 for skill overlap
            "experience_score": 80, // score 0-100 for experience match (years, roles)
            "education_score": 85, // score 0-100 for education suitability
            "projects_score": 85 // score 0-100 for relevance of projects
          }},
          "strengths": ["Strength 1 (specific to resume vs JD)", "Strength 2"],
          "weaknesses": ["Gap/Weakness 1 (specific to resume vs JD)", "Gap/Weakness 2"],
          "suitability_summary": "A detailed explanation of why the candidate is or isn't a good fit.",
          "recommendation": "Shortlist / Interview / Keep on File / Reject with a 1-sentence reason.",
          "skill_gap_analysis": [
            {{
              "skill": "Skill Name", 
              "required": true, // true if it's a core requirement, false if preferred/optional
              "candidate_has": "yes", // 'yes', 'no', or 'partial'
              "notes": "Brief explanation of where in the resume this skill is shown, or what is missing."
            }}
          ],
          "interview_questions": [
            "Highly specific interview question 1 targeting their skill gaps",
            "Highly specific interview question 2",
            "Highly specific interview question 3",
            "Highly specific interview question 4",
            "Highly specific interview question 5"
          ],
          "resume_suggestions": [
            "Actionable resume improvement suggestion 1",
            "Actionable resume improvement suggestion 2",
            "Actionable resume improvement suggestion 3"
          ]
        }}

        Candidate Resume:
        {json.dumps(resume_data, indent=2)}

        Job Description:
        {json.dumps(jd_data, indent=2)}
        """
        try:
            response = model.generate_content(prompt)
            result = clean_and_parse_json(response.text)
            # Ensure the new fields are present
            if "interview_questions" not in result:
                result["interview_questions"] = generate_interview_questions(resume_data, jd_data, result, api_key)
            if "resume_suggestions" not in result:
                result["resume_suggestions"] = generate_resume_suggestions(resume_data, jd_data, result, api_key)
            return result
        except Exception as e:
            print(f"Gemini matching failed, using fallback: {e}")
            
    # Fallback Mechanism
    return run_local_matching(resume_data, jd_data)

def generate_interview_questions(resume_data, jd_data, evaluation_data, api_key=None):
    """
    Generates tailored interview questions based on the candidate's gaps and strengths.
    """
    model = get_gemini_model(api_key)
    
    if model:
        prompt = f"""
        You are a hiring manager interviewing {resume_data.get('name', 'the candidate')} for the position of {jd_data.get('title', 'the role')}.
        Generate 5 custom, highly specific technical and behavioral interview questions designed to probe their experience, verify their skills, and explore the identified weaknesses/gaps.
        
        Candidate Resume Summary: {resume_data.get('summary', '')}
        Strengths: {json.dumps(evaluation_data.get('strengths', []))}
        Gaps/Weaknesses: {json.dumps(evaluation_data.get('weaknesses', []))}
        
        Respond ONLY with a valid JSON array of strings containing the 5 questions. Do not add any conversational text or markdown formatting.
        """
        try:
            response = model.generate_content(prompt)
            return clean_and_parse_json(response.text)
        except Exception as e:
            print(f"Gemini interview questions failed, using fallback: {e}")
            
    # Fallback
    return [
        f"Can you explain your experience working with {jd_data.get('required_skills', ['core technologies'])[0] if jd_data.get('required_skills') else 'the required technologies'} in your past projects?",
        "Describe a challenging technical problem you solved recently. What was your approach and the outcome?",
        "How do you keep your technical skills up to date with rapidly evolving industry standards?",
        "Explain a time when you had to work with a technology you were not familiar with. How did you adapt?",
        f"Based on the role requirements for {jd_data.get('title', 'this role')}, how would you describe your team collaboration and communication style?"
    ]

def generate_resume_suggestions(resume_data, jd_data, evaluation_data, api_key=None):
    """
    Generates recommendations to improve the candidate's resume.
    """
    model = get_gemini_model(api_key)
    
    if model:
        prompt = f"""
        You are a career coach. Suggest 3 to 5 actionable improvements for {resume_data.get('name', 'the candidate')} to tailer their resume for the {jd_data.get('title', 'the role')} position.
        Be specific about what skills to highlight, what projects to detail, or how to rephrase their experience to match the JD requirements.
        
        Candidate Resume: {json.dumps(resume_data, indent=2)}
        Gaps/Weaknesses: {json.dumps(evaluation_data.get('weaknesses', []))}
        
        Respond ONLY with a valid JSON array of strings containing the suggestions. Do not add any conversational text or markdown formatting.
        """
        try:
            response = model.generate_content(prompt)
            return clean_and_parse_json(response.text)
        except Exception as e:
            print(f"Gemini resume suggestions failed, using fallback: {e}")
            
    # Fallback
    return [
        "Add more quantifiable achievements in your work experience bullet points (e.g., 'improved performance by 20%').",
        f"Highlight experience with missing skills like {', '.join([g['skill'] for g in evaluation_data.get('skill_gap_analysis', []) if g['candidate_has'] == 'no'][:3])}.",
        "Elaborate on the technical architecture of your projects, mentioning specific design patterns and database decisions.",
        "Ensure your professional summary directly addresses the domain of the job description."
    ]

def chat_about_candidate(resume_data, jd_data, evaluation_data, chat_history, user_message, api_key=None):
    """
    Handles a chat conversation about the candidate.
    """
    model = get_gemini_model(api_key)
    
    context = f"""
    You are an expert recruitment assistant. You are discussing the candidate '{resume_data.get('name', 'Unknown')}' who has applied for the job '{jd_data.get('title', 'Unknown')}'.
    
    Here is the candidate's resume data:
    {json.dumps(resume_data, indent=2)}
    
    Here is the job description:
    {json.dumps(jd_data, indent=2)}
    
    Here is the AI evaluation:
    {json.dumps(evaluation_data, indent=2)}
    
    Answer the user's question accurately and professionally, referencing the candidate's actual experience and how it aligns with the job requirements. Keep answers concise, objective, and helpful.
    """
    
    if model:
        # Format chat history for Gemini API
        messages = [{"role": "user", "parts": [context]}]
        for chat in chat_history:
            messages.append({"role": "user" if chat["is_user"] else "model", "parts": [chat["message"]]})
        messages.append({"role": "user", "parts": [user_message]})
        
        try:
            response = model.generate_content(messages)
            return response.text
        except Exception as e:
            print(f"Gemini chat failed: {e}")
            return f"Error communicating with Gemini: {e}. (Local fallback: The candidate has skills: {', '.join(resume_data.get('skills', []))})"
            
    # Simple Local Chat Fallback
    user_message_lower = user_message.lower()
    if "skill" in user_message_lower:
        return f"Based on the resume, {resume_data.get('name')} possesses the following skills: {', '.join(resume_data.get('skills', []))}. Key required skills for the role are: {', '.join(jd_data.get('required_skills', []))}."
    elif "experience" in user_message_lower or "work" in user_message_lower:
        exp_list = [f"{e.get('role')} at {e.get('company')} ({e.get('duration')})" for e in resume_data.get('work_experience', [])]
        return f"{resume_data.get('name')}'s work experience includes: {'; '.join(exp_list)}. The job requires {jd_data.get('experience_years')}."
    elif "education" in user_message_lower or "study" in user_message_lower:
        edu_list = [f"{e.get('degree')} from {e.get('institution')} ({e.get('year')})" for e in resume_data.get('education', [])]
        return f"{resume_data.get('name')} studied: {', '.join(edu_list)}."
    else:
        return f"I can help you analyze {resume_data.get('name')}'s profile. They have an overall matching score of {evaluation_data.get('matching_score')}% for the '{jd_data.get('title')}' position. Ask me about their skills, experience, or education!"


# ==========================================
# LOCAL FALLBACK IMPLEMENTATION DETAILS
# ==========================================

def run_local_resume_extraction(text):
    """
    Extracts basic structured data using regex and keyword matching when Gemini is offline.
    """
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    
    email_match = re.search(email_pattern, text)
    phone_match = re.search(phone_pattern, text)
    
    email = email_match.group(0) if email_match else "N/A"
    phone = phone_match.group(0) if phone_match else "N/A"
    
    # Simple name heuristic (first few capitalized/all-caps words)
    name = "Candidate Name"
    ignore_keywords = {
        "resume", "cv", "curriculum", "vitae", "page", "contact", "profile", "summary",
        "computer", "engineering", "science", "developer", "analyst", "manager", "engineer",
        "designer", "student", "university", "technology", "systems", "solutions", "software",
        "data", "scientist", "technical", "product", "lead", "senior", "junior"
    }
    
    # Extract words, filtering out punctuation and ignored keywords
    words = []
    for w in re.sub(r'[^a-zA-Z\s]', ' ', text).split():
        if w.lower() not in ignore_keywords and len(w) > 1:
            words.append(w)
            
    for i in range(min(10, len(words) - 1)):
        w1, w2 = words[i], words[i+1]
        # Check if both words are capitalized or all-caps
        if (w1.istitle() or w1.isupper()) and (w2.istitle() or w2.isupper()):
            # Titlecase nicely (e.g. "ALI RAZA" -> "Ali Raza")
            name = f"{w1.capitalize()} {w2.capitalize()}"
            break

    # Extract skills by matching a predefined dictionary of common technical & soft skills
    common_skills = [
        "python", "javascript", "java", "c++", "c#", "ruby", "php", "sql", "html", "css",
        "react", "angular", "vue", "django", "flask", "spring", "node", "express",
        "aws", "azure", "gcp", "docker", "kubernetes", "git", "ci/cd", "agile", "scrum",
        "machine learning", "deep learning", "nlp", "pytorch", "tensorflow", "scikit-learn",
        "pandas", "numpy", "tableau", "powerbi", "jira", "confluence", "product strategy",
        "roadmap", "wireframing", "user research", "mixpanel", "figma", "project management",
        "communication", "leadership", "problem solving"
    ]
    
    found_skills = []
    text_lower = text.lower()
    for skill in common_skills:
        # Use word boundaries for short skills like R, SQL, Git to avoid false matches inside other words
        if len(skill) <= 4:
            pattern = r'\b' + re.escape(skill) + r'\b'
        else:
            pattern = re.escape(skill)
            
        if re.search(pattern, text_lower):
            # Capitalize nicely
            if skill in ["aws", "gcp", "sql", "html", "css", "nlp", "ci/cd"]:
                found_skills.append(skill.upper())
            elif skill in ["react", "django", "flask", "pytorch", "tensorflow", "git", "figma", "jira", "tableau"]:
                found_skills.append(skill.capitalize())
            elif skill == "react.js" or skill == "react":
                found_skills.append("React.js")
            elif skill == "scikit-learn":
                found_skills.append("Scikit-Learn")
            else:
                found_skills.append(titlecase_skill(skill))
                
    # Deduplicate skills
    found_skills = list(set(found_skills))
    if not found_skills:
        found_skills = ["Python", "SQL", "Git", "Project Management"] # Default fallback skills

    # Attempt to extract education
    education = []
    edu_keywords = ["university", "college", "institute", "school", "bs", "ms", "phd", "bachelor", "master", "degree"]
    sentences = re.split(r'[.!?\n]', text)
    for sent in sentences:
        sent_lower = sent.lower()
        if any(kw in sent_lower for kw in edu_keywords):
            # Look for years
            year_match = re.search(r'\b(20\d{2})\b', sent)
            year = year_match.group(1) if year_match else "N/A"
            
            # Simple clean up of sentence
            clean_sent = re.sub(r'\s+', ' ', sent).strip()
            if len(clean_sent) > 15 and len(clean_sent) < 100:
                education.append({
                    "degree": "Degree/Program",
                    "institution": clean_sent,
                    "year": year
                })
                if len(education) >= 2:
                    break
                    
    if not education:
        education = [{"degree": "Bachelor's Degree", "institution": "State University", "year": "2018 - 2022"}]

    # Stub experience, projects, certifications for fallback
    work_experience = [
        {
            "role": "Software Engineer / Professional",
            "company": "Company Corp",
            "duration": "2022 - Present",
            "bullets": [
                "Responsible for developing core features and collaborating with team members.",
                "Improved workflow efficiency and resolved critical system issues."
            ]
        }
    ]
    
    projects = [
        {
            "name": "Personal Portfolio & Capstone Project",
            "description": "Developed a custom web application demonstrating core technical skills and database integration."
        }
    ]
    
    certifications = ["Professional Certification"]
    
    # Try to extract job title/domain from text
    domain_title = "Professional"
    if "data scientist" in text_lower or "machine learning" in text_lower or "data science" in text_lower:
        domain_title = "Data Scientist"
    elif "product manager" in text_lower or "pm" in text_lower:
        domain_title = "Product Manager"
    elif "software engineer" in text_lower or "developer" in text_lower:
        domain_title = "Software Engineer"

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": found_skills,
        "education": education,
        "work_experience": work_experience,
        "projects": projects,
        "certifications": certifications,
        "summary": f"Accomplished {domain_title} with skills in {', '.join(found_skills[:5])}. Strong background in problem-solving and technical execution."
    }

def run_local_jd_analysis(text):
    """
    Analyzes job description using simple keyword extraction when Gemini is offline.
    """
    text_lower = text.lower()
    
    # Extract Title
    title = "Job Position"
    lines = text.split('\n')
    for line in lines[:5]:
        if "title" in line.lower() or "position" in line.lower() or "role" in line.lower():
            title = line.split(':')[-1].strip()
            break
    if title == "Job Position" and len(lines) > 0:
        title = lines[0].strip()

    # Extract Skills
    common_skills = [
        "python", "javascript", "java", "c++", "c#", "ruby", "php", "sql", "html", "css",
        "react", "angular", "vue", "django", "flask", "spring", "node", "express",
        "aws", "azure", "gcp", "docker", "kubernetes", "git", "ci/cd", "agile", "scrum",
        "machine learning", "deep learning", "nlp", "pytorch", "tensorflow", "scikit-learn",
        "pandas", "numpy", "tableau", "powerbi", "jira", "confluence", "product strategy",
        "roadmap", "wireframing", "user research", "mixpanel", "figma"
    ]
    
    required_skills = []
    for skill in common_skills:
        if len(skill) <= 4:
            pattern = r'\b' + re.escape(skill) + r'\b'
        else:
            pattern = re.escape(skill)
            
        if re.search(pattern, text_lower):
            if skill in ["aws", "gcp", "sql", "html", "css", "nlp", "ci/cd"]:
                required_skills.append(skill.upper())
            elif skill in ["react", "django", "flask", "pytorch", "tensorflow", "git", "figma", "jira", "tableau"]:
                required_skills.append(skill.capitalize())
            else:
                required_skills.append(titlecase_skill(skill))

    required_skills = list(set(required_skills))
    if not required_skills:
        required_skills = ["Python", "SQL", "Collaboration"]

    # Experience Years
    exp_match = re.search(r'(\d+)\+?\s*(year|yr)s?', text_lower)
    exp_years = f"{exp_match.group(1)}+ years" if exp_match else "3+ years"

    return {
        "title": title,
        "required_skills": required_skills,
        "preferred_qualifications": ["Strong communication skills", "Degree in Computer Science or related field"],
        "experience_years": exp_years,
        "requirements_summary": f"Seeking a qualified {title} with expertise in {', '.join(required_skills[:4])} and at least {exp_years} of experience."
    }

def run_local_matching(resume, jd):
    """
    Computes a mock matching score based on skill intersection and text overlap when Gemini is offline.
    """
    resume_skills = set([s.lower() for s in resume.get("skills", [])])
    jd_skills = set([s.lower() for s in jd.get("required_skills", [])])
    
    # Calculate skill overlap
    matching_skills = resume_skills.intersection(jd_skills)
    missing_skills = jd_skills - resume_skills
    
    skills_score = int((len(matching_skills) / len(jd_skills)) * 100) if jd_skills else 70
    
    # Mock scores for experience, education, projects
    # We can randomize slightly or base them on length of lists
    exp_score = min(60 + len(resume.get("work_experience", [])) * 10, 95)
    edu_score = 85 if len(resume.get("education", [])) > 0 else 50
    proj_score = min(70 + len(resume.get("projects", [])) * 10, 95)
    
    overall_score = int((skills_score * 0.4) + (exp_score * 0.3) + (edu_score * 0.2) + (proj_score * 0.1))
    
    # Strengths and Weaknesses
    strengths = []
    if matching_skills:
        strengths.append(f"Possesses core required skills: {', '.join(list(matching_skills)[:3])}.")
    if len(resume.get("work_experience", [])) > 1:
        strengths.append("Demonstrates solid professional work history.")
    if len(resume.get("projects", [])) > 0:
        strengths.append("Has practical project portfolio demonstrating application of skills.")
    if not strengths:
        strengths.append("Has a clean resume layout with clear sections.")

    weaknesses = []
    if missing_skills:
        weaknesses.append(f"Lacks explicit mention of skills: {', '.join(list(missing_skills)[:3])}.")
    if len(resume.get("work_experience", [])) <= 1:
        weaknesses.append("Limited work experience in the industry.")
    if not weaknesses:
        weaknesses.append("Could benefit from adding more quantifiable metrics to project outcomes.")

    # Skill gap analysis
    skill_gap_analysis = []
    for skill in jd.get("required_skills", []):
        has_it = "no"
        notes = "Not found in resume."
        for r_skill in resume.get("skills", []):
            if r_skill.lower() == skill.lower():
                has_it = "yes"
                notes = f"Explicitly listed under skills."
                break
        skill_gap_analysis.append({
            "skill": skill,
            "required": True,
            "candidate_has": has_it,
            "notes": notes
        })

    recommendation = "Shortlist"
    if overall_score >= 80:
        recommendation = "Shortlist for Interview - Candidate is highly qualified."
    elif overall_score >= 60:
        recommendation = "Interview - Candidate meets basic requirements, but has minor skill gaps."
    else:
        recommendation = "Keep on File - Candidate has significant skill gaps for this role."

    # Generate local interview questions
    local_questions = [
        f"Can you explain your experience working with {jd.get('required_skills', ['core technologies'])[0] if jd.get('required_skills') else 'the required technologies'} in your past projects?",
        "Describe a challenging technical problem you solved recently. What was your approach and the outcome?",
        "How do you keep your technical skills up to date with rapidly evolving industry standards?",
        "Explain a time when you had to work with a technology you were not familiar with. How did you adapt?",
        f"Based on the role requirements for {jd.get('title', 'this role')}, how would you describe your team collaboration and communication style?"
    ]
    
    # Generate local resume suggestions
    local_suggestions = [
        "Add more quantifiable achievements in your work experience bullet points (e.g., 'improved performance by 20%').",
        f"Highlight experience with missing skills like {', '.join([g['skill'] for g in skill_gap_analysis if g['candidate_has'] == 'no'][:3]) if [g['skill'] for g in skill_gap_analysis if g['candidate_has'] == 'no'] else 'the required skills'}.",
        "Elaborate on the technical architecture of your projects, mentioning specific design patterns and database decisions.",
        "Ensure your professional summary directly addresses the domain of the job description."
    ]

    return {
        "matching_score": overall_score,
        "breakdown": {
            "skills_score": skills_score,
            "experience_score": exp_score,
            "education_score": edu_score,
            "projects_score": proj_score
        },
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suitability_summary": f"The candidate matches {overall_score}% of the requirements. They have good alignment in {', '.join(list(matching_skills)[:2])} but lack {', '.join(list(missing_skills)[:2]) if missing_skills else 'critical gaps'}.",
        "recommendation": recommendation,
        "skill_gap_analysis": skill_gap_analysis,
        "interview_questions": local_questions,
        "resume_suggestions": local_suggestions
    }

def titlecase_skill(skill):
    words = skill.split()
    return " ".join([w.capitalize() for w in words])
