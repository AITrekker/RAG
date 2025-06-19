"""
Report export functionality.

This module provides functionality for exporting sync reports to various
formats including CSV, JSON, and PDF with customizable templates.
"""

import logging
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import pandas as pd
from jinja2 import Environment, PackageLoader, select_autoescape
from weasyprint import HTML

from .report_storage import ReportStorage, SyncReport
from .report_generator import ReportGenerator, ReportSummary

logger = logging.getLogger(__name__)

class ReportExporter:
    """Exports sync reports to various formats."""
    
    def __init__(
        self,
        report_storage: ReportStorage,
        report_generator: ReportGenerator,
        export_dir: Optional[Union[str, Path]] = None
    ):
        """Initialize report exporter.
        
        Args:
            report_storage: Report storage instance
            report_generator: Report generator instance
            export_dir: Optional directory for exports
        """
        self.report_storage = report_storage
        self.report_generator = report_generator
        self.export_dir = Path(export_dir) if export_dir else Path.cwd() / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Jinja2 environment for PDF templates
        self.jinja_env = Environment(
            loader=PackageLoader("src.sync", "templates"),
            autoescape=select_autoescape(["html", "xml"])
        )
    
    def export_to_csv(
        self,
        reports: List[SyncReport],
        output_file: Optional[Union[str, Path]] = None
    ) -> Path:
        """Export reports to CSV format.
        
        Args:
            reports: List of reports to export
            output_file: Optional output file path
        
        Returns:
            Path to exported file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.export_dir / f"sync_reports_{timestamp}.csv"
        else:
            output_file = Path(output_file)
        
        # Flatten report data for CSV
        rows = []
        for report in reports:
            row = {
                "task_id": report.task_id,
                "tenant_id": report.tenant_id,
                "timestamp": report.timestamp.isoformat(),
                "status": report.status
            }
            
            # Add metrics
            for metric_type, values in report.metrics.items():
                if values:
                    row[f"metric_{metric_type.value}"] = values[-1].value
            
            # Add details
            for key, value in report.details.items():
                row[f"detail_{key}"] = json.dumps(value)
            
            rows.append(row)
        
        # Write CSV
        with open(output_file, "w", newline="") as f:
            if not rows:
                return output_file
            
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        logger.info(f"Exported {len(reports)} reports to CSV: {output_file}")
        return output_file
    
    def export_to_json(
        self,
        reports: List[SyncReport],
        output_file: Optional[Union[str, Path]] = None,
        pretty: bool = True
    ) -> Path:
        """Export reports to JSON format.
        
        Args:
            reports: List of reports to export
            output_file: Optional output file path
            pretty: Whether to pretty-print JSON
        
        Returns:
            Path to exported file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.export_dir / f"sync_reports_{timestamp}.json"
        else:
            output_file = Path(output_file)
        
        # Convert reports to JSON-serializable format
        data = []
        for report in reports:
            report_data = {
                "task_id": report.task_id,
                "tenant_id": report.tenant_id,
                "timestamp": report.timestamp.isoformat(),
                "status": report.status,
                "metrics": {
                    metric_type.value: [
                        {
                            "value": v.value,
                            "timestamp": v.timestamp.isoformat(),
                            "metadata": v.metadata
                        }
                        for v in values
                    ]
                    for metric_type, values in report.metrics.items()
                },
                "details": report.details
            }
            data.append(report_data)
        
        # Write JSON
        with open(output_file, "w") as f:
            json.dump(
                data,
                f,
                indent=2 if pretty else None,
                default=str
            )
        
        logger.info(f"Exported {len(reports)} reports to JSON: {output_file}")
        return output_file
    
    def export_to_pdf(
        self,
        reports: List[SyncReport],
        summary: Optional[ReportSummary] = None,
        output_file: Optional[Union[str, Path]] = None,
        template_name: str = "report_template.html"
    ) -> Path:
        """Export reports to PDF format.
        
        Args:
            reports: List of reports to export
            summary: Optional report summary
            output_file: Optional output file path
            template_name: Name of HTML template to use
        
        Returns:
            Path to exported file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.export_dir / f"sync_reports_{timestamp}.pdf"
        else:
            output_file = Path(output_file)
        
        # Generate summary if not provided
        if not summary and reports:
            summary = self.report_generator.generate_summary_report(
                start_time=min(r.timestamp for r in reports),
                end_time=max(r.timestamp for r in reports)
            )
        
        # Prepare data for template
        template_data = {
            "reports": [
                {
                    "task_id": report.task_id,
                    "tenant_id": report.tenant_id,
                    "timestamp": report.timestamp,
                    "status": report.status,
                    "metrics": {
                        metric_type.value: values[-1].value
                        for metric_type, values in report.metrics.items()
                        if values
                    },
                    "details": report.details
                }
                for report in reports
            ],
            "summary": summary._asdict() if summary else None,
            "generated_at": datetime.now()
        }
        
        # Render template
        template = self.jinja_env.get_template(template_name)
        html_content = template.render(**template_data)
        
        # Convert to PDF
        HTML(string=html_content).write_pdf(output_file)
        
        logger.info(f"Exported {len(reports)} reports to PDF: {output_file}")
        return output_file
    
    def export_to_excel(
        self,
        reports: List[SyncReport],
        output_file: Optional[Union[str, Path]] = None
    ) -> Path:
        """Export reports to Excel format.
        
        Args:
            reports: List of reports to export
            output_file: Optional output file path
        
        Returns:
            Path to exported file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.export_dir / f"sync_reports_{timestamp}.xlsx"
        else:
            output_file = Path(output_file)
        
        # Convert reports to pandas DataFrame
        data = []
        for report in reports:
            row = {
                "task_id": report.task_id,
                "tenant_id": report.tenant_id,
                "timestamp": report.timestamp,
                "status": report.status
            }
            
            # Add metrics
            for metric_type, values in report.metrics.items():
                if values:
                    row[f"metric_{metric_type.value}"] = values[-1].value
            
            # Add details
            for key, value in report.details.items():
                row[f"detail_{key}"] = str(value)
            
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Write Excel file with formatting
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Reports")
            
            # Auto-adjust column widths
            worksheet = writer.sheets["Reports"]
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[
                    chr(65 + idx)
                ].width = max_length + 2
        
        logger.info(f"Exported {len(reports)} reports to Excel: {output_file}")
        return output_file 