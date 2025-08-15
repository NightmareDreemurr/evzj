#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
作文数据查询脚本
用于展示数据库中的作文完整数据结构
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from pathlib import Path

def connect_to_database():
    """连接到SQLite数据库"""
    db_path = Path(__file__).parent / 'app.db'
    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return None
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        print(f"✅ 成功连接到数据库: {db_path}")
        return conn
    except Exception as e:
        print(f"❌ 连接数据库失败: {e}")
        return None

def get_essay_with_full_details(conn, essay_id=None):
    """获取作文的完整详细信息"""
    try:
        # 如果没有指定essay_id，获取第一篇作文
        if essay_id is None:
            cursor = conn.execute("SELECT id FROM essays LIMIT 1")
            result = cursor.fetchone()
            if not result:
                print("❌ 数据库中没有找到任何作文数据")
                return None
            essay_id = result['id']
            print(f"📝 自动选择作文ID: {essay_id}")
        
        # 查询作文基本信息
        essay_query = """
        SELECT e.*, 
               ea.title as assignment_title,
               ea.description as assignment_description,
               ea.due_date as assignment_due_date,
               gs.title as grading_standard_title,
               gs.total_score as grading_standard_total_score
        FROM essays e
        LEFT JOIN essay_assignments ea ON e.assignment_id = ea.id
        LEFT JOIN grading_standards gs ON e.grading_standard_id = gs.id OR ea.grading_standard_id = gs.id
        WHERE e.id = ?
        """
        
        cursor = conn.execute(essay_query, (essay_id,))
        essay = cursor.fetchone()
        
        if not essay:
            print(f"❌ 未找到ID为 {essay_id} 的作文")
            return None
        
        # 查询学生信息（通过enrollment）
        student_query = """
        SELECT u.id as user_id, u.email, u.username, u.full_name, u.nickname,
               sp.id as student_profile_id,
               en.student_number, en.status as enrollment_status,
               c.class_name, c.entry_year, c.graduate_year,
               s.name as school_name
        FROM enrollments en
        JOIN student_profiles sp ON en.student_profile_id = sp.id
        JOIN users u ON sp.user_id = u.id
        JOIN classrooms c ON en.classroom_id = c.id
        JOIN schools s ON c.school_id = s.id
        WHERE en.id = ?
        """
        
        cursor = conn.execute(student_query, (essay['enrollment_id'],))
        student = cursor.fetchone()
        
        # 查询教师信息（如果有作业）
        teacher = None
        if essay['assignment_id']:
            teacher_query = """
            SELECT u.id as user_id, u.email, u.username, u.full_name,
                   tp.id as teacher_profile_id,
                   s.name as school_name
            FROM essay_assignments ea
            JOIN teacher_profiles tp ON ea.teacher_profile_id = tp.id
            JOIN users u ON tp.user_id = u.id
            JOIN schools s ON tp.school_id = s.id
            WHERE ea.id = ?
            """
            
            cursor = conn.execute(teacher_query, (essay['assignment_id'],))
            teacher = cursor.fetchone()
        
        # 查询人工复核信息
        review_query = """
        SELECT mr.*, u.full_name as reviewer_name
        FROM manual_reviews mr
        JOIN teacher_profiles tp ON mr.teacher_id = tp.id
        JOIN users u ON tp.user_id = u.id
        WHERE mr.essay_id = ?
        """
        
        cursor = conn.execute(review_query, (essay_id,))
        manual_review = cursor.fetchone()
        
        # 查询评分标准详细信息
        grading_details = None
        if essay['grading_standard_id'] or (essay['assignment_id'] and essay['grading_standard_title']):
            # 确定使用哪个grading_standard_id
            gs_id = essay['grading_standard_id']
            if not gs_id and essay['assignment_id']:
                # 从作业中获取评分标准ID
                cursor = conn.execute("SELECT grading_standard_id FROM essay_assignments WHERE id = ?", (essay['assignment_id'],))
                result = cursor.fetchone()
                if result:
                    gs_id = result['grading_standard_id']
            
            if gs_id:
                grading_query = """
                SELECT gs.*, gl.name as grade_level_name,
                       d.id as dimension_id, d.name as dimension_name, d.max_score as dimension_max_score
                FROM grading_standards gs
                JOIN grade_levels gl ON gs.grade_level_id = gl.id
                LEFT JOIN dimensions d ON gs.id = d.standard_id
                WHERE gs.id = ?
                ORDER BY d.id
                """
                
                cursor = conn.execute(grading_query, (gs_id,))
                grading_rows = cursor.fetchall()
                
                if grading_rows:
                    grading_details = {
                        'standard_info': {
                            'id': grading_rows[0]['id'],
                            'title': grading_rows[0]['title'],
                            'total_score': grading_rows[0]['total_score'],
                            'grade_level': grading_rows[0]['grade_level_name'],
                            'is_active': grading_rows[0]['is_active']
                        },
                        'dimensions': []
                    }
                    
                    for row in grading_rows:
                        if row['dimension_id']:
                            grading_details['dimensions'].append({
                                'id': row['dimension_id'],
                                'name': row['dimension_name'],
                                'max_score': row['dimension_max_score']
                            })
        
        # 组装完整数据
        full_data = {
            'essay_info': dict(essay),
            'student_info': dict(student) if student else None,
            'teacher_info': dict(teacher) if teacher else None,
            'manual_review': dict(manual_review) if manual_review else None,
            'grading_standard_details': grading_details
        }
        
        return full_data
        
    except Exception as e:
        print(f"❌ 查询作文数据时出错: {e}")
        return None

def format_json_data(data):
    """格式化JSON数据，处理datetime等特殊类型"""
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)
    
    return json.dumps(data, ensure_ascii=False, indent=2, default=json_serializer)

def print_essay_summary(data):
    """打印作文数据摘要"""
    print("\n" + "="*80)
    print("📊 作文数据完整报告")
    print("="*80)
    
    essay = data['essay_info']
    student = data['student_info']
    teacher = data['teacher_info']
    
    print(f"\n📝 作文基本信息:")
    print(f"   ID: {essay['id']}")
    print(f"   状态: {essay['status']}")
    print(f"   创建时间: {essay['created_at']}")
    print(f"   是否来自OCR: {'是' if essay['is_from_ocr'] else '否'}")
    print(f"   最终得分: {essay['final_score'] or '未评分'}")
    
    if student:
        print(f"\n👤 学生信息:")
        print(f"   姓名: {student['full_name']}")
        print(f"   用户名: {student['username']}")
        print(f"   学号: {student['student_number'] or '无'}")
        print(f"   班级: {student['class_name']}")
        print(f"   学校: {student['school_name']}")
    
    if teacher:
        print(f"\n👨‍🏫 教师信息:")
        print(f"   姓名: {teacher['full_name']}")
        print(f"   学校: {teacher['school_name']}")
    
    if essay['assignment_title']:
        print(f"\n📋 作业信息:")
        print(f"   标题: {essay['assignment_title']}")
        print(f"   描述: {essay['assignment_description'] or '无'}")
        print(f"   截止日期: {essay['assignment_due_date'] or '无'}")
    
    if data['grading_standard_details']:
        gs = data['grading_standard_details']['standard_info']
        print(f"\n📏 评分标准:")
        print(f"   标题: {gs['title']}")
        print(f"   年级: {gs['grade_level']}")
        print(f"   总分: {gs['total_score']}")
        print(f"   评分维度数量: {len(data['grading_standard_details']['dimensions'])}")
    
    if essay['content']:
        content_preview = essay['content'][:200] + "..." if len(essay['content']) > 200 else essay['content']
        print(f"\n📄 作文内容预览:")
        print(f"   {content_preview}")
    
    if essay['ai_score']:
        print(f"\n🤖 AI评分信息:")
        try:
            ai_score = json.loads(essay['ai_score']) if isinstance(essay['ai_score'], str) else essay['ai_score']
            print(f"   AI评分数据: {type(ai_score)} - {str(ai_score)[:100]}...")
        except:
            print(f"   AI评分数据: {str(essay['ai_score'])[:100]}...")
    
    if data['manual_review']:
        print(f"\n✅ 人工复核:")
        print(f"   复核教师: {data['manual_review']['reviewer_name']}")
        print(f"   复核时间: {data['manual_review']['created_at']}")

def get_database_stats(conn):
    """获取数据库统计信息"""
    stats = {}
    
    tables = ['users', 'essays', 'essay_assignments', 'schools', 'classrooms', 'enrollments']
    
    for table in tables:
        try:
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            result = cursor.fetchone()
            stats[table] = result['count']
        except Exception as e:
            stats[table] = f"错误: {e}"
    
    return stats

def main():
    """主函数"""
    print("🔍 作文数据查询工具")
    print("-" * 50)
    
    # 连接数据库
    conn = connect_to_database()
    if not conn:
        return
    
    try:
        # 获取数据库统计
        print("\n📊 数据库统计信息:")
        stats = get_database_stats(conn)
        for table, count in stats.items():
            print(f"   {table}: {count} 条记录")
        
        # 查询作文数据
        print("\n🔍 正在查询作文数据...")
        essay_data = get_essay_with_full_details(conn)
        
        if essay_data:
            # 打印摘要
            print_essay_summary(essay_data)
            
            # 询问是否输出完整JSON
            print("\n" + "="*80)
            print("💾 完整数据结构 (JSON格式):")
            print("="*80)
            print(format_json_data(essay_data))
            
        else:
            print("❌ 未能获取到作文数据")
            
    except Exception as e:
        print(f"❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    main()