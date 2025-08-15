#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新生成作业报告的脚本
"""

import sys
import os
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import AssignmentReport
from app.services.ai_report_analyzer import analyze_assignment_with_ai

def regenerate_assignment_report(assignment_id, user_id=1):
    """重新生成指定作业的报告"""
    app = create_app()
    
    with app.app_context():
        try:
            print(f"开始重新生成作业 {assignment_id} 的报告...")
            
            # 删除现有报告（如果存在）
            existing_report = AssignmentReport.query.filter_by(assignment_id=assignment_id).first()
            if existing_report:
                print("删除现有报告...")
                db.session.delete(existing_report)
                db.session.commit()
            
            # 生成新报告
            print("调用AI分析器生成新报告...")
            report_data = analyze_assignment_with_ai(assignment_id)
            
            # 保存报告到数据库
            print("保存报告到数据库...")
            new_report = AssignmentReport(
                assignment_id=assignment_id,
                report_data=json.dumps(report_data, ensure_ascii=False),
                generated_by=user_id
            )
            
            db.session.add(new_report)
            db.session.commit()
            
            print("报告生成成功！")
            
            # 输出问题类型分布数据用于验证
            if 'charts' in report_data and 'problem_types' in report_data['charts']:
                problem_types = report_data['charts']['problem_types']
                print("\n问题类型分布数据：")
                print(f"标签: {problem_types['labels']}")
                print(f"数据: {problem_types['data']}")
            
            return True
            
        except Exception as e:
            print(f"生成报告失败: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    assignment_id = 2  # 作业ID
    success = regenerate_assignment_report(assignment_id)
    
    if success:
        print("\n报告重新生成完成！")
    else:
        print("\n报告生成失败！")
        sys.exit(1)