"""
Export manager for generating reports and exporting data.
"""

from typing import List, Optional
from datetime import datetime
from pathlib import Path

from ..models import Campaign, MessageLog
from ..utils.logger import Logger


class ExportManager:
    """Manages exporting reports and campaign data."""
    
    def __init__(self):
        """Initialize export manager."""
        pass
    
    def export_campaign_pdf(
        self,
        campaign: Campaign,
        message_logs: List[MessageLog],
        output_file: str
    ) -> bool:
        """
        Export campaign report as PDF.
        
        Args:
            campaign: Campaign object
            message_logs: List of message logs
            output_file: Output PDF file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
            
            doc = SimpleDocTemplate(output_file, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            
            # Title
            title = Paragraph(f"Campaign Report: {campaign.name}", styles['Heading1'])
            elements.append(title)
            elements.append(Spacer(1, 0.3 * inch))
            
            # Campaign summary
            summary_data = [
                ['Campaign Name', campaign.name],
                ['Date', datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                ['Total Contacts', str(campaign.total_contacts)],
                ['Messages Sent', str(campaign.sent_count)],
                ['Messages Failed', str(campaign.failed_count)],
                ['Success Rate', f"{self._calculate_success_rate(campaign.sent_count, campaign.total_contacts):.1f}%"],
            ]
            
            summary_table = Table(summary_data, colWidths=[2 * inch, 2 * inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            
            elements.append(summary_table)
            elements.append(Spacer(1, 0.3 * inch))
            
            # Message logs table
            if message_logs:
                heading = Paragraph("Message Details", styles['Heading2'])
                elements.append(heading)
                elements.append(Spacer(1, 0.1 * inch))
                
                log_data = [['Phone', 'Status', 'Sent At']]
                
                for log in message_logs[:50]:  # Limit to 50 rows
                    log_data.append([
                        log.contact_phone,
                        log.status.value,
                        log.sent_at.strftime("%H:%M:%S") if log.sent_at else 'N/A'
                    ])
                
                log_table = Table(log_data, colWidths=[2 * inch, 1.5 * inch, 1.5 * inch])
                log_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ]))
                
                elements.append(log_table)
            
            # Build PDF
            doc.build(elements)
            
            Logger.info(f"Campaign report exported to {output_file}")
            return True
        
        except ImportError:
            Logger.error("reportlab not installed")
            return False
        except Exception as e:
            Logger.error(f"Error exporting PDF: {e}")
            return False
    
    def export_campaign_excel(
        self,
        campaign: Campaign,
        message_logs: List[MessageLog],
        output_file: str
    ) -> bool:
        """
        Export campaign report as Excel.
        
        Args:
            campaign: Campaign object
            message_logs: List of message logs
            output_file: Output Excel file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import pandas as pd
            
            data = []
            for log in message_logs:
                data.append({
                    'Phone': log.contact_phone,
                    'Name': log.contact_name,
                    'Status': log.status.value,
                    'Sent At': log.sent_at.isoformat() if log.sent_at else '',
                    'Error': log.error_message or ''
                })
            
            df = pd.DataFrame(data)
            df.to_excel(output_file, index=False, engine='openpyxl')
            
            Logger.info(f"Campaign report exported to {output_file}")
            return True
        
        except ImportError:
            Logger.error("pandas or openpyxl not installed")
            return False
        except Exception as e:
            Logger.error(f"Error exporting Excel: {e}")
            return False
    
    @staticmethod
    def _calculate_success_rate(sent: int, total: int) -> float:
        """
        Calculate success rate percentage.
        
        Args:
            sent: Number of messages sent
            total: Total messages
            
        Returns:
            Success rate percentage
        """
        if total == 0:
            return 0.0
        
        return (sent / total) * 100
