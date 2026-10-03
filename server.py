from database import SessionLocal, init_db, User, Course, Subject, Student, Grade, LessonTopic
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

# Pydantic-схемы
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
    assigned_course_ids: List[int] = []
    subject_ids: List[int] = []

class AdminTeacherUpdate(BaseModel):
    user_id: int
    username: str
    password: Optional[str] = ""
    full_name: str
    is_kursghek: int
    course_ids: List[int] = []
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
    
    subjs = [{"id": s.id, "name": s.name} for s in getattr(user, 'subjects', [])]
    
    managed_courses = []
    assigned_course_ids = []

    # Безопасное получение связей с курсами
    if hasattr(user, 'courses') and user.courses:
        managed_courses = [{"id": c.id, "name": c.name} for c in user.courses]
        assigned_course_ids = [c.id for c in user.courses]
    elif getattr(user, 'assigned_course_id', None):
        c = db.query(Course).filter(Course.id == user.assigned_course_id).first()
        if c:
            managed_courses = [{"id": c.id, "name": c.name}]
            assigned_course_ids = [c.id]

    primary_assigned_id = assigned_course_ids[0] if assigned_course_ids else getattr(user, 'assigned_course_id', None)

    return {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name or user.username,
        "role": user.role,
        "is_kursghek": user.is_kursghek,
        "assigned_course_id": primary_assigned_id,
        "assigned_course_ids": assigned_course_ids,
        "managed_courses": managed_courses,
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
    result = []
    for t in teachers:
        c_ids = []
        if hasattr(t, 'courses') and t.courses:
            c_ids = [c.id for c in t.courses]
        elif getattr(t, 'assigned_course_id', None):
            c_ids = [t.assigned_course_id]

        primary_id = c_ids[0] if c_ids else getattr(t, 'assigned_course_id', None)

        result.append({
            "id": t.id,
            "username": t.username,
            "full_name": t.full_name,
            "is_kursghek": t.is_kursghek,
            "assigned_course_id": primary_id,
            "course_ids": c_ids
        })
    return result


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
    grades = db.query(Grade, Student.full_name, Subject.name, User.full_name)\
        .join(Student, Grade.student_id == Student.id)\
        .join(Subject, Grade.subject_id == Subject.id)\
        .outerjoin(User, Grade.teacher_id == User.id)\
        .filter(Grade.course_id == course_id)\
        .order_by(Grade.date.desc()).all()

    res = []
    for g, st_name, subj_name, teacher_name in grades:
        res.append({
            "date": g.date,
            "student_id": g.student_id,
            "student_name": st_name,
            "subject_name": subj_name,
            "lesson_number": g.lesson_number,
            "grade_value": g.grade_value,
            "teacher_name": teacher_name or "Դասախոս"
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


# --- API АДМИНА ---

@app.get("/api/admin/teacher/{teacher_id}")
def get_teacher_details(teacher_id: int, db: Session = Depends(get_db)):
    t = db.query(User).filter(User.id == teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Դասախոսը գտնված չէ")
    
    subject_ids = [s.id for s in getattr(t, 'subjects', [])]
    
    course_ids = []
    if hasattr(t, 'courses') and t.courses:
        course_ids = [c.id for c in t.courses]
    elif getattr(t, 'assigned_course_id', None):
        course_ids = [t.assigned_course_id]

    return {
        "id": t.id,
        "username": t.username,
        "full_name": t.full_name,
        "is_kursghek": t.is_kursghek,
        "course_ids": course_ids,
        "subject_ids": subject_ids
    }


@app.post("/api/admin/update-teacher")
def update_teacher(req: AdminTeacherUpdate, db: Session = Depends(get_db)):
    t = db.query(User).filter(User.id == req.user_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Դասախոսը գտնված չէ")

    t.username = req.username
    t.full_name = req.full_name
    t.is_kursghek = req.is_kursghek

    if req.password and req.password.strip() != "":
        t.password = req.password

    if req.subject_ids is not None and hasattr(t, 'subjects'):
        subjs = db.query(Subject).filter(Subject.id.in_(req.subject_ids)).all()
        t.subjects = subjs

    if req.course_ids:
        if hasattr(t, 'assigned_course_id'):
            setattr(t, 'assigned_course_id', req.course_ids[0])
        if hasattr(t, 'courses'):
            courses = db.query(Course).filter(Course.id.in_(req.course_ids)).all()
            t.courses = courses
    else:
        if hasattr(t, 'assigned_course_id'):
            setattr(t, 'assigned_course_id', None)
        if hasattr(t, 'courses'):
            t.courses = []

    db.commit()
    return {"status": "success"}


@app.post("/api/admin/create-course")
def create_course(name: str, db: Session = Depends(get_db)):
    c = Course(name=name)
    db.add(c)
    db.commit()
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
    assigned_c_id = req.assigned_course_ids[0] if req.assigned_course_ids else None
    
    user_kwargs = {
        "username": req.username,
        "password": req.password,
        "full_name": req.full_name,
        "role": req.role,
        "is_kursghek": req.is_kursghek,
    }

    if hasattr(User, 'assigned_course_id'):
        user_kwargs["assigned_course_id"] = assigned_c_id

    u = User(**user_kwargs)

    if req.subject_ids and hasattr(u, 'subjects'):
        subjs = db.query(Subject).filter(Subject.id.in_(req.subject_ids)).all()
        u.subjects = subjs

    if hasattr(u, 'courses') and req.assigned_course_ids:
        courses = db.query(Course).filter(Course.id.in_(req.assigned_course_ids)).all()
        u.courses = courses

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
# --- Pydantic Схемы ---
class TopicSave(BaseModel):
    course_id: int
    subject_id: int
    date: str
    lesson_number: int
    topic_text: str

# --- Эндпоинты для Тем Уроков (Lesson Topics) ---

@app.get("/api/topics")
def get_topics(course_id: int, date: str, subject_id: int, db: Session = Depends(get_db)):
    topics = db.query(LessonTopic).filter(
        LessonTopic.course_id == course_id,
        LessonTopic.subject_id == subject_id,
        LessonTopic.date == date
    ).all()
    return {t.lesson_number: t.topic_text for t in topics}

@app.post("/api/topics")
def save_topic(req: TopicSave, db: Session = Depends(get_db)):
    existing = db.query(LessonTopic).filter(
        LessonTopic.course_id == req.course_id,
        LessonTopic.subject_id == req.subject_id,
        LessonTopic.date == req.date,
        LessonTopic.lesson_number == req.lesson_number
    ).first()

    if existing:
        existing.topic_text = req.topic_text
    else:
        top = LessonTopic(
            course_id=req.course_id,
            subject_id=req.subject_id,
            date=req.date,
            lesson_number=req.lesson_number,
            topic_text=req.topic_text
        )
        db.add(top)
    
    db.commit()
    return {"status": "success"}

# --- Обновленный save_grade (поддерживает удаление/очистку оценки) ---

@app.post("/api/grades")
def save_grade(req: GradeSave, db: Session = Depends(get_db)):
    existing = db.query(Grade).filter(
        Grade.student_id == req.student_id,
        Grade.course_id == req.course_id,
        Grade.lesson_number == req.lesson_number,
        Grade.date == req.date,
        Grade.subject_id == req.subject_id
    ).first()

    # Если передана пустая строка "", удаляем оценку из БД
    if req.grade_value == "" or req.grade_value is None:
        if existing:
            if existing.is_locked == 1 and existing.teacher_id != req.teacher_id and req.teacher_id != 0:
                raise HTTPException(status_code=403, detail="Գնահատականը արգելափակված է")
            db.delete(existing)
            db.commit()
        return {"status": "deleted"}

    if existing:
        if existing.is_locked == 1 and existing.teacher_id != req.teacher_id and req.teacher_id != 0:
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

@app.delete("/api/admin/delete-grade")
def delete_grade_admin(student_id: int, course_id: int, subject_id: int, lesson_number: int, date: str, db: Session = Depends(get_db)):
    g = db.query(Grade).filter(
        Grade.student_id == student_id,
        Grade.course_id == course_id,
        Grade.subject_id == subject_id,
        Grade.lesson_number == lesson_number,
        Grade.date == date
    ).first()
    if g:
        db.delete(g)
        db.commit()
    return {"status": "success"}
