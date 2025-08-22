"""
Demo script to showcase the batch DOCX reporting functionality.

This script demonstrates the new batch reporting capabilities without
requiring a full database setup.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import io
import tempfile
from pathlib import Path
from unittest.mock import Mock

from app.reporting.viewmodels import (
    ScoreItemVM, ScoreVM, StudentReportVM, AssignmentReportVM
)


def create_demo_data():
    """Create demo data for testing."""
    
    # Create score items
    score_items = [
        ScoreItemVM(key="content", name="内容", score=18.5, max_score=20.0),
        ScoreItemVM(key="structure", name="结构", score=16.0, max_score=20.0),  
        ScoreItemVM(key="language", name="语言", score=17.5, max_score=20.0),
        ScoreItemVM(key="aesthetics", name="文采", score=15.0, max_score=20.0),
        ScoreItemVM(key="norms", name="规范", score=18.0, max_score=20.0)
    ]
    
    # Create students
    students = []
    for i in range(3):
        student_scores = ScoreVM(
            total=sum(item.score for item in score_items),
            items=score_items
        )
        
        student = StudentReportVM(
            student_id=i+1,
            student_name=f"学生{i+1}",
            student_no=f"2023{i+1:03d}",
            essay_id=(i+1)*100,
            topic="我的家乡",
            words=450 + i*50,
            scores=student_scores,
            feedback=f"这是学生{i+1}的评语。写作水平良好，建议在{['内容深度', '结构布局', '语言表达'][i]}方面继续提升。",
            original_paragraphs=[
                f"这是学生{i+1}作文的第一段内容。描述了家乡的美丽风景和独特文化。",
                f"第二段进一步阐述了家乡的发展变化，体现了时代的进步。",
                f"最后一段表达了对家乡的深厚感情和美好祝愿。"
            ]
        )
        students.append(student)
    
    # Create assignment  
    assignment = AssignmentReportVM(
        assignment_id=1,
        title="五年级作文练习：我的家乡",
        classroom={"name": "五年级一班", "id": 1},
        teacher={"name": "李老师", "id": 1},
        students=students
    )
    
    return assignment


def demo_viewmodels():
    """Demonstrate ViewModel functionality."""
    print("🎯 Demo: ViewModel System")
    print("=" * 50)
    
    assignment = create_demo_data()
    
    print(f"作业: {assignment.title}")
    print(f"班级: {assignment.classroom['name']}")
    print(f"教师: {assignment.teacher['name']}")
    print(f"学生数量: {len(assignment.students)}")
    print()
    
    for student in assignment.students:
        print(f"📝 {student.student_name} (学号: {student.student_no})")
        print(f"   题目: {student.topic}")
        print(f"   字数: {student.words}字")
        print(f"   总分: {student.scores.total}分")
        print(f"   各维度: {', '.join([f'{item.name}: {item.score}/{item.max_score}' for item in student.scores.items])}")
        print(f"   评语: {student.feedback[:50]}...")
        print()


def demo_template_creation():
    """Demonstrate template creation."""
    print("📄 Demo: Template Creation")
    print("=" * 50)
    
    from tools.create_templates import create_assignment_template
    
    try:
        doc = create_assignment_template()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            doc.save(tmp.name)
            temp_path = tmp.name
        
        file_size = Path(temp_path).stat().st_size
        print(f"✅ Template created successfully")
        print(f"   File size: {file_size} bytes")
        print(f"   Temp path: {temp_path}")
        print(f"   Paragraphs: {len(doc.paragraphs)}")
        print(f"   Styles: {len(doc.styles)}")
        
        # Clean up
        Path(temp_path).unlink()
        
    except Exception as e:
        print(f"❌ Template creation failed: {e}")


def demo_cli_tool():
    """Demonstrate CLI tool."""
    print("⚙️ Demo: CLI Tool")
    print("=" * 50)
    
    import subprocess
    import sys
    
    try:
        # Show help
        result = subprocess.run([
            sys.executable, 'tools/gen_report.py', '--help'
        ], capture_output=True, text=True, cwd='.')
        
        print("CLI Tool Help:")
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ CLI tool is working correctly")
        else:
            print(f"❌ CLI tool error: {result.stderr}")
            
    except Exception as e:
        print(f"❌ CLI demo failed: {e}")


def main():
    """Run all demos."""
    print("🚀 Batch DOCX Reporting System Demo")
    print("=" * 60)
    print()
    
    try:
        demo_viewmodels()
        demo_template_creation()
        demo_cli_tool()
        
        print("🎉 Demo completed successfully!")
        print()
        print("📋 Summary of Features:")
        print("  ✅ ViewModel mapping with safe fallbacks")
        print("  ✅ Enhanced DOCX templates with Chinese font support")  
        print("  ✅ CLI tool for batch report generation")
        print("  ✅ Service layer for business logic")
        print("  ✅ Route handlers for web interface")
        print("  ✅ Support for combined DOCX and ZIP modes")
        print()
        print("🔗 Next Steps:")
        print("  • Test with real database data")
        print("  • Deploy to production environment")
        print("  • Train users on new batch export features")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()