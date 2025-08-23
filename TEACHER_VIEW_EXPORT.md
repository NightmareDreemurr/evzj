# Teacher View Aligned DOCX Export Implementation

## Summary Update (August 2024)
**作业报告页面的三个导出入口均已切换到教师视图对齐版：**
1. **批量导出（合并 DOCX）** - 现在使用教师视图格式生成单个合并 DOCX
2. **批量导出（打包 ZIP）** - 现在使用教师视图格式，每个学生一个 DOCX 文件  
3. **下载代表作文报告** - 现在使用教师视图格式导出代表作文

所有导出均不包含 diff 标记，按教师终稿正文与 7 个板块排版：基本信息、评分结果、作文正文、综合评价与寄语、主要优点、改进建议、AI 增强内容审核。

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

### 3. Batch Export Support (New)
**Three export entry points all use teacher view format:**

#### 批量导出（合并 DOCX）
- Route: `/assignments/{assignment_id}/report/download_batch?mode=combined`
- Function: `render_assignment_docx_teacher_view(assignment_id, mode="combined")`
- Output: Single DOCX file containing all students' teacher view reports
- Implementation: Uses `docxcompose` to merge individual teacher view DOCX files
- Cover page includes assignment metadata (title, class, teacher, generation time)

#### 批量导出（打包 ZIP）  
- Route: `/assignments/{assignment_id}/report/download_batch?mode=zip`
- Function: `render_assignment_docx_teacher_view(assignment_id, mode="zip")`
- Output: ZIP file containing separate teacher view DOCX for each student
- Filename format: `{studentName}_{assignmentTitle}_{YYYYMMDD}.docx`
- Implementation: Uses `zipstream` for memory-efficient streaming

#### 下载代表作文报告
- Route: `/assignments/{assignment_id}/report/download` (representative fallback)
- Function: `render_teacher_view_docx(representative_essay_id)`
- Output: Single teacher view DOCX for the representative essay
- Fallback: When batch mode fails, exports first essay in teacher view format

### 4. Data Field Mapping
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

3. **Single Essay Rendering**: `render_teacher_view_docx()` generates individual teacher view DOCX

4. **Batch Processing**: 
   - **Combined Mode**: `_render_assignment_combined_teacher_view()` uses docxcompose to merge individual DOCX files
   - **ZIP Mode**: `_render_assignment_zip_teacher_view()` streams individual DOCX files into ZIP
   - **Representative**: Direct fallback to `render_teacher_view_docx()` for first essay

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