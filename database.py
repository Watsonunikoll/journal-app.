import os
import sqlite3
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL")

# Авто-коррекция схемы подключения для SQLAlchemy
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # Фоллбэк на локальный SQLite для локальных тестов
    engine = create_engine("sqlite:///journal.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_order=True, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False) # 'admin', 'teacher'
    is_kursghek = Column(Integer, default=0) # 1 если является Կուրսղեկ
    assigned_course_id = Column(Integer, ForeignKey("courses.id"), nullable=True) # Курс для Կուրսղեկ

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)

class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    lesson_number = Column(Integer, nullable=False) # 1..8
    grade_value = Column(String, nullable=False) # 1..10, 'Բ', 'Հ'
    date = Column(String, nullable=False) # YYYY-MM-DD

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # 1. Создаем 30 курсов, если их еще нет
    if db.query(Course).count() == 0:
        for i in range(1, 31):
            db.add(Course(id=i, name=f"{i}-րդ կուրս"))
        db.commit()

    # 2. Аккаунт администратора
    admin = db.query(User).filter_by(username="admin").first()
    if not admin:
        db.add(User(username="admin", password="admin123", role="admin"))
        db.commit()

    # 3. 30 Преподавателей + привязка режима Կուրսղեկ
    if db.query(User).filter(User.role == "teacher").count() == 0:
        for i in range(1, 31):
            db.add(User(
                username=f"teacher{i}",
                password="password123",
                role="teacher",
                is_kursghek=1,
                assigned_course_id=i
            ))
        db.commit()

    db.close()

if __name__ == "__main__":
    init_db()
