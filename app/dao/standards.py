"""
Data access object for grading standards.
"""
import os
import yaml
import logging
from typing import Optional
from app.models import GradingStandard, GradeLevel, Dimension, Rubric
from app.schemas.evaluation import StandardDTO

logger = logging.getLogger(__name__)


def get_grading_standard(grade: str, genre: str = "narrative") -> Optional[StandardDTO]:
    """
    Get grading standard by grade and genre.
    
    Args:
        grade: Grade level (e.g., "五年级")
        genre: Essay genre (e.g., "narrative", "expository")
        
    Returns:
        StandardDTO or None if not found
    """
    try:
        # First try to get from database (only if app is in production/development mode)
        from flask import current_app
        if current_app.config.get('TESTING', False):
            # Skip database check in testing mode
            logger.info(f"Testing mode: skipping DB check, loading YAML for {grade}-{genre}")
            return _load_from_yaml(grade, genre)
            
        grade_level = GradeLevel.query.filter_by(name=grade).first()
        if grade_level:
            standard = GradingStandard.query.filter_by(
                grade_level_id=grade_level.id,
                is_active=True
            ).first()
            
            if standard:
                return _convert_to_dto(standard, grade, genre)
        
        # Fallback to YAML file
        logger.info(f"No DB standard found for {grade}-{genre}, trying YAML fallback")
        return _load_from_yaml(grade, genre)
        
    except Exception as e:
        logger.error(f"Error loading grading standard for {grade}-{genre}: {e}")
        return None


def _convert_to_dto(standard: GradingStandard, grade: str, genre: str) -> StandardDTO:
    """Convert database GradingStandard to DTO"""
    dimensions = []
    
    for dim in standard.dimensions:
        rubrics = []
        for rubric in dim.rubrics:
            rubrics.append({
                "level_name": rubric.level_name,
                "description": rubric.description,
                "min_score": rubric.min_score,
                "max_score": rubric.max_score
            })
        
        dimensions.append({
            "name": dim.name,
            "max_score": dim.max_score,
            "rubrics": rubrics
        })
    
    return StandardDTO(
        title=standard.title,
        total_score=standard.total_score,
        grade=grade,
        genre=genre,
        dimensions=dimensions
    )


def _load_from_yaml(grade: str, genre: str) -> Optional[StandardDTO]:
    """Load grading standard from YAML fallback file"""
    try:
        # Map grade names to file names
        grade_file_map = {
            "五年级": "grade5_narrative.yaml",
            "四年级": "grade4_narrative.yaml",
            "三年级": "grade3_narrative.yaml",
        }
        
        filename = grade_file_map.get(grade)
        if not filename:
            logger.warning(f"No YAML fallback for grade: {grade}")
            return None
        
        # Get file path
        # app/dao/standards.py -> go up 3 levels to get to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        yaml_path = os.path.join(project_root, "data", "standards", filename)
        
        if not os.path.exists(yaml_path):
            logger.warning(f"YAML file not found: {yaml_path}")
            return None
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return StandardDTO(
            title=data.get("title", f"{grade}作文评分标准"),
            total_score=data.get("total_score", 100),
            grade=grade,
            genre=genre,
            dimensions=data.get("dimensions", [])
        )
        
    except Exception as e:
        logger.error(f"Error loading YAML standard for {grade}-{genre}: {e}")
        return None