from PIL import Image
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import sys


def convert_rgb_to_cmyk_pdf(input_file, output_file):
    """
    Convert an RGB image to CMYK and create a PDF.
    """

    input_path = Path(input_file)
    output_path = Path(output_file)

    # Check that the input file exists
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    # Open the image and make sure it is RGB
    rgb_image = Image.open(input_path).convert("RGB")

    print(f"Input image: {rgb_image.size[0]} x {rgb_image.size[1]}")
    print(f"Input mode: {rgb_image.mode}")

    # Convert the COMPLETE image from RGB to CMYK
    cmyk_image = rgb_image.convert("CMYK")

    print(f"Output mode: {cmyk_image.mode}")

    # Create PDF dimensions based on the image dimensions
    width, height = cmyk_image.size

    # Create the PDF
    pdf = canvas.Canvas(
        str(output_path),
        pagesize=(width, height)
    )

    # Place the converted image across the entire page
    pdf.drawImage(
        ImageReader(cmyk_image),
        0,
        0,
        width=width,
        height=height,
        preserveAspectRatio=False
    )

    # Finish PDF
    pdf.showPage()
    pdf.save()

    print(f"PDF created successfully: {output_path}")

    return output_path


def main():

    # Make sure the user supplied input and output files
    if len(sys.argv) < 3:
        print()
        print("PrintPrep RGB → CMYK Converter")
        print("--------------------------------")
        print()
        print("Usage:")
        print("python converter.py input.png output.pdf")
        print()
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:

        convert_rgb_to_cmyk_pdf(
            input_file,
            output_file
        )

        print()
        print("SUCCESS")
        print("RGB image converted to CMYK.")
        print(f"Output: {output_file}")

    except Exception as error:

        print()
        print("ERROR")
        print(error)

        sys.exit(1)


if __name__ == "__main__":
    main()