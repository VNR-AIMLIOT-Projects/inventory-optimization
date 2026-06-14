import io
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from typing import List, Dict, Any

class ReportPDF(FPDF):
    def header(self):
        # Logo placeholder (or just title for now)
        self.set_font("helvetica", "B", 18)
        self.cell(0, 10, "Replenix Inventory Optimization Report", border=False, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "I", 10)
        self.cell(0, 10, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", border=False, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

def generate_excel_report(sku: str, metrics: Dict[str, Any], history: List[Dict[str, Any]]) -> io.BytesIO:
    """Generates a multi-sheet Excel workbook as a BytesIO stream."""
    output = io.BytesIO()
    
    # Process history into DataFrame
    df = pd.DataFrame(history)
    if not df.empty:
        # Standardize column names
        df = df.rename(columns={
            "day": "Day",
            "date": "Date",
            "demand": "Demand",
            "inventory": "Inventory",
            "rl_action": "RL Action",
            "human_action": "Human Action",
            "final_action": "Final Action",
            "reward": "Reward",
            "pipeline": "Pipeline"
        })

    # Summary data
    summary_data = {
        "Metric": [
            "SKU",
            "Total Days",
            "Cumulative Reward",
            "Total Revenue ($)",
            "Total Cost ($)",
            "Net Profit ($)",
            "Stockout Days",
            "Avg Inventory"
        ],
        "Value": [
            sku,
            metrics.get("total_days", 0),
            f"{metrics.get('cumulative_reward', 0):.2f}",
            f"{metrics.get('total_revenue', 0):.2f}",
            f"{metrics.get('total_cost', 0):.2f}",
            f"{(metrics.get('total_revenue', 0) - metrics.get('total_cost', 0)):.2f}",
            metrics.get("stockout_days", 0),
            f"{metrics.get('avg_inventory', 0):.2f}"
        ]
    }
    summary_df = pd.DataFrame(summary_data)

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name="Executive Summary", index=False)
        if not df.empty:
            df.to_excel(writer, sheet_name="Simulation Data", index=False)
            
        # Optional: Auto-adjust column widths for Executive Summary
        worksheet = writer.sheets["Executive Summary"]
        for idx, col in enumerate(summary_df.columns):
            max_len = max(
                summary_df[col].astype(str).map(len).max(),
                len(str(col))
            ) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = max_len

    output.seek(0)
    return output


def generate_pdf_report(sku: str, metrics: Dict[str, Any], history: List[Dict[str, Any]]) -> io.BytesIO:
    """Generates a formatted PDF document as a BytesIO stream."""
    pdf = ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # 1. Executive Summary Section
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, f"Executive Summary: {sku}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    pdf.set_font("helvetica", "", 11)
    
    net_profit = metrics.get('total_revenue', 0) - metrics.get('total_cost', 0)
    
    summary_items = [
        (f"Total Days Run: {metrics.get('total_days', 0)}", f"Cumulative Reward: {metrics.get('cumulative_reward', 0):.2f}"),
        (f"Total Revenue: ${metrics.get('total_revenue', 0):.2f}", f"Total Cost: ${metrics.get('total_cost', 0):.2f}"),
        (f"Net Profit: ${net_profit:.2f}", f"Avg Inventory Level: {metrics.get('avg_inventory', 0):.2f}"),
        (f"Stockout Days: {metrics.get('stockout_days', 0)}", "")
    ]
    
    for left, right in summary_items:
        pdf.cell(90, 8, left, border=0)
        pdf.cell(90, 8, right, border=0, new_x="LMARGIN", new_y="NEXT")
        
    pdf.ln(10)
    
    # 2. Data Table Section
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(0, 10, "Day-by-Day Simulation Data", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    # Table Header
    pdf.set_font("helvetica", "B", 9)
    col_widths = [15, 25, 20, 20, 25, 25, 20]
    headers = ["Day", "Date", "Demand", "Inv", "RL Action", "Final Act", "Reward"]
    
    for width, header in zip(col_widths, headers):
        pdf.cell(width, 8, header, border=1, align="C")
    pdf.ln()
    
    # Table Rows
    pdf.set_font("helvetica", "", 9)
    for row in history:
        pdf.cell(col_widths[0], 8, str(row.get("day", "")), border=1, align="C")
        pdf.cell(col_widths[1], 8, str(row.get("date", "")), border=1, align="C")
        pdf.cell(col_widths[2], 8, str(row.get("demand", "")), border=1, align="C")
        pdf.cell(col_widths[3], 8, f"{row.get('inventory', 0):.1f}", border=1, align="C")
        pdf.cell(col_widths[4], 8, str(row.get("rl_action", "")), border=1, align="C")
        pdf.cell(col_widths[5], 8, str(row.get("final_action", "")), border=1, align="C")
        pdf.cell(col_widths[6], 8, f"{row.get('reward', 0):.1f}", border=1, align="C")
        pdf.ln()
        
    # Return as BytesIO
    output = io.BytesIO(pdf.output())
    output.seek(0)
    return output
