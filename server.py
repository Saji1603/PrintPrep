import base64
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from PIL import Image, ImageCms


HOST = "0.0.0.0"
PORT = int(__import__("os").environ.get("PORT", "8765"))

BASE_DIR = Path(__file__).resolve().parent
PROFILES_DIR = BASE_DIR / "profiles"


class PrintPrepHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} - {format % args}")

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, status, data):
        response = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_cors_headers()
        self.end_headers()

        self.wfile.write(response)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):

        if self.path == "/":
            self.send_json(
                200,
                {
                    "success": True,
                    "service": "PrintPrep",
                    "status": "running",
                },
            )
            return

        if self.path == "/health":
            self.send_json(
                200,
                {
                    "success": True,
                    "status": "ok",
                },
            )
            return

        self.send_json(
            404,
            {
                "success": False,
                "error": "Endpoint not found.",
            },
        )

    def do_POST(self):

        if self.path != "/convert":
            self.send_json(
                404,
                {
                    "success": False,
                    "error": "Endpoint not found.",
                },
            )
            return

        try:
            # ---------------------------------------------------------
            # READ REQUEST
            # ---------------------------------------------------------

            content_length = int(
                self.headers.get("Content-Length", "0")
            )

            if content_length <= 0:
                raise ValueError("Empty request received.")

            body = self.rfile.read(content_length)

            payload = json.loads(
                body.decode("utf-8")
            )

            image_base64 = payload.get("image")

            filename = payload.get(
                "filename",
                "PrintPrep"
            )

            width = payload.get("width")
            height = payload.get("height")

            # Optional ICC profile name.
            #
            # Example:
            # "iccProfile": "RSWOP.icm"
            #
            # If this is empty or missing, PrintPrep falls back
            # to the normal Pillow RGB -> CMYK conversion.

            icc_profile_name = payload.get(
                "iccProfile"
            )

            if not image_base64:
                raise ValueError(
                    "No artwork image was received."
                )

            print()
            print("=" * 60)
            print("PRINTPREP CONVERSION REQUEST")
            print("=" * 60)

            print(f"Artwork: {filename}")

            if width and height:
                print(
                    f"Figma size: {width} x {height} px"
                )

            # ---------------------------------------------------------
            # DECODE IMAGE
            # ---------------------------------------------------------

            image_bytes = base64.b64decode(
                image_base64
            )

            image = Image.open(
                io.BytesIO(image_bytes)
            )

            print(
                f"Input image mode: {image.mode}"
            )

            print(
                f"Input image size: {image.size}"
            )

            # ---------------------------------------------------------
            # FLATTEN TRANSPARENCY
            # ---------------------------------------------------------

            if image.mode == "RGBA":

                print(
                    "Flattening RGBA transparency onto white..."
                )

                background = Image.new(
                    "RGB",
                    image.size,
                    (255, 255, 255),
                )

                alpha = image.getchannel("A")

                background.paste(
                    image,
                    mask=alpha,
                )

                image = background

            elif image.mode == "LA":

                print(
                    "Flattening LA transparency onto white..."
                )

                background = Image.new(
                    "RGB",
                    image.size,
                    (255, 255, 255),
                )

                alpha = image.getchannel("A")

                grayscale = image.convert("RGB")

                background.paste(
                    grayscale,
                    mask=alpha,
                )

                image = background

            else:

                image = image.convert("RGB")

            # ---------------------------------------------------------
            # RGB -> CMYK
            # ---------------------------------------------------------

            if icc_profile_name:

                print()
                print(
                    "ICC COLOR MANAGEMENT ENABLED"
                )

                profile_path = (
                    PROFILES_DIR
                    / icc_profile_name
                )

                print(
                    f"ICC profile: {profile_path}"
                )

                if not profile_path.exists():
                    raise FileNotFoundError(
                        f"ICC profile not found: {profile_path}"
                    )

                # Load the RGB source profile.
                #
                # Figma artwork is exported as RGB PNG,
                # so sRGB is used as the source color space.

                srgb_profile = ImageCms.createProfile(
                    "sRGB"
                )

                # Load the selected CMYK printer profile.

                cmyk_profile = (
                    ImageCms.getOpenProfile(
                        str(profile_path)
                    )
                )

                print(
                    "Source profile: sRGB"
                )

                print(
                    "Destination profile:",
                    ImageCms.getProfileDescription(
                        cmyk_profile
                    ),
                )

                print(
                    "Converting sRGB -> CMYK using LittleCMS..."
                )

                cmyk_image = ImageCms.profileToProfile(
                    image,
                    srgb_profile,
                    cmyk_profile,
                    renderingIntent=0,
                    outputMode="CMYK",
                )

                color_mode = "CMYK"
                profile_used = (
                    ImageCms.getProfileDescription(
                        cmyk_profile
                    )
                )

            else:

                print()
                print(
                    "ICC COLOR MANAGEMENT DISABLED"
                )

                print(
                    "Using standard Pillow RGB -> CMYK conversion..."
                )

                cmyk_image = image.convert(
                    "CMYK"
                )

                color_mode = "CMYK"
                profile_used = None

            # ---------------------------------------------------------
            # VERIFY OUTPUT
            # ---------------------------------------------------------

            print()

            print(
                f"Output mode: {cmyk_image.mode}"
            )

            print(
                f"Output size: {cmyk_image.size}"
            )

            # ---------------------------------------------------------
            # CREATE PDF
            # ---------------------------------------------------------

            pdf_buffer = io.BytesIO()

            cmyk_image.save(
                pdf_buffer,
                format="PDF",
                resolution=300.0,
            )

            pdf_bytes = (
                pdf_buffer.getvalue()
            )

            pdf_base64 = base64.b64encode(
                pdf_bytes
            ).decode("ascii")

            # ---------------------------------------------------------
            # OUTPUT FILENAME
            # ---------------------------------------------------------

            safe_name = Path(
                filename
            ).stem

            if icc_profile_name:
                output_filename = (
                    f"{safe_name}_"
                    f"CMYK_{Path(icc_profile_name).stem}_"
                    f"PrintPrep.pdf"
                )
            else:
                output_filename = (
                    f"{safe_name}_"
                    f"CMYK_PrintPrep.pdf"
                )

            print(
                f"PDF size: {len(pdf_bytes):,} bytes"
            )

            print(
                f"Output filename: {output_filename}"
            )

            print()
            print(
                "Conversion successful."
            )

            print("=" * 60)
            print()

            # ---------------------------------------------------------
            # RESPONSE
            # ---------------------------------------------------------

            self.send_json(
                200,
                {
                    "success": True,
                    "filename": output_filename,
                    "pdf": pdf_base64,
                    "colorMode": color_mode,
                    "iccProfile": profile_used,
                    "width": cmyk_image.width,
                    "height": cmyk_image.height,
                },
            )

        except Exception as error:

            print()
            print("=" * 60)
            print("PRINTPREP ERROR")
            print("=" * 60)

            print(str(error))

            print("=" * 60)
            print()

            self.send_json(
                500,
                {
                    "success": False,
                    "error": str(error),
                },
            )


def run_server():

    server = HTTPServer(
        (HOST, PORT),
        PrintPrepHandler,
    )

    print()
    print("=" * 60)
    print("              PRINTPREP LOCAL SERVER")
    print("=" * 60)
    print()

    print("Server running at:")
    print(
        f"http://{HOST}:{PORT}"
    )

    print()

    print("Health check:")
    print(
        "http://localhost:8765/health"
    )

    print()

    print("Conversion endpoint:")
    print(
        "http://localhost:8765/convert"
    )

    print()

    print("ICC profiles folder:")
    print(
        str(PROFILES_DIR)
    )

    print()

    print("Waiting for Figma...")

    print()

    print("Press Ctrl+C to stop.")

    print()

    try:
        server.serve_forever()

    except KeyboardInterrupt:

        print()
        print(
            "Stopping PrintPrep server..."
        )

    finally:

        server.server_close()


if __name__ == "__main__":
    run_server()