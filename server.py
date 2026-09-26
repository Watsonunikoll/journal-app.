from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd
import io

from database import SessionLocal, init_db, User, Course, Subject, Student, Grade

app = FastAPI(title="College Electronic Journal")
app.mount("/static", StaticFiles(directory="static"), name="static")

init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LoginRequest(BaseModel):
    username: str
    password: str

class GradeSave(BaseModel):
    student_id: int
    teacher_id: int
    subject_id: int
    course_id: int
    lesson_number: int
    grade_value: str
    date: str

class AdminCourseUpdate(BaseModel):
    course_id: int
    new_name: str

class AdminUserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str
    is_kursghek: int
    assigned_course_id: Optional[int] = None
    subject_ids: List[int] = []

class AdminStudentCreate(BaseModel):
    full_name: str
    course_id: int

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.post("/api/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username, User.password == req.password).first()
    if not user:
        raise HTTPException(status_code=400, detail="Անվավեր մուտքանուն կամ գաղտնաբառ")
    
    subjs = [{"id": s.id, "name": s.name} for s in user.subjects]
    return {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name or user.username,
        "role": user.role,
        "is_kursghek": user.is_kursghek,
        "assigned_course_id": user.assigned_course_id,
        "subjects": subjs
    }

@app.get("/api/courses")
def get_courses(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name} for c in db.query(Course).order_by(Course.id).all()]

@app.get("/api/subjects")
def get_subjects(db: Session = Depends(get_db)):
    return [{"id": s.id, "name": s.name} for s in db.query(Subject).order_by(Subject.id).all()]

@app.get("/api/courses/{course_id}/students")
def get_students(course_id: int, db: Session = Depends(get_db)):
    students = db.query(Student).filter(Student.course_id == course_id).order_by(Student.id).all()
    return [{"id": s.id, "full_name": s.full_name, "course_id": s.course_id} for s in students]

@app.get("/api/teachers")
def get_teachers(db: Session = Depends(get_db)):
    teachers = db.query(User).filter(User.role == "teacher").order_by(User.id).all()
    return [{"id": t.id, "username": t.username, "full_name": t.full_name, "is_kursghek": t.is_kursghek, "assigned_course_id": t.assigned_course_id} for t in teachers]

@app.get("/api/grades")
def get_grades(course_id: int, date: str, subject_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Grade).filter(Grade.course_id == course_id, Grade.date == date)
    if subject_id:
        q = q.filter(Grade.subject_id == subject_id)
    grades = q.all()
    return [{
        "id": g.id,
        "student_id": g.student_id,
        "teacher_id": g.teacher_id,
        "subject_id": g.subject_id,
        "lesson_number": g.lesson_number,
        "grade_value": g.grade_value,
        "is_locked": g.is_locked
    } for g in grades]

@app.post("/api/grades")
def save_grade(req: GradeSave, db: Session = Depends(get_db)):
    existing = db.query(Grade).filter(
        Grade.student_id == req.student_id,
        Grade.course_id == req.course_id,
        Grade.lesson_number == req.lesson_number,
        Grade.date == req.date,
        Grade.subject_id == req.subject_id
    ).first()

    if existing:
        if existing.is_locked == 1 and existing.teacher_id != req.teacher_id:
            raise HTTPException(status_code=403, detail="Գնահատականը արգելափակված է")
        existing.grade_value = req.grade_value
    else:
        g = Grade(
            student_id=req.student_id,
            teacher_id=req.teacher_id,
            subject_id=req.subject_id,
            course_id=req.course_id,
            lesson_number=req.lesson_number,
            grade_value=req.grade_value,
            date=req.date,
            is_locked=1
        )
        db.add(g)

    db.commit()
    return {"status": "success"}

@app.get("/api/kursghek/all-grades")
def get_all_course_grades(course_id: int, db: Session = Depends(get_db)):
    grades = db.query(Grade, Student.full_name, Subject.name)\
        .join(Student, Grade.student_id == Student.id)\
        .join(Subject, Grade.subject_id == Subject.id)\
        .filter(Grade.course_id == course_id)\
        .order_by(Grade.date.desc()).all()

    res = []
    for g, st_name, subj_name in grades:
        res.append({
            "date": g.date,
            "student_name": st_name,
            "subject_name": subj_name,
            "lesson_number": g.lesson_number,
            "grade_value": g.grade_value
        })
    return res

@app.get("/api/kursghek/export-excel")
def export_excel(course_id: int, db: Session = Depends(get_db)):
    grades = db.query(Grade, Student.full_name, Subject.name)\
        .join(Student, Grade.student_id == Student.id)\
        .join(Subject, Grade.subject_id == Subject.id)\
        .filter(Grade.course_id == course_id).all()

    data = []
    for g, st_name, subj_name in grades:
        data.append({
            "Ամսաթիվ": g.date,
            "Ուսանող": st_name,
            "Առարկա": subj_name,
            "Դաս №": g.lesson_number,
            "Գնահատական": g.grade_value
        })

    df = pd.DataFrame(data)
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Հաշվետվություն')
    stream.seek(0)

    headers = {'Content-Disposition': f'attachment; filename="course_{course_id}_report.xlsx"'}
    return StreamingResponse(stream, headers=headers, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# API АДМИНА
@app.post("/api/admin/create-course")
def create_course(name: str, db: Session = Depends(get_db)):
    c = Course(name=name)
    db.add(c)
    db.commit()
    # Добавляем сразу 30 студентов
    for i in range(1, 31):
        db.add(Student(full_name=f"Student {i}", course_id=c.id))
    db.commit()
    return {"status": "success"}

@app.post("/api/admin/update-course")
def update_course(req: AdminCourseUpdate, db: Session = Depends(get_db)):
    c = db.query(Course).filter(Course.id == req.course_id).first()
    if c:
        c.name = req.new_name
        db.commit()
    return {"status": "success"}

@app.post("/api/admin/add-student")
def add_student(req: AdminStudentCreate, db: Session = Depends(get_db)):
    st = Student(full_name=req.full_name, course_id=req.course_id)
    db.add(st)
    db.commit()
    return {"status": "success"}

@app.delete("/api/admin/delete-student/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    st = db.query(Student).filter(Student.id == student_id).first()
    if st:
        db.delete(st)
        db.commit()
    return {"status": "success"}

@app.post("/api/admin/add-subject")
def add_subject(name: str, db: Session = Depends(get_db)):
    s = Subject(name=name)
    db.add(s)
    db.commit()
    return {"status": "success"}

@app.post("/api/admin/create-user")
def create_user(req: AdminUserCreate, db: Session = Depends(get_db)):
    u = User(
        username=req.username,
        password=req.password,
        full_name=req.full_name,
        role=req.role,
        is_kursghek=req.is_kursghek,
        assigned_course_id=req.assigned_course_id
    )
    if req.subject_ids:
        subjs = db.query(Subject).filter(Subject.id.in_(req.subject_ids)).all()
        u.subjects = subjs
    db.add(u)
    db.commit()
    return {"status": "success"}

@app.delete("/api/admin/delete-user/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if u:
        db.delete(u)
        db.commit()
    return {"status": "success"}
