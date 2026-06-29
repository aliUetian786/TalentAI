import json
import os

DB_FILE = "data/db.json"

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    if not os.path.exists(DB_FILE):
        default_db = {
            "resumes": {},
            "job_descriptions": {},
            "evaluations": {}
        }
        save_db(default_db)

def load_db():
    init_db()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading database: {e}")
        return {"resumes": {}, "job_descriptions": {}, "evaluations": {}}

def save_db(db_data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db_data, f, indent=4)
    except Exception as e:
        print(f"Error saving database: {e}")

# Resume Operations
def save_resume(resume_id, resume_data):
    db = load_db()
    db["resumes"][resume_id] = resume_data
    save_db(db)

def get_resumes():
    db = load_db()
    return db["resumes"]

def get_resume(resume_id):
    db = load_db()
    return db["resumes"].get(resume_id)

def delete_resume(resume_id):
    db = load_db()
    if resume_id in db["resumes"]:
        del db["resumes"][resume_id]
        # Clean up associated evaluations
        eval_keys_to_delete = [k for k in db["evaluations"] if k.startswith(f"{resume_id}#")]
        for k in eval_keys_to_delete:
            del db["evaluations"][k]
        save_db(db)

# Job Description Operations
def save_jd(jd_id, jd_data):
    db = load_db()
    db["job_descriptions"][jd_id] = jd_data
    save_db(db)

def get_jds():
    db = load_db()
    return db["job_descriptions"]

def get_jd(jd_id):
    db = load_db()
    return db["job_descriptions"].get(jd_id)

def delete_jd(jd_id):
    db = load_db()
    if jd_id in db["job_descriptions"]:
        del db["job_descriptions"][jd_id]
        # Clean up associated evaluations
        eval_keys_to_delete = [k for k in db["evaluations"] if k.endswith(f"#{jd_id}")]
        for k in eval_keys_to_delete:
            del db["evaluations"][k]
        save_db(db)

# Evaluation Operations
def save_evaluation(resume_id, jd_id, evaluation_data):
    db = load_db()
    key = f"{resume_id}#{jd_id}"
    db["evaluations"][key] = evaluation_data
    save_db(db)

def get_evaluation(resume_id, jd_id):
    db = load_db()
    key = f"{resume_id}#{jd_id}"
    return db["evaluations"].get(key)

def get_evaluations_for_jd(jd_id):
    db = load_db()
    evals = {}
    for key, val in db["evaluations"].items():
        res_id, j_id = key.split("#")
        if j_id == jd_id:
            evals[res_id] = val
    return evals

def clear_db():
    db = {
        "resumes": {},
        "job_descriptions": {},
        "evaluations": {}
    }
    save_db(db)
