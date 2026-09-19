from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import database

app = FastAPI()
database.init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

class LoginRequest(BaseModel):
    username: str
    password: str

class RecordRequest(BaseModel):
    student_id: int
    subject: str
    date: str
    lesson_num: int
    value: str

class ProfileUpdateRequest(BaseModel):
    user_id: int
    new_username: str
    new_password: str

class TopicSchema(BaseModel):
    subject: str
    date: str
    lesson_num: int
    topic: str

@app.post("/api/login")
def login(data: LoginRequest):
    user = database.authenticate_user(data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return {
        "id": user[0],
        "username": user[1],
        "full_name": user[2],
        "subject": user[3],
        "is_curator": bool(user[4])
    }

@app.post("/api/update_profile")
def update_profile(data: ProfileUpdateRequest):
    ok, msg = database.update_user_credentials(data.user_id, data.new_username, data.new_password)
    return {"success": ok, "message": msg}

@app.get("/api/students")
def get_students():
    return database.get_all_students()

@app.get("/api/teacher_records")
def get_teacher_records(subject: str, date: str, l1: int = 1, l2: int = 2):
    return database.get_teacher_records_for_date(subject, date, l1, l2)

@app.post("/api/save_record")
def save_record(data: RecordRequest):
    database.add_or_update_record(data.student_id, data.subject, data.date, data.lesson_num, data.value)
    return {"status": "success"}

@app.get("/api/curator/by_date")
def get_by_date(date: str, subject: str):
    return database.get_curator_grid_by_date(date, subject)

@app.get("/api/curator/student_history/{student_id}")
def get_student_history(student_id: int):
    return database.get_student_history(student_id)

@app.get("/api/subjects")
def get_subjects():
    return database.get_all_subjects()

@app.post("/api/topic")
def set_topic(data: TopicSchema):
    database.save_topic(data.subject, data.date, data.lesson_num, data.topic)
    return {"status": "success"}

@app.get("/api/topic")
def get_topic(subject: str, date: str, lesson_num: int):
    topic = database.get_topic(subject, date, lesson_num)
    return {"topic": topic}
