#!/usr/bin/env python3
"""
CLI tool for generating assignment and essay reports.

Usage:
    python tools/gen_report.py --assignment 123 --mode combined --out report.docx
    python tools/gen_report.py --essay-id 456 --out essay_report.docx
"""
import argparse
import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.reporting.service import render_student_docx, render_assignment_docx


def main():
    parser = argparse.ArgumentParser(description='Generate assignment or essay reports')
    parser.add_argument('--assignment', type=int, help='Assignment ID for batch report')
    parser.add_argument('--essay-id', type=int, help='Essay ID for single report')
    parser.add_argument('--mode', choices=['combined', 'zip'], default='combined',
                       help='Batch report mode: combined DOCX or ZIP of individual files')
    parser.add_argument('--out', required=True, help='Output file path')
    
    args = parser.parse_args()
    
    if not args.assignment and not args.essay_id:
        parser.error('Either --assignment or --essay-id must be specified')
    
    if args.assignment and args.essay_id:
        parser.error('Cannot specify both --assignment and --essay-id')
    
    try:
        if args.essay_id:
            print(f"Generating report for essay {args.essay_id}...")
            data = render_student_docx(args.essay_id)
            
            with open(args.out, 'wb') as f:
                f.write(data)
            print(f"Essay report saved to {args.out}")
            
        else:  # assignment
            print(f"Generating {args.mode} report for assignment {args.assignment}...")
            result = render_assignment_docx(args.assignment, mode=args.mode)
            
            if args.mode == 'combined':
                with open(args.out, 'wb') as f:
                    f.write(result)
                print(f"Combined assignment report saved to {args.out}")
            else:  # zip mode
                with open(args.out, 'wb') as f:
                    for chunk in result:
                        f.write(chunk)
                print(f"ZIP assignment report saved to {args.out}")
                
    except Exception as e:
        print(f"Error generating report: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()