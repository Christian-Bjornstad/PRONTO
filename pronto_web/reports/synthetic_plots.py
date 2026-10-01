"""Deterministic illustrative plots; no patient images or measurements are reused."""
from io import BytesIO
import math
import random

from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas


def cnv_overview(sample_id, seed, index):
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(780, 330), invariant=1)
    randomizer = random.Random(f'{seed}:{index}:cnv')
    for panel in ('A1', 'A2', 'B2', 'B3', 'C1', 'C2', 'C3', 'C4', 'C6'):
        pdf.setFont('Helvetica-Bold', 14)
        pdf.drawString(35, 300, f'Synthetic demonstration | CNV {panel} | {sample_id}')
        pdf.setFont('Helvetica', 10)
        pdf.drawString(35, 282, 'Illustrative simulated profile - not a measured sample')
        pdf.setStrokeColorRGB(.7, .75, .8)
        pdf.line(45, 45, 750, 45)
        pdf.line(45, 45, 45, 255)
        for value in range(0, 9, 2):
            y = 45 + value * 24
            pdf.drawString(24, y, str(value))
            pdf.line(45, y, 750, y)
        for chromosome in range(1, 23):
            pdf.drawString(45 + chromosome * 30, 25, str(chromosome))
        pdf.drawString(325, 8, 'Simulated chromosome position')
        pdf.setFillColorRGB(.14, .42, .58)
        for point in range(230):
            segment = 3 if 50 < point < 78 else -1 if 145 < point < 170 else 0
            value = max(.1, 2 + segment + .3 * math.sin(point / 8) + randomizer.uniform(-.15, .15))
            pdf.circle(50 + point * 3, 45 + value * 24, 1.7, fill=1, stroke=0)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def rna_domain(sample_id, gene_a, gene_b, event_type):
    image = Image.new('RGB', (1000, 260), 'white')
    drawing = ImageDraw.Draw(image)
    drawing.text((25, 20), f'Synthetic demonstration | {sample_id} | {event_type}', fill='#203b63')
    drawing.text((25, 45), 'Illustrative exon/domain arrangement - not a measured sample', fill='#657085')
    drawing.line((50, 140, 950, 140), fill='#627085', width=3)
    for index in range(9):
        x = 75 + index * 100
        drawing.rectangle((x, 110, x + 60, 170), fill='#277587' if index < 4 else '#859c41')
        drawing.text((x + 18, 185), f'E{index + 1}', fill='#203b63')
    drawing.text((75, 85), gene_a, fill='#203b63')
    drawing.text((575, 85), gene_b, fill='#203b63')
    drawing.line((445, 100, 445, 175), fill='#e88917', width=4)
    drawing.text((365, 225), 'Simulated event boundary', fill='#875807')
    output = BytesIO()
    image.save(output, 'PNG')
    return output.getvalue()
