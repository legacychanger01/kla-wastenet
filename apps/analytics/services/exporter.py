"""KLA WasteNet Pro — Report Export Service"""
import io
import csv
from datetime import date
from django.http import HttpResponse


class ReportExporter:

    def export_csv(self, report_type='requests'):
        from apps.waste.models import PickupRequest

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="kla_wastenet_{report_type}_{date.today()}.csv"'

        writer = csv.writer(response)

        if report_type == 'requests':
            writer.writerow(['Request #', 'Resident', 'Division', 'Category', 'Status', 'Priority', 'Amount (UGX)', 'Paid', 'Date'])
            for r in PickupRequest.objects.select_related('user', 'category').order_by('-created_at'):
                writer.writerow([
                    r.request_number, r.user.get_display_name(), r.division,
                    r.category.name, r.status, r.priority,
                    r.amount_due, 'Yes' if r.is_paid else 'No',
                    r.created_at.strftime('%Y-%m-%d %H:%M'),
                ])
        elif report_type == 'payments':
            from apps.payments.models import Payment
            writer.writerow(['Reference', 'User', 'Gateway', 'Amount (UGX)', 'Status', 'Date'])
            for p in Payment.objects.select_related('user').order_by('-created_at'):
                writer.writerow([
                    p.reference, p.user.get_display_name(), p.get_gateway_display(),
                    p.amount, p.status, p.created_at.strftime('%Y-%m-%d %H:%M'),
                ])

        return response

    def export_excel(self, report_type='requests'):
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = report_type.title()

        # Header style
        header_font = Font(bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill(start_color='1a7a3c', end_color='1a7a3c', fill_type='solid')

        if report_type == 'requests':
            from apps.waste.models import PickupRequest
            headers = ['Request #', 'Resident', 'Phone', 'Division', 'Category', 'Status', 'Priority', 'Amount', 'Paid', 'Date']
            ws.append(headers)

            for r in PickupRequest.objects.select_related('user', 'category').order_by('-created_at'):
                ws.append([
                    r.request_number, r.user.get_display_name(), r.user.phone,
                    r.division, r.category.name, r.status, r.priority,
                    float(r.amount_due), 'Yes' if r.is_paid else 'No',
                    r.created_at.strftime('%Y-%m-%d'),
                ])

        # Apply header styles
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')

        # Auto-width
        for col_idx in range(1, ws.max_column + 1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = 18

        ws.row_dimensions[1].height = 25

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="kla_wastenet_{report_type}_{date.today()}.xlsx"'
        return response

    def export_pdf(self, report_type='requests'):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=1*cm, bottomMargin=1*cm)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        title_style = ParagraphStyle(
            'Title', parent=styles['Title'],
            textColor=colors.HexColor('#1a7a3c'),
            fontSize=16, spaceAfter=20,
        )
        elements.append(Paragraph(f'KLA WasteNet — {report_type.title()} Report', title_style))
        elements.append(Paragraph(f'Generated: {date.today().strftime("%d %B %Y")}', styles['Normal']))
        elements.append(Spacer(1, 20))

        if report_type == 'requests':
            from apps.waste.models import PickupRequest
            data = [['Request #', 'Resident', 'Division', 'Category', 'Status', 'Amount (UGX)', 'Date']]

            for r in PickupRequest.objects.select_related('user', 'category').order_by('-created_at')[:200]:
                data.append([
                    r.request_number, r.user.get_display_name()[:20],
                    r.division.title(), r.category.name, r.status.title(),
                    f"{r.amount_due:,.0f}", r.created_at.strftime('%d/%m/%Y'),
                ])

            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a7a3c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f4f6f8')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('PADDING', (0, 0), (-1, -1), 4),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            elements.append(table)

        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="kla_wastenet_{report_type}_{date.today()}.pdf"'
        return response
