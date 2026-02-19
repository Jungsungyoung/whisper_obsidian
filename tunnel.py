"""
Cloudflare Quick Tunnel launcher.
Starts cloudflared, waits for the tunnel URL, then prints a QR code.
Run from run.bat in a separate window.
"""
import re
import subprocess
import sys


def main():
    try:
        import qrcode
    except ImportError:
        print("[tunnel] qrcode not installed. Run: pip install qrcode")
        sys.exit(1)

    print("[tunnel] Starting Cloudflare Quick Tunnel...")
    print("[tunnel] Waiting for URL (may take 10-20 seconds)...")

    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:8765"],
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        print("[tunnel] cloudflared not found. Install from:")
        print("[tunnel] https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        sys.exit(1)

    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    for line in proc.stderr:
        match = url_pattern.search(line)
        if match:
            url = match.group(0)
            print("\n" + "=" * 52)
            print(f"  Tunnel URL: {url}")
            print("=" * 52 + "\n")

            qr = qrcode.QRCode(border=2)
            qr.add_data(url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)

            print(f"\n  Scan the QR code above with your phone.\n")
            break

    # Keep cloudflared alive until this window is closed
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()


if __name__ == "__main__":
    main()
