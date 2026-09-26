from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io

from database import SessionLocal, init_db, User, Course, Student, Grade

app = FastAPI(title="College Journal Management System")

app.mount("/static", StaticFiles(directory="static"), name="static")

init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic модели
class LoginRequest(BaseModel):
    username: str
    password: str

class StudentCreate(BaseModel):
    full_name: str
    course_id: int

class GradeSave(BaseModel):
    student_id: int
    teacher_id: int
    course_id: int
    lesson_number: int
    grade_value: str
    date: str

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username, User.password == req.password).first()
    if not user:
        raise HTTPException(status_code=400, detail="Անվավեր մուտքանուն կամ գաղտնաբառ")
    
    return {
        "status": "success",
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "is_kursghek": user.is_kursghek,
        "assigned_course_id": user.assigned_course_id
    }

# Получение списка курсов
@app.get("/api/courses")
def get_courses(db: Session = Depends(get_db)):
    courses = db.query(Course).order_by(Course.id).all()
    return [{"id": c.id, "name": c.name} for c in courses]

# Получение студентов выбранного курса
@app.get("/api/courses/{course_id}/students")
def get_students(course_id: int, db: Session = Depends(get_db)):
    students = db.query(Student).filter(Student.course_id == course_id).order_by(Student.full_name).all()
    return [{"id": s.id, "full_name": s.full_name, "course_id": s.course_id} for s in students]

# Админка: Добавление студента вручную
@app.post("/api/admin/students")
def create_student(req: StudentCreate, db: Session = Depends(get_db)):
    student = Student(full_name=req.full_name, course_id=req.course_id)
    db.add(student)
    db.commit()
    db.refresh(student)
    return {"status": "success", "student": {"id": student.id, "full_name": student.full_name}}

# Админка: Удаление студента
@app.delete("/api/admin/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Ուսանողը գտնված չէ")
    db.delete(student)
    db.commit()
    return {"status": "success"}

# Админка: Массовый импорт студентов из Excel/CSV
@app.post("/api/admin/import-students")
async def import_students(file: UploadFile = File(...), course_id: int = 1, db: Session = Depends(get_db)):
    contents = await file.read()
    if file.filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(contents))
    else:
        df = pd.read_excel(io.BytesIO(contents))

    count = 0
    # Ожидаем колонку 'full_name' или берём первую колонку
    col = 'full_name' if 'full_name' in df.columns else df.columns[0]
    for val in df[col].dropna():
        name = str(val).strip()
        if name:
            db.add(Student(full_name=name, course_id=course_id))
            count += 1
    db.commit()
    return {"status": "success", "imported": count}

# Сохранение/обновление оценки
@app.post("/api/grades")
def save_grade(req: GradeSave, db: Session = Depends(get_db)):
    grade = db.query(Grade).filter(
        Grade.student_id == req.student_id,
        Grade.course_id == req.course_id,
        Grade.lesson_number == req.lesson_number,
        Grade.date == req.date
    ).first()

    if grade:
        grade.grade_value = req.grade_value
        grade.teacher_id = req.teacher_id
    else:
        grade = Grade(
            student_id=req.student_id,
            teacher_id=req.teacher_id,
            course_id=req.course_id,
            lesson_number=req.lesson_number,
            grade_value=req.grade_value,
            date=req.date
        )
        db.add(grade)

    db.commit()
    return {"status": "success"}

# Получение оценок для таблицы
@app.get("/api/grades")
def get_grades(course_id: int, date: str, db: Session = Depends(get_db)):
    grades = db.query(Grade).filter(Grade.course_id == course_id, Grade.date == date).all()
    return [{
        "student_id": g.student_id,
        "lesson_number": g.lesson_number,
        "grade_value": g.grade_value
    } for g in grades]
