# Teacher View Aligned DOCX Export Implementation

## Overview

This implementation adds support for exporting DOCX reports aligned with the teacher's review page display, without any diff markings or UI elements, as specified in the requirements.

## Key Features

### 1. Teacher View Aligned Structure
The exported DOCX follows the exact structure specified:
- **Header**: 批阅作业 - {作业名}（{学生名}）
- **Basic Info**: 作业、学生、提交时间
- **Scoring Table**: 总分与维度评分明细（无diff）
- **Essay Content**: 当前作文内容（教师最终版本，无diff标记）
- **AI Enhanced Sections**: 综合评价、优点、改进建议、AI增强内容审核

### 2. No Diff Rendering
- Uses `currentEssayContent` (teacher's final version) without any diff markings
- Excludes all UI elements (navigation, sidebars, buttons, etc.)
- Pure content export aligned with teacher's final review

### 3. Data Field Mapping
Maps frontend data structure to export format:
```python
# Frontend → Export
content_source → currentEssayContent  # Teacher's final text
grading_result → structured scoring data
evaluation_data → AI enhanced content sections
```

## Usage

### Programmatic Usage
```python
from app.reporting.service import render_teacher_view_docx

# Generate teacher view aligned DOCX for essay ID 12
docx_bytes = render_teacher_view_docx(12)

with open('teacher_report.docx', 'wb') as f:
    f.write(docx_bytes)
```

### CLI Usage
```bash
# Generate teacher view report
python tools/gen_report.py --essay-id 12 --teacher-view --out teacher_report.docx

# Generate legacy format report
python tools/gen_report.py --essay-id 12 --out legacy_report.docx
```

### Testing
```bash
# Run unit tests
python test_teacher_view_units.py

# Test with sample data
python test_teacher_view_export.py
```

## Implementation Details

### Data Flow
1. **Data Collection**: `build_teacher_view_evaluation()` extracts data from:
   - Essay model (content, teacher corrections)
   - Grading results (with teacher overrides applied)
   - Evaluation data (AI enhanced content)

2. **Context Building**: `to_context()` maps data to template variables

3. **Rendering**: Both docxtpl and python-docx paths support the structure

### Template Variables
Key template variables available:
- `assignmentTitle`, `studentName`, `submittedAt`
- `currentEssayContent` (no diff)
- `gradingResult.dimensions[]` with scoring details
- `outline[]`, `diagnoses[]`, `personalizedPractices[]`
- `summaryData`, `parentSummary`

### Backward Compatibility
- Legacy format rendering still supported
- Auto-detection based on data fields present
- Existing APIs remain unchanged

## Validation

### Test Coverage
- ✅ Teacher view rendering with full data
- ✅ Legacy format compatibility
- ✅ Auto-detection of format
- ✅ Empty/missing data handling
- ✅ CLI tool functionality

### Sample Output Verification
Generated DOCX includes all required sections:
1. 抬头信息 with assignment/student details
2. 评分结果 with dimension table (no diff)
3. 作文正文 (teacher's final content, no diff)
4. 综合评价与寄语
5. 主要优点 (bullet points)
6. 改进建议 (bullet points)
7. AI 增强内容审核 (4 sub-sections)

### Field Mapping Validation
Ensures proper mapping from teacher review page data:
- `content_source` → pure text essay content
- Dimension scoring → structured table format
- AI analysis → organized review sections

## Error Handling
- Graceful fallback for missing data fields
- Default placeholders: "（本项暂无数据）"
- Maintains export functionality even with incomplete data
- Clear error messages for debugging

## Configuration
No additional configuration required - works with existing setup:
- Uses existing DOCX template infrastructure
- Leverages current evaluation data models
- Compatible with existing database schema