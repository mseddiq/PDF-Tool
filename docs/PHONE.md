# Private Android and iPhone access

Version 0.4.0 has a responsive browser interface, page controls and a home-screen manifest. PDF processing still runs on your Windows PC. This is not a standalone offline Android/iOS app. Your PC must be on, awake and running PDF Studio; both devices need Internet for remote access.

The recommended private route is **Tailscale Serve**, an encrypted HTTPS reverse proxy available only inside your private Tailscale network. This repository does not set up a public deployment. Do not use Tailscale Funnel or router port forwarding. Use a personal Tailscale network containing only your own authorized devices, or restrict its access policy to your identity before exposing this app. The app itself has no multi-user login; anyone you allow to reach this service can use its workspace.

## Set up once on your Windows PC

1. Install the latest PDF Studio update and run Setup-Windows.cmd. Start it using its desktop shortcut.
2. Install Tailscale on the PC and your Android/iPhone from the official Tailscale site / app store. Sign into your own account on both devices. Do not share the network with other people unless you have configured an access policy limiting this service to you.
3. In Tailscale, find the PC's full DNS name, such as `my-pc.example.ts.net`. HTTPS certificates / MagicDNS may need enabling in the Tailscale administration page; follow Tailscale's prompts.
4. In the extracted PDF Studio folder, open PowerShell and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/configure-phone.ps1
   ```

   Paste only your PC's full `.ts.net` hostname when prompted. This stores that exact hostname in a local `.studio-private-host` file. It allows its HTTPS origin without permitting arbitrary network hosts.

5. Quit PDF Studio through Settings and reopen it with the desktop shortcut. Then run in PowerShell:

   ```powershell
   tailscale serve --bg http://127.0.0.1:8000
   ```

   Follow Tailscale's HTTPS enablement prompt if shown. Copy the HTTPS address it displays. This setup leaves PDF Studio bound to loopback; Tailscale handles the private connection.

## Use on your phone

Keep Tailscale connected and open that HTTPS address in Android Chrome or iPhone Safari. Open a PDF from the phone's file picker. Use **Go to page** to choose its page, then edit, convert or remove the current page. The Properties button opens/closes the smaller-screen editing panel. Download results through the phone browser's normal Files/download interface.

For a launcher icon, use Chrome's **Add to Home screen** or Safari's **Share → Add to Home Screen**. This creates an app-like shortcut; it does not put the processing engine on the phone or make remote processing available without the PC. All uploads go to your own PC, not a conversion provider. Documents opened on your PC may be visible in the same application workspace; treat both devices as access to the same private app.

## Stop or undo

Run `tailscale serve reset` to stop the private proxy. Remove `.studio-private-host` (or unset STUDIO_PRIVATE_HOST if configured instead) and restart PDF Studio to restore its default local-host-only policy. Settings → Quit app stops the PDF service. Closing a phone/browser tab leaves it running.

If you see a host/origin error, check the exact hostname, HTTPS scheme, that both devices use the same authorized tailnet, and that you restarted the app after configuration. Do not change the backend to `0.0.0.0`, disable origin checks, or use a public tunnel to work around it.

Automated tests verify the responsive interface and explicit hostname/origin policy. A real phone-to-PC Tailscale connection, device-specific downloads and home-screen behavior still require a run on your own devices; they are not certified by desktop browser emulation.

For use while your PC is off, a separate private server with authentication and persistent storage would be needed. That is a deployment task with hosting and access-control decisions, not a static website or Streamlit upload of this app.
