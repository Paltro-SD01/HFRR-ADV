"""
HFRR Stroke Calibration Report Generator (1 mm)
=================================================
Designed to be called from LabVIEW via a Python Node.

LabVIEW Python Node call signature:
    generate_report(
        instrument_serial,   # string
        operator_name,       # string
        measured_value,      # float, mm
        nominal_value,       # float, mm (default 1.0)
        tolerance,           # float, mm
        output_dir,          # string, folder to save PDF
        logo_path,           # string, path to LOCAL company logo image ("" if none)
        logo_link_url,       # string, URL opened when logo is clicked ("" if none)
        footer_link_url      # string, URL opened when footer text is clicked ("" if none)
    )

Returns: full path to the generated PDF (string)

Save this file e.g. as: C:\\HFRR_Calibration\\generate_stroke_report.py
LabVIEW Python Node settings:
    Module Name : generate_stroke_report
    Function    : generate_report
"""

import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.utils import ImageReader

# ---------------------------------------------------------------------------
# >>> CONFIGURE HYPERLINK URLs HERE <<<
# ---------------------------------------------------------------------------
LOGO_LINK_URL = "https://www.paltro.com/"
FOOTER_LINK_URL = "https://www.paltro.com/products/product-selector/lubricity"

# ---------------------------------------------------------------------------
# Modern Executive Typography & Color Palette Constants
# ---------------------------------------------------------------------------
SLATE_PRIMARY = HexColor("#2C3E50")     # Rich corporate primary dark
SLATE_SECONDARY = HexColor("#7F8C8D")   # Clean layout frame grey
BORDER_LIGHT = HexColor("#E2E8F0")      # Sophisticated dividing line grey
BG_LIGHT_PANEL = HexColor("#F8F9FA")    # Clean soft background fill

# Modern Pastel Status Tones
GREEN_CARD_BG = HexColor("#E6F4EA")
GREEN_CARD_TXT = HexColor("#137333")
RED_CARD_BG = HexColor("#FCE8E6")
RED_CARD_TXT = HexColor("#C5221F")

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "TitleStyle", parent=styles["Title"],
    fontSize=18, textColor=SLATE_PRIMARY, alignment=TA_LEFT, spaceAfter=2,
    fontName="Helvetica-Bold"
)
section_style = ParagraphStyle(
    "SectionStyle", parent=styles["Heading2"],
    fontSize=10, textColor=SLATE_PRIMARY, spaceBefore=14, spaceAfter=8,
    fontName="Helvetica-Bold", textTransform="uppercase"
)
small_grey = ParagraphStyle(
    "SmallGrey", parent=styles["Normal"], fontSize=8.5, leading=12,
    textColor=SLATE_SECONDARY
)

# Text configurations inside data tables
table_header_style = ParagraphStyle(
    "TableHeader", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold",
    textColor=SLATE_PRIMARY
)
table_cell_style = ParagraphStyle(
    "TableCell", parent=styles["Normal"], fontSize=9, fontName="Helvetica",
    textColor=HexColor("#333333")
)

# Dynamic text banners for status remarks
pass_status_style = ParagraphStyle(
    "PassStatusStyle", parent=styles["Normal"], fontSize=9.5, leading=14,
    textColor=GREEN_CARD_TXT, fontName="Helvetica"
)
fail_status_style = ParagraphStyle(
    "FailStatusStyle", parent=styles["Normal"], fontSize=9.5, leading=14,
    textColor=RED_CARD_TXT, fontName="Helvetica"
)


# ---------------------------------------------------------------------------
# Header / Footer Engine
# ---------------------------------------------------------------------------
def _make_header_footer(logo_image, logo_link_url, footer_link_url, calibration_name):
    def _draw(canvas, doc):
        canvas.saveState()
        width, height = A4

        # Clean thin dividing header line
        canvas.setStrokeColor(HexColor("#BDC3C7"))
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, height - 24 * mm, width - 20 * mm, height - 24 * mm)

        # Image Logo canvas rendering
        if logo_image is not None:
            try:
                max_h = 11 * mm
                iw, ih = logo_image.getSize()
                ratio = iw / ih
                draw_h = max_h
                draw_w = draw_h * ratio
                x = 20 * mm
                y = height - 21 * mm
                canvas.drawImage(
                    logo_image,
                    x, y,
                    width=draw_w, height=draw_h,
                    preserveAspectRatio=True, mask='auto'
                )
                if logo_link_url:
                    canvas.linkURL(
                        logo_link_url,
                        (x, y, x + draw_w, y + draw_h),
                        relative=0, thickness=0
                    )
            except Exception:
                pass

        # Clean document title tracking (Header Top-Right)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(SLATE_PRIMARY)
        canvas.drawRightString(width - 20 * mm, height - 15 * mm, "HFRR Calibration Report")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(SLATE_SECONDARY)
        canvas.drawRightString(width - 20 * mm, height - 20 * mm, calibration_name)

        # Bottom Page Divider rule
        canvas.setStrokeColor(BORDER_LIGHT)
        canvas.setLineWidth(0.5)
        canvas.line(20 * mm, 18 * mm, width - 20 * mm, 18 * mm)

        footer_text = "Fully automated next-gen fuel and lubricant testers: BOCLE-ADV, HFRR-ADV, FBT 3-p"
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(SLATE_PRIMARY)
        canvas.drawCentredString(width / 2, 13 * mm, footer_text)

        # Hyperlinked canvas overlay bounding area configuration
        if footer_link_url:
            text_width = canvas.stringWidth(footer_text, "Helvetica", 7.5)
            x0 = (width - text_width) / 2
            canvas.linkURL(
                footer_link_url,
                (x0, 11 * mm, x0 + text_width, 15.5 * mm),
                relative=0, thickness=0
            )

        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(SLATE_SECONDARY)
        canvas.drawString(
            20 * mm, 7 * mm,
            datetime.now().strftime("Generated: %m/%d/%Y %I:%M:%S %p")
        )
        canvas.drawRightString(width - 20 * mm, 7 * mm, f"Page {doc.page}")

        canvas.restoreState()

    return _draw


# ---------------------------------------------------------------------------
# Main report generation function
# ---------------------------------------------------------------------------
def generate_report(
    instrument_serial,
    operator_name,
    measured_value,
    nominal_value=1.0,
    tolerance=0.02,
    output_dir=r"C:\HFRR_Calibration\Reports",
    logo_path="",
    logo_link_url=LOGO_LINK_URL,
    footer_link_url=FOOTER_LINK_URL
):
    """
    Generate a Stroke Calibration (1 mm) PDF report with modern executive design.
    """

    # --- Type Safeguards for LabVIEW Python Node Inputs -----------------
    try:
        measured_value = float(measured_value)
    except (ValueError, TypeError):
        measured_value = 0.0

    try:
        nominal_value = float(nominal_value)
    except (ValueError, TypeError):
        nominal_value = 1.0

    try:
        tolerance = float(tolerance)
    except (ValueError, TypeError):
        tolerance = 0.02

    # --- Calculations -------------------------------------------------
    deviation = round(measured_value - nominal_value, 4)
    pass_fail = "PASS" if abs(deviation) <= tolerance else "FAIL"

    calibration_name = f"Stroke Calibration for {nominal_value:g} mm"
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%m/%d/%Y %I:%M:%S %p")

    # --- Resolve logo image (local file only) ---------------------------
    logo_image = None
    if logo_path and os.path.isfile(logo_path):
        try:
            logo_image = ImageReader(logo_path)
        except Exception:
            logo_image = None

    # --- Ensure output directory exists --------------------------------
    os.makedirs(output_dir, exist_ok=True)

    file_safe_time = timestamp.strftime("%m-%d-%Y_%H%M%S")
    filename = f"Stroke_Calibration_{nominal_value:g}mm_{instrument_serial}_{file_safe_time}.pdf"
    filepath = os.path.join(output_dir, filename)

    # --- Build document template geometry -------------------------------
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        topMargin=30 * mm,
        bottomMargin=22 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=calibration_name,
    )

    story = []

    # Modernized document title header banner area
    story.append(Paragraph(calibration_name, title_style))
    story.append(Spacer(1, 2))
    story.append(Spacer(1, 8))

    # --- Section 1: General Information ---------------------------------
    story.append(Paragraph("1. General Information", section_style))
    
    # Text encapsulated flows to cleanly handle padding constraints safely
    general_data = [
        [Paragraph("Calibration Profile", table_header_style), Paragraph(calibration_name, table_cell_style)],
        [Paragraph("Instrument Serial", table_header_style), Paragraph(str(instrument_serial), table_cell_style)],
        [Paragraph("Authorized Operator", table_header_style), Paragraph(str(operator_name), table_cell_style)],
        [Paragraph("Calibration Timestamp", table_header_style), Paragraph(timestamp_str, table_cell_style)],
    ]
    
    general_table = Table(general_data, colWidths=[50 * mm, 120 * mm])
    general_table.setStyle(TableStyle([
        ["BACKGROUND", (0, 0), (-1, -1), BG_LIGHT_PANEL],
        ["VALIGN", (0, 0), (-1, -1), "MIDDLE"],
        ["TOPPADDING", (0, 0), (-1, -1), 6],
        ["BOTTOMPADDING", (0, 0), (-1, -1), 6],
        ["LEFTPADDING", (0, 0), (-1, -1), 10],
        ["RIGHTPADDING", (0, 0), (-1, -1), 10],
        ["LINEBELOW", (0, 0), (-1, -2), 0.5, BORDER_LIGHT],  # Elegant subtle horizontal rows
        ["BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")],  # Crisp border housing matrix
    ]))
    story.append(general_table)
    story.append(Spacer(1, 10))

    # --- Section 2: Calibration Status -------------------------------------
    story.append(Paragraph("2. Performance Status", section_style))

    # Dynamic styling configuration assignments based on performance threshold rules
    if pass_fail == "PASS":
        status_card_bg = GREEN_CARD_BG
        status_card_text_color = GREEN_CARD_TXT
        status_comment = (
            "Verification successful. The calculated stroke length remains within the bounds "
            "of the factory accepted tolerance criteria defined for this verification sequence."
        )
        status_text_style = pass_status_style
    else:
        status_card_bg = RED_CARD_BG
        status_card_text_color = RED_CARD_TXT
        status_comment = (
            "Verification warning. The recorded mechanical stroke length drift deviates outside "
            "the safe operational parameters. System calibration maintenance cycle recommended."
        )
        status_text_style = fail_status_style

    # Reconfigured Status metric presentation layout block
    status_label_p = Paragraph("System Condition Assessment", table_header_style)
    status_value_p = Paragraph(
        f"<font name='Helvetica-Bold' size='11' color='{status_card_text_color.hexval()}'>{pass_fail}</font>", 
        ParagraphStyle("CenterSt", alignment=TA_CENTER)
    )

    status_table_data = [[status_label_p, status_value_p]]
    status_table = Table(status_table_data, colWidths=[125 * mm, 45 * mm])
    status_table.setStyle(TableStyle([
        ["VALIGN", (0, 0), (-1, -1), "MIDDLE"],
        ["ALIGN", (1, 0), (1, 0), "CENTER"],
        ["BACKGROUND", (0, 0), (0, 0), BG_LIGHT_PANEL],
        ["BACKGROUND", (1, 0), (1, 0), status_card_bg],  # Pastel highlighted dynamic panel card
        ["TOPPADDING", (0, 0), (-1, -1), 8],
        ["BOTTOMPADDING", (0, 0), (-1, -1), 8],
        ["LEFTPADDING", (0, 0), (0, 0), 10],
        ["BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")],
    ]))
    story.append(status_table)
    story.append(Spacer(1, 8))
    
    # Conditional performance analysis block summary
    story.append(Paragraph(status_comment, status_text_style))

    # --- Build PDF document timeline flow execution pass ---
    header_footer = _make_header_footer(logo_image, logo_link_url, footer_link_url, calibration_name)
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)

    return filepath


# ---------------------------------------------------------------------------
# Standalone execution test (Run directly via Terminal/CMD)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== HFRR Report Generator Test Interface ===")
    try:
        user_input = input("Enter a measured stroke value in mm (e.g. 1.005 or 1.05): ")
        measured_val = float(user_input)
        
        nominal_val = 1.0
        tolerance_val = 0.02
        
        print("\nProcessing calibration logic...")
        
        generated_path = generate_report(
            instrument_serial="HFRR-TEST-SERIAL",
            operator_name="Local Tester",
            measured_value=measured_val,
            nominal_value=nominal_val,
            tolerance=tolerance_val,
            output_dir="./test_output",
            logo_path="",
            logo_link_url=LOGO_LINK_URL,
            footer_link_url=FOOTER_LINK_URL
        )
        
        calc_deviation = abs(measured_val - nominal_val)
        if calc_deviation <= tolerance_val:
            print(f" SUCCESS: [PASS] report generated successfully at:\n {generated_path}")
        else:
            print(f" ALERT: [FAIL] report generated successfully at:\n {generated_path}")
            
    except ValueError:
        print("Error: Invalid numerical value input. Please run the script again.")