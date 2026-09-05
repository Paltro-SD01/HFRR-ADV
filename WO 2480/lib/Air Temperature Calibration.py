"""
HFRR Air Temperature Calibration Report Generator (2-Point: 0 °C & 60 °C)
=====================================================================
Designed to be called from LabVIEW via a Python Node.

LabVIEW Python Node call signature:
    generate_air_temp_report(
        instrument_serial,   # string
        operator_name,       # string
        measured_zero,       # float, measured value at 0°C setpoint
        measured_sixty,      # float, measured value at 60°C setpoint
        tolerance,           # float, °C (default 0.5)
        output_dir,          # string, folder to save PDF
        logo_path,           # string, path to LOCAL company logo image ("" if none)
        logo_link_url,       # string, URL opened when logo is clicked ("" if none)
        footer_link_url      # string, URL opened when footer text is clicked ("" if none)
    )

Returns: full path to the generated PDF (string)

Save this file e.g. as: C:\\HFRR_Calibration\\generate_air_temp_report.py
LabVIEW Python Node settings:
    Module Name : generate_air_temp_report
    Function    : generate_air_temp_report
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
# Modern Executive Typography & Color Palette Constants (Matching Stroke)
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
def generate_air_temp_report(
    instrument_serial,
    operator_name,
    measured_zero,
    measured_sixty,
    tolerance=0.5,
    output_dir=r"C:\HFRR_Calibration\Reports",
    logo_path="",
    logo_link_url=LOGO_LINK_URL,
    footer_link_url=FOOTER_LINK_URL
):
    """
    Generate an Air Temperature 2-Point Calibration PDF report keeping the exact Stroke design.
    """

    # --- Type Safeguards for LabVIEW Python Node Inputs -----------------
    try:
        measured_zero = float(measured_zero)
    except (ValueError, TypeError):
        measured_zero = 0.0

    try:
        measured_sixty = float(measured_sixty)
    except (ValueError, TypeError):
        measured_sixty = 60.0

    try:
        tolerance = float(tolerance)
    except (ValueError, TypeError):
        tolerance = 0.5

    # --- Calculations -------------------------------------------------
    dev_zero = round(measured_zero - 0.0, 4)
    dev_sixty = round(measured_sixty - 60.0, 4)
    
    max_dev = max(abs(dev_zero), abs(dev_sixty))
    pass_fail = "PASS" if max_dev <= tolerance else "FAIL"

    calibration_name = "Air Temperature Calibration (2-Point)"
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

    # Output: Air_Temperature_Calibration_SERIAL_09-05-2026_143000.pdf
    file_safe_time = timestamp.strftime("%m-%d-%Y_%H%M%S")
    filename = f"Air_Temperature_Calibration_{instrument_serial}_{file_safe_time}.pdf"
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
    
    general_data = [
        [Paragraph("Calibration Profile", table_header_style), Paragraph(calibration_name, table_cell_style)],
        [Paragraph("Instrument Serial", table_header_style), Paragraph(str(instrument_serial), table_cell_style)],
        [Paragraph("Authorized Operator", table_header_style), Paragraph(str(operator_name), table_cell_style)],
        [Paragraph("Execution Timestamp", table_header_style), Paragraph(timestamp_str, table_cell_style)],
    ]
    
    general_table = Table(general_data, colWidths=[50 * mm, 120 * mm])
    general_table.setStyle(TableStyle([
        ["BACKGROUND", (0, 0), (-1, -1), BG_LIGHT_PANEL],
        ["VALIGN", (0, 0), (-1, -1), "MIDDLE"],
        ["TOPPADDING", (0, 0), (-1, -1), 6],
        ["BOTTOMPADDING", (0, 0), (-1, -1), 6],
        ["LEFTPADDING", (0, 0), (-1, -1), 10],
        ["RIGHTPADDING", (0, 0), (-1, -1), 10],
        ["LINEBELOW", (0, 0), (-1, -2), 0.5, BORDER_LIGHT],
        ["BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")],
    ]))
    story.append(general_table)
    story.append(Spacer(1, 10))

    # --- Section 2: Verification Matrix Block --------------------------
    story.append(Paragraph("2. Metrology Matrix", section_style))
    
    matrix_data = [
        [Paragraph("Target Setpoint", table_header_style), Paragraph("Measured Value", table_header_style), Paragraph("Deviation", table_header_style)],
        [Paragraph("0.00 °C", table_cell_style), Paragraph(f"{measured_zero:.3f} °C", table_cell_style), Paragraph(f"{dev_zero:+.3f} °C", table_cell_style)],
        [Paragraph("60.00 °C", table_cell_style), Paragraph(f"{measured_sixty:.3f} °C", table_cell_style), Paragraph(f"{dev_sixty:+.3f} °C", table_cell_style)]
    ]
    
    matrix_table = Table(matrix_data, colWidths=[56 * mm, 57 * mm, 57 * mm])
    matrix_table.setStyle(TableStyle([
        ["BACKGROUND", (0, 0), (-1, 0), BG_LIGHT_PANEL],
        ["VALIGN", (0, 0), (-1, -1), "MIDDLE"],
        ["TOPPADDING", (0, 0), (-1, -1), 6],
        ["BOTTOMPADDING", (0, 0), (-1, -1), 6],
        ["LEFTPADDING", (0, 0), (-1, -1), 10],
        ["RIGHTPADDING", (0, 0), (-1, -1), 10],
        ["LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER_LIGHT],
        ["BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")],
    ]))
    story.append(matrix_table)
    story.append(Spacer(1, 10))

    # --- Section 3: Calibration Status -------------------------------------
    story.append(Paragraph("3. Performance Status", section_style))

    # Dynamic styling and comment selections tailored for Air Temperature parameters
    if pass_fail == "PASS":
        status_card_bg = GREEN_CARD_BG
        status_card_text_color = GREEN_CARD_TXT
        status_comment = f"Air Temperature Calibration PASSED<br/>Max deviation {max_dev:.3f} °C — within ±{tolerance:g} °C tolerance. Two-point correction applied (0 °C & 60 °C)."
        status_text_style = pass_status_style
    else:
        status_card_bg = RED_CARD_BG
        status_card_text_color = RED_CARD_TXT
        status_comment = "Air Temperature Calibration Failed<br/>measured Air Temperature differs from the factory calibration value"
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
        ["BACKGROUND", (1, 0), (1, 0), status_card_bg],
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
    print("=== HFRR Air Temp Report Generator Test Interface ===")
    try:
        val_0 = float(input("Enter measured value at 0 °C Setpoint (e.g. 0.12): "))
        val_60 = float(input("Enter measured value at 60 °C Setpoint (e.g. 59.85): "))
        
        print("\nProcessing air temperature verification logic...")
        
        generated_path = generate_air_temp_report(
            instrument_serial="HFRR-AIR-SERIAL",
            operator_name="Local Air Analyst",
            measured_zero=val_0,
            measured_sixty=val_60,
            tolerance=0.5,
            output_dir="./test_output",
            logo_path="",
            logo_link_url=LOGO_LINK_URL,
            footer_link_url=FOOTER_LINK_URL
        )
        print(f"\nReport processing complete. PDF output saved to:\n{generated_path}")
            
    except ValueError:
        print("Error: Invalid numerical inputs. Please execute the test engine again.")